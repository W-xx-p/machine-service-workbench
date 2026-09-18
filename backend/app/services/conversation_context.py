from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Alarm, ConversationContext, MachineModel, Message
from app.services.embeddings import tokenize


MAX_HISTORY_TURNS = 6
MAX_FEEDBACK_ITEMS = 10
RESET_PHRASES = ("重新开始排查", "重置故障上下文", "清空故障上下文")
RESOLVED_PHRASES = ("恢复正常", "问题解决", "已经解决", "故障消失", "报警消失")
UNRESOLVED_PHRASES = ("还是不行", "仍然不行", "故障依旧", "报警还在", "没有解决", "仍未解决")
COMPLETION_PHRASES = ("已检查", "检查过", "做完", "完成了", "已完成", "正常", "没问题", "无异常")
NEGATED_COMPLETION_PHRASES = ("没检查", "未检查", "还没", "没有检查", "尚未")
CHECK_TERM_GROUPS = (
    ("气压", "气源", "压力"),
    ("泄漏", "漏气", "接头", "储气罐"),
    ("过滤器", "过滤组件", "过滤"),
    ("压力开关", "开关输入", "输入状态"),
    ("冷却机", "冷却回路", "冷却液"),
    ("液位", "可见泄漏"),
    ("负载记录", "温度趋势", "记录"),
    ("喷嘴", "冲屑"),
    ("排屑", "切屑", "通道"),
)


@dataclass
class ContextResolution:
    row: ConversationContext
    search_question: str
    inherited_fields: list[str] = field(default_factory=list)
    history_turns_used: int = 0
    notice: str | None = None

    def public(self) -> dict:
        return {
            "model_code": self.row.model_code,
            "serial_number": self.row.serial_number,
            "alarm_code": self.row.alarm_code,
            "symptom": self.row.symptom,
            "completed_checks": list(self.row.completed_checks or []),
            "latest_feedback": self.row.latest_feedback,
            "status": self.row.status,
            "inherited_fields": self.inherited_fields,
            "history_turns_used": self.history_turns_used,
        }


def recent_user_messages(
    db: Session, conversation_id: int, after_message_id: int = 0
) -> list[str]:
    rows = db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role == "user",
            Message.id > after_message_id,
        )
        .order_by(Message.id.desc())
        .limit(MAX_HISTORY_TURNS)
    ).all()
    return [row.content for row in reversed(rows)]


def _latest_message_id(db: Session, conversation_id: int) -> int:
    return db.scalar(
        select(func.max(Message.id)).where(Message.conversation_id == conversation_id)
    ) or 0


def _find_latest_value(texts: list[str], values: list[str]) -> str | None:
    for text in reversed(texts):
        normalized = text.upper().replace(" ", "")
        for value in values:
            if value.upper().replace(" ", "") in normalized:
                return value
    return None


def _unknown_alarm_code(question: str, known_models: list[str]) -> str | None:
    model_set = {item.upper().replace(" ", "") for item in known_models}
    candidates = re.findall(r"(?<![A-Z0-9])[A-Z]{2,6}[-_ ]?\d{3,5}(?![A-Z0-9])", question.upper())
    for candidate in candidates:
        normalized = candidate.replace("_", "-").replace(" ", "-")
        if normalized.replace("-", "") not in model_set and not normalized.startswith("SN-"):
            return normalized
    return None


def _ordinal_indexes(question: str) -> list[int]:
    chinese_numbers = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    indexes: list[int] = []
    for value in re.findall(r"第\s*([一二三四五六七八九十\d]+)\s*(?:步|项)", question):
        number = int(value) if value.isdigit() else chinese_numbers.get(value)
        if number and number > 0:
            indexes.append(number - 1)
    return indexes


def _matched_completed_checks(question: str, alarm: Alarm | None) -> list[str]:
    if not alarm or any(item in question for item in NEGATED_COMPLETION_PHRASES):
        return []
    if not any(item in question for item in COMPLETION_PHRASES + UNRESOLVED_PHRASES + RESOLVED_PHRASES):
        return []

    checks = list(alarm.checks or [])
    matched = [checks[index] for index in _ordinal_indexes(question) if index < len(checks)]
    if matched:
        return matched

    question_tokens = set(tokenize(question))
    ranked: list[tuple[int, str]] = []
    for check in checks:
        overlap = len(question_tokens & set(tokenize(check)))
        for group in CHECK_TERM_GROUPS:
            if any(term in question for term in group) and any(term in check for term in group):
                overlap += 2
        if overlap:
            ranked.append((overlap, check))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [ranked[0][1]] if ranked and ranked[0][0] >= 1 else []


def _feedback_label(question: str) -> str | None:
    if any(item in question for item in RESOLVED_PHRASES):
        return "故障已恢复"
    if any(item in question for item in UNRESOLVED_PHRASES):
        return "检查后故障仍存在"
    if (
        any(item in question for item in ("异常", "泄漏", "不足", "有问题"))
        and any(item in question for item in ("检查", "发现", "测得", "显示", "确认", "检测"))
    ):
        return "检查发现异常"
    if any(item in question for item in ("正常", "没问题", "无异常")):
        return "检查结果正常"
    return None


def _reset_row(row: ConversationContext) -> None:
    row.model_code = None
    row.serial_number = None
    row.alarm_code = None
    row.symptom = None
    row.completed_checks = []
    row.feedback_history = []
    row.latest_feedback = None
    row.status = "collecting_information"
    row.turn_count = 0


def clear_context(db: Session, row: ConversationContext) -> None:
    _reset_row(row)
    row.history_start_message_id = _latest_message_id(db, row.conversation_id)


def resolve_context(
    db: Session,
    conversation_id: int,
    question: str,
    supplied_model: str | None,
    supplied_serial: str | None,
) -> ContextResolution:
    row = db.get(ConversationContext, conversation_id)
    if not row:
        row = ConversationContext(conversation_id=conversation_id)
        db.add(row)
        db.flush()

    previous = {
        "model_code": row.model_code,
        "serial_number": row.serial_number,
        "alarm_code": row.alarm_code,
        "symptom": row.symptom,
    }

    if any(phrase in question for phrase in RESET_PHRASES):
        clear_context(db, row)

    history = recent_user_messages(db, conversation_id, row.history_start_message_id or 0)
    history_used = min(len(history), MAX_HISTORY_TURNS)

    models = db.scalars(select(MachineModel).order_by(MachineModel.id)).all()
    model_codes = [item.code for item in models]
    alarms = db.scalars(select(Alarm).where(Alarm.review_status == "published")).all()
    alarm_codes = [item.code for item in alarms]

    # Reconstruct old conversations lazily, then let the current question override them.
    if not row.model_code and history:
        row.model_code = _find_latest_value(history, model_codes)
    if not row.alarm_code and history:
        row.alarm_code = _find_latest_value(history, alarm_codes)

    context_switched = False
    model_changed = False
    question_model = _find_latest_value([question], model_codes)
    effective_model = question_model or (supplied_model.strip().upper() if supplied_model else None)
    if effective_model and effective_model != row.model_code:
        model_changed = bool(row.model_code or row.alarm_code or history)
        context_switched = model_changed
        row.model_code = effective_model
        row.serial_number = None
        row.alarm_code = None
        row.completed_checks = []
        row.feedback_history = []
        row.latest_feedback = None
        row.symptom = question[:1000]

    if (
        supplied_serial
        and supplied_serial.strip()
        and (not model_changed or supplied_serial.strip() != previous["serial_number"])
    ):
        row.serial_number = supplied_serial.strip()

    question_alarm = _find_latest_value([question], alarm_codes) or _unknown_alarm_code(question, model_codes)
    if question_alarm and question_alarm != row.alarm_code:
        context_switched = context_switched or bool(row.alarm_code or history)
        row.alarm_code = question_alarm
        row.completed_checks = []
        row.feedback_history = []
        row.latest_feedback = None
        row.symptom = question[:1000]

    if context_switched:
        row.history_start_message_id = _latest_message_id(db, conversation_id)
        history = []
        history_used = 0

    alarm = next((item for item in alarms if item.code == row.alarm_code), None)
    new_checks = _matched_completed_checks(question, alarm)
    row.completed_checks = list(dict.fromkeys([*(row.completed_checks or []), *new_checks]))

    feedback = _feedback_label(question)
    if feedback:
        row.latest_feedback = f"{feedback}：{question[:300]}"
        row.feedback_history = [
            *(row.feedback_history or []),
            {"result": feedback, "message": question[:300]},
        ][-MAX_FEEDBACK_ITEMS:]

    if not row.symptom and any(word in question for word in ("报警", "故障", "异常", "不能", "中止", "温升")):
        row.symptom = question[:1000]

    if any(item in question for item in RESOLVED_PHRASES):
        row.status = "resolved"
    elif any(item in question for item in UNRESOLVED_PHRASES) or new_checks:
        row.status = "investigating"
    elif row.model_code and row.alarm_code:
        row.status = "troubleshooting"
    else:
        row.status = "collecting_information"
    row.turn_count = (row.turn_count or 0) + 1

    inherited_fields = [
        key
        for key, current in (
            ("model_code", row.model_code),
            ("serial_number", row.serial_number),
            ("alarm_code", row.alarm_code),
            ("symptom", row.symptom),
        )
        if current and current == previous.get(key)
        and not (key == "model_code" and (question_model or supplied_model))
        and not (key == "serial_number" and supplied_serial)
        and not (key == "alarm_code" and question_alarm)
    ]

    pieces = [question]
    if row.model_code:
        pieces.append(f"当前机床型号：{row.model_code}")
    if row.serial_number:
        pieces.append(f"当前机床序列号：{row.serial_number}")
    if row.alarm_code:
        pieces.append(f"当前报警代码：{row.alarm_code}")
    if row.symptom and row.symptom != question:
        pieces.append(f"最初故障现象：{row.symptom}")
    if row.completed_checks:
        pieces.append("已经完成的检查：" + "；".join(row.completed_checks))
    if row.latest_feedback:
        pieces.append("最近现场反馈：" + row.latest_feedback)
    if history:
        compact_history = "；".join(item[:250] for item in history[-3:])
        pieces.append("最近用户描述：" + compact_history)

    notice = None
    if inherited_fields:
        labels = {
            "model_code": "机床型号",
            "serial_number": "序列号",
            "alarm_code": "报警代码",
            "symptom": "故障现象",
        }
        notice = "本轮已沿用会话中的" + "、".join(labels[item] for item in inherited_fields) + "，并结合此前检查结果继续排查。"

    return ContextResolution(
        row=row,
        search_question="\n".join(pieces)[:5000],
        inherited_fields=inherited_fields,
        history_turns_used=history_used,
        notice=notice,
    )
