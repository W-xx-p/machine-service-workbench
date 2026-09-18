from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alarm, Document, DocumentChunk, MachineModel, MaintenanceCase, Part
from app.services.embeddings import cosine_similarity, embed_text, tokenize
from app.services.graph import graph_service


@dataclass
class Evidence:
    title: str
    source_type: str
    content: str
    source_url: str | None
    section: str | None
    version: str | None
    model_codes: list[str]
    data_classification: str
    score: float = 0.0

    def citation(self) -> dict:
        return {
            "title": self.title,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "section": self.section,
            "version": self.version,
            "model_codes": self.model_codes,
            "data_classification": self.data_classification,
        }


@dataclass
class QAResult:
    answer: str
    confidence: float
    missing_information: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    relation_paths: list[dict] = field(default_factory=list)
    graph_notice: str | None = None


def _match_model(db: Session, question: str, supplied: str | None) -> MachineModel | None:
    if supplied:
        return db.scalar(select(MachineModel).where(MachineModel.code.ilike(supplied.strip())))
    machines = db.scalars(select(MachineModel)).all()
    normalized = question.upper().replace(" ", "")
    return next((machine for machine in machines if machine.code.upper() in normalized), None)


def _score_text(question: str, text: str) -> float:
    query_tokens = set(tokenize(question))
    text_tokens = set(tokenize(text))
    if not query_tokens:
        return 0.0
    return len(query_tokens & text_tokens) / max(1, len(query_tokens))


def _alarm_evidence(alarm: Alarm) -> Evidence:
    content = "\n".join(
        [
            f"报警：{alarm.code} {alarm.title}",
            "可能原因：" + "；".join(alarm.possible_causes),
            "检查顺序：" + "；".join(alarm.checks),
            "建议动作：" + "；".join(alarm.actions),
            "停止条件：" + "；".join(alarm.stop_conditions),
        ]
    )
    return Evidence(
        title=f"{alarm.code} {alarm.title}",
        source_type="alarm",
        content=content,
        source_url=alarm.source_url,
        section=alarm.source_section,
        version=alarm.knowledge_version,
        model_codes=list(alarm.applies_to),
        data_classification=alarm.data_classification,
        score=1.0,
    )


def _part_evidence(part: Part) -> Evidence:
    content = "\n".join(
        [
            f"备件：{part.part_no} {part.name}",
            "关键属性：" + "；".join(f"{key}={value}" for key, value in part.key_specs.items()),
            "下单前核对：" + "；".join(part.verification_notes),
        ]
    )
    return Evidence(
        title=f"{part.part_no} {part.name}",
        source_type="part",
        content=content,
        source_url=part.source_url,
        section=part.category,
        version=None,
        model_codes=list(part.applies_to),
        data_classification=part.data_classification,
        score=1.0,
    )


def _case_evidence(case: MaintenanceCase) -> Evidence:
    content = "\n".join(
        [
            f"现象：{case.symptom}",
            f"原因：{case.root_cause}",
            f"处理：{case.resolution}",
            f"验证：{case.verification}",
        ]
    )
    return Evidence(
        title=f"{case.case_no} {case.title}",
        source_type="case",
        content=content,
        source_url=None,
        section="已审核维修案例",
        version=None,
        model_codes=[case.model_code],
        data_classification=case.data_classification,
        score=0.85,
    )


def _graph_fault_enrichment(
    db: Session,
    model: MachineModel | None,
    alarm: Alarm | None,
    parts: list[Part],
    cases: list[MaintenanceCase],
) -> tuple[list[dict], list[Part], list[MaintenanceCase]]:
    """Use Neo4j associations to enrich, not replace, published SQL records."""
    if not model or not alarm:
        return [], parts, cases
    context = graph_service.fault_context(model.code, alarm.code)
    # A case or part edge alone does not mean that a fault is inside the reviewed
    # pilot scope. Coverage requires the complete model/subsystem/alarm spine.
    if not context or not context.get("subsystems"):
        return [], parts, cases

    relation_paths: list[dict] = []
    for subsystem in context.get("subsystems", []):
        subsystem_name = subsystem.get("name") or subsystem.get("code") or "相关子系统"
        relation_paths.append(
            {
                "path": [model.code, subsystem_name],
                "relation": "机型配置子系统",
                "source_title": subsystem.get("source_title") or model.source_title,
                "source_url": subsystem.get("source_url") or model.source_url,
                "source_section": subsystem.get("source_section"),
                "data_classification": subsystem.get("data_classification") or "official_public",
            }
        )
        relation_paths.append(
            {
                "path": [subsystem_name, alarm.code],
                "relation": "故障定位关联",
                "source_title": subsystem.get("alarm_source_title") or alarm.source_title,
                "source_url": subsystem.get("alarm_source_url") or alarm.source_url,
                "source_section": subsystem.get("alarm_source_section") or alarm.source_section,
                "data_classification": subsystem.get("alarm_data_classification")
                or alarm.data_classification,
            }
        )

    graph_part_numbers = {
        item["part_no"] for item in context.get("parts", []) if item.get("part_no")
    }
    known_part_numbers = {part.part_no for part in parts}
    if graph_part_numbers - known_part_numbers:
        graph_parts = db.scalars(
            select(Part).where(
                Part.part_no.in_(graph_part_numbers - known_part_numbers),
                Part.review_status == "published",
            )
        ).all()
        parts.extend(
            part
            for part in graph_parts
            if not part.applies_to or model.code in part.applies_to
        )
    for item in context.get("parts", []):
        if not item.get("part_no"):
            continue
        relation_paths.append(
            {
                "path": [alarm.code, item["part_no"]],
                "relation": "待核对备件关联",
                "source_title": item.get("source_title") or "故障与备件关联",
                "source_url": item.get("source_url"),
                "source_section": item.get("source_section"),
                "data_classification": item.get("data_classification")
                or "demo_process_data",
            }
        )

    graph_case_numbers = {
        item["case_no"] for item in context.get("cases", []) if item.get("case_no")
    }
    known_case_numbers = {case.case_no for case in cases}
    if graph_case_numbers - known_case_numbers:
        graph_cases = db.scalars(
            select(MaintenanceCase).where(
                MaintenanceCase.case_no.in_(graph_case_numbers - known_case_numbers),
                MaintenanceCase.review_status == "published",
            )
        ).all()
        cases.extend(case for case in graph_cases if case.model_code == model.code)
    for item in context.get("cases", []):
        if not item.get("case_no"):
            continue
        relation_paths.append(
            {
                "path": [alarm.code, item["case_no"]],
                "relation": "相似维修案例",
                "source_title": item.get("title") or "已审核维修案例",
                "source_url": None,
                "source_section": "案例关联",
                "data_classification": item.get("data_classification")
                or "demo_process_data",
            }
        )
    return relation_paths, parts, cases


def _find_alarm(
    db: Session,
    question: str,
    model: MachineModel | None,
    allow_fuzzy: bool = True,
    supplied: str | None = None,
) -> Alarm | None:
    alarms = db.scalars(select(Alarm).where(Alarm.review_status == "published")).all()
    if supplied:
        supplied_alarm = next(
            (alarm for alarm in alarms if alarm.code.upper() == supplied.strip().upper()),
            None,
        )
        if not supplied_alarm:
            return None
        if model and supplied_alarm.applies_to and model.code not in supplied_alarm.applies_to:
            return None
        return supplied_alarm
    upper = question.upper().replace(" ", "")
    exact = next(
        (
            alarm
            for alarm in alarms
            if alarm.code.upper().replace(" ", "") in upper
            and (not model or not alarm.applies_to or model.code in alarm.applies_to)
        ),
        None,
    )
    if exact:
        return exact
    if not allow_fuzzy:
        return None
    ranked = []
    for alarm in alarms:
        if model and alarm.applies_to and model.code not in alarm.applies_to:
            continue
        searchable = " ".join(
            [alarm.code, alarm.title, alarm.system, *alarm.symptoms, *alarm.possible_causes]
        )
        ranked.append((_score_text(question, searchable), alarm))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] >= 0.12 else None


def _find_parts(db: Session, question: str, model: MachineModel | None) -> list[Part]:
    intent_words = ["备件", "配件", "零件", "物料", "替换", "替代", "采购", "下单"]
    parts = db.scalars(select(Part).where(Part.review_status == "published")).all()
    upper = question.upper()
    exact = [part for part in parts if part.part_no.upper() in upper]
    if exact:
        return [part for part in exact if not model or not part.applies_to or model.code in part.applies_to][:3]
    if not any(word in question for word in intent_words):
        return []
    ranked: list[tuple[float, Part]] = []
    for part in parts:
        if model and part.applies_to and model.code not in part.applies_to:
            continue
        searchable = " ".join([part.part_no, part.name, part.category, *part.verification_notes])
        ranked.append((_score_text(question, searchable), part))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < 0.08:
        return []
    if any(word in question for word in ["哪些", "全部", "列表", "所有"]):
        return [part for score, part in ranked if score >= 0.08][:3]
    # For a specific free-form question, one best fit is safer than several
    # superficially similar order numbers. The parts page remains available for broad searches.
    return [ranked[0][1]]


def _find_cases(
    db: Session, question: str, model: MachineModel | None, alarm: Alarm | None
) -> list[MaintenanceCase]:
    case_intent = any(word in question for word in ["案例", "历史", "相似", "以前", "处理过"])
    cases = db.scalars(
        select(MaintenanceCase).where(MaintenanceCase.review_status == "published")
    ).all()
    ranked: list[tuple[float, MaintenanceCase]] = []
    for case in cases:
        if model and case.model_code != model.code:
            continue
        score = _score_text(
            question,
            " ".join(
                [
                    case.case_no,
                    case.title,
                    case.alarm_code or "",
                    case.symptom,
                    case.root_cause,
                ]
            ),
        )
        if alarm and case.alarm_code == alarm.code:
            score = max(score, 0.95)
        threshold = 0.12 if case_intent or alarm else 0.22
        if score >= threshold:
            ranked.append((score, case))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [case for _, case in ranked[:2]]


def _document_evidence(db: Session, question: str, model: MachineModel | None) -> list[Evidence]:
    query_vector = embed_text(question)
    statement = (
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.review_status == "published", Document.parse_status == "complete")
    )
    if model:
        # Model applicability is rechecked in Python for portable SQLite/PostgreSQL behavior.
        pass
    if db.bind and db.bind.dialect.name == "postgresql" and hasattr(DocumentChunk.embedding, "cosine_distance"):
        statement = statement.order_by(DocumentChunk.embedding.cosine_distance(query_vector)).limit(8)
        rows = db.execute(statement).all()
    else:
        rows = db.execute(statement.limit(500)).all()
        rows = sorted(
            rows,
            key=lambda row: cosine_similarity(row[0].embedding, query_vector),
            reverse=True,
        )[:8]

    results: list[Evidence] = []
    for chunk, document in rows:
        if model and document.model_codes and model.code not in document.model_codes:
            continue
        similarity = cosine_similarity(chunk.embedding, query_vector)
        lexical = _score_text(question, chunk.content)
        score = max(similarity, lexical)
        if score < 0.08:
            continue
        results.append(
            Evidence(
                title=document.title,
                source_type="document",
                content=chunk.content,
                source_url=document.source_url,
                section=chunk.heading or (f"第 {chunk.page_number} 页" if chunk.page_number else None),
                version=document.version,
                model_codes=list(document.model_codes),
                data_classification=document.source_kind,
                score=score,
            )
        )
    return results[:4]


def _product_answer(model: MachineModel) -> QAResult:
    specs = "\n".join(f"- {key}: {value}" for key, value in model.specs.items())
    evidence = Evidence(
        title=model.source_title,
        source_type="product",
        content=specs,
        source_url=model.source_url,
        section="公开产品参数",
        version=model.model_version,
        model_codes=[model.code],
        data_classification=model.data_classification,
        score=1.0,
    )
    return QAResult(
        answer=(
            f"已匹配机型 **{model.code}（{model.name}）**。\n\n"
            f"当前已核验的公开参数：\n{specs}\n\n"
            "这些是公开产品目录参数，不包含具体出厂配置。涉及备件或维修时，还必须核对序列号、配置清单和企业受控手册。"
        ),
        confidence=0.96,
        evidence=[evidence],
    )


def answer_question(
    db: Session,
    question: str,
    model_code: str | None = None,
    serial_number: str | None = None,
    alarm_code: str | None = None,
    completed_checks: list[str] | None = None,
    latest_feedback: str | None = None,
    context_status: str | None = None,
) -> QAResult:
    model = _match_model(db, question, model_code)
    missing: list[str] = []
    fault_intent = any(
        word in question
        for word in ["报警", "故障", "备件", "配件", "换刀", "主轴", "排屑", "异常", "维修"]
    )
    troubleshooting_intent = any(
        word in question
        for word in ["报警", "故障", "异常", "失败", "停机", "温升", "过热", "排查", "不能", "中止"]
    )
    if model_code and not model:
        return QAResult(
            answer=(
                f"当前产品主数据中没有找到机型 **{model_code}**，因此没有继续生成维修建议。"
                "请核对型号拼写，或先由管理员补充该机型和对应受控资料。"
            ),
            confidence=0.1,
            missing_information=[f"有效机床型号（{model_code} 未收录）"],
        )
    if not model and fault_intent:
        missing.append("机床型号")
    if model and fault_intent and not serial_number:
        missing.append("机床序列号（用于核对具体出厂配置）")

    if model and any(word in question for word in ["参数", "行程", "转速", "功率", "扭矩", "介绍"]):
        return _product_answer(model)

    alarm = _find_alarm(
        db,
        question,
        model,
        allow_fuzzy=troubleshooting_intent,
        supplied=alarm_code,
    )
    if context_status == "resolved" and alarm:
        return QAResult(
            answer=(
                f"已记录 **{alarm.code}** 本次故障恢复。建议保留报警发生时间、已执行检查、"
                "恢复后的空载验证结果和工程师确认记录，作为后续复盘依据。\n\n"
                "如果同一报警再次出现，请继续当前会话并补充复现条件；不要因本次恢复而绕过安全检查。"
            ),
            confidence=0.82 if model else 0.68,
            evidence=[_alarm_evidence(alarm)],
        )
    parts = _find_parts(db, question, model)
    cases = _find_cases(db, question, model, alarm)
    relation_paths, parts, cases = _graph_fault_enrichment(db, model, alarm, parts, cases)
    graph_notice = None
    if model and alarm:
        graph_notice = (
            "已使用已审核知识图谱关联补全检索范围；请结合路径的数据分类判断可信边界。"
            if relation_paths
            else "当前机型与报警暂无已审核的图谱关联，本次已自动使用结构化数据与文档检索。"
        )
    documents = _document_evidence(db, question, model)
    evidence: list[Evidence] = []
    sections: list[str] = []

    if alarm:
        evidence.append(_alarm_evidence(alarm))
        applies = "、".join(alarm.applies_to)
        sections.append(
            f"匹配到 **{alarm.code}：{alarm.title}**（风险等级：{alarm.severity}）。\n"
            f"适用演示机型：{applies}。"
        )
        sections.append("**可能原因**\n" + "\n".join(f"- {item}" for item in alarm.possible_causes))
        completed = [item for item in (completed_checks or []) if item in alarm.checks]
        remaining = [item for item in alarm.checks if item not in completed]
        if completed:
            progress = "**本次会话已完成的检查**\n" + "\n".join(f"- {item}" for item in completed)
            if latest_feedback:
                progress += f"\n\n最近现场反馈：{latest_feedback}"
            sections.append(progress)
            if remaining:
                sections.append(
                    "**下一步建议检查**\n"
                    + "\n".join(f"{i + 1}. {item}" for i, item in enumerate(remaining))
                    + "\n\n以上顺序已排除本次会话中确认完成的步骤。"
                )
            else:
                sections.append(
                    "**建议升级处理**：当前已发布知识中的检查步骤均已完成，不再重复推荐。"
                    "请保留报警、负载和现场记录，由授权工程师依据企业受控手册继续诊断。"
                )
        else:
            sections.append("**建议检查顺序**\n" + "\n".join(f"{i + 1}. {item}" for i, item in enumerate(alarm.checks)))
        sections.append("**停止并升级处理的条件**\n" + "\n".join(f"- {item}" for item in alarm.stop_conditions))

    if relation_paths:
        readable_paths = [" → ".join(item["path"]) for item in relation_paths]
        sections.append(
            "**知识图谱关联**\n"
            + "\n".join(f"- {path}" for path in readable_paths)
            + "\n关联路径用于限定检索和提示核对对象，不代表备件可以直接采购或更换。"
        )

    if documents:
        evidence.extend(documents)
        excerpts = []
        for item in documents[:2]:
            compact = re.sub(r"\s+", " ", item.content).strip()
            excerpts.append(f"- {item.title}：{compact[:220]}{'…' if len(compact) > 220 else ''}")
        sections.append("**相关已发布资料**\n" + "\n".join(excerpts))

    if parts:
        evidence.extend(_part_evidence(part) for part in parts)
        sections.append(
            "**相关备件核对线索**\n"
            + "\n".join(
                (
                    f"- {part.part_no} {part.name}："
                    f"{'；'.join(f'{key}={value}' for key, value in part.key_specs.items())}；"
                    f"{'；'.join(part.verification_notes)}"
                )
                for part in parts
            )
        )

    if cases:
        evidence.extend(_case_evidence(case) for case in cases)
        sections.append(
            "**相似历史案例**\n"
            + "\n".join(
                f"- {case.case_no}：{case.title}。关闭验证：{case.verification}" for case in cases
            )
        )

    if not evidence:
        return QAResult(
            answer=(
                "当前已发布知识中没有找到足够可靠的依据，因此没有生成维修结论。"
                "请补充机床型号、序列号、完整报警码、发生步骤和现场现象，或由审核人员导入对应版本的受控手册。"
            ),
            confidence=0.15,
            missing_information=list(
                dict.fromkeys([*missing, "完整报警码或现场现象"])
            ) if missing else ["机床型号", "完整报警码或现场现象"],
            evidence=[],
        )

    if missing:
        sections.insert(
            0,
            f"**适用性提醒**：尚缺少{'、'.join(missing)}，下列内容只能作为定位线索，不能直接执行。",
        )
    if any(item.data_classification == "demo_process_data" for item in evidence):
        sections.append(
            "**数据边界**：本次命中包含演示流程数据，不是制造商维修指令。真实处置前必须用企业受控资料复核。"
        )
    sections.append("任何涉及拆机、带电测量、进入危险区或绕过安全互锁的操作，都必须停止并交由授权工程师处理。")
    confidence = 0.82 if alarm and model else 0.66 if alarm else 0.62 if parts or cases else 0.55
    return QAResult(
        answer="\n\n".join(sections),
        confidence=confidence,
        missing_information=missing,
        evidence=evidence[:6],
        relation_paths=relation_paths,
        graph_notice=graph_notice,
    )
