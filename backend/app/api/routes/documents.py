from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import Document, DocumentChunk, KnowledgeItem, MachineModel, User
from app.schemas import DocumentOut, KnowledgeOut, ReviewRequest
from app.services.audit import write_audit
from app.services.embeddings import embed_text
from app.services.extraction import extract_candidates
from app.services.parser import ParserUnavailable, parse_document

router = APIRouter(tags=["文档与审核"])
logger = logging.getLogger(__name__)
ALLOWED_SUFFIXES = {".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg", ".txt", ".md", ".csv", ".json"}


def _safe_filename(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._\-\u4e00-\u9fff]", "_", Path(name).name)
    return clean[:180] or "upload.bin"


def _discard_uncommitted_upload(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Unable to remove uncommitted upload: path=%s", path)


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    status: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    statement = select(Document)
    if status:
        statement = statement.where(Document.review_status == status)
    return db.scalars(statement.order_by(Document.created_at.desc())).all()


@router.post("/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    title: str = Form(min_length=2, max_length=255),
    doc_type: str = Form(default="manual"),
    version: str = Form(default="1.0"),
    model_codes: str = Form(default=""),
    source_url: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("engineer", "reviewer", "admin")),
):
    settings = get_settings()
    filename = _safe_filename(file.filename or "upload.bin")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="不支持该文件类型")
    content = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status_code=400, detail="不能上传空文件")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件不能超过 {settings.max_upload_mb} MB")
    normalized_models = list(dict.fromkeys(item.strip().upper() for item in model_codes.split(",") if item.strip()))
    if normalized_models:
        existing_models = set(
            db.scalars(select(MachineModel.code).where(MachineModel.code.in_(normalized_models))).all()
        )
        unknown_models = [code for code in normalized_models if code not in existing_models]
        if unknown_models:
            raise HTTPException(status_code=422, detail=f"以下机型尚未建立产品主数据：{'、'.join(unknown_models)}")
    normalized_source_url = source_url.strip() if source_url else None
    if normalized_source_url and urlparse(normalized_source_url).scheme not in {"http", "https"}:
        raise HTTPException(status_code=422, detail="来源网址只允许使用 http 或 https")
    checksum = hashlib.sha256(content).hexdigest()
    duplicate = db.scalar(select(Document).where(Document.checksum == checksum))
    if duplicate:
        raise HTTPException(status_code=409, detail=f"相同文件已存在：{duplicate.title}")
    same_version = db.scalar(
        select(Document).where(Document.title == title, Document.version == version)
    )
    if same_version:
        raise HTTPException(status_code=409, detail="相同名称和版本的资料已经存在")

    target = settings.upload_dir / f"{uuid4().hex}_{filename}"
    target.write_bytes(content)
    document = Document(
        title=title,
        filename=filename,
        stored_path=str(target),
        doc_type=doc_type,
        version=version,
        model_codes=normalized_models,
        source_url=normalized_source_url,
        source_kind="external_public" if normalized_source_url else "internal",
        review_status="pending",
        parse_status="processing",
        uploaded_by=user.id,
        checksum=checksum,
    )
    db.add(document)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        _discard_uncommitted_upload(target)
        raise HTTPException(status_code=409, detail="相同文件或相同名称版本的资料已经存在") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _discard_uncommitted_upload(target)
        logger.exception("Document metadata could not be saved: filename=%s", filename)
        raise HTTPException(status_code=503, detail="资料暂时无法保存，请稍后重试") from exc
    try:
        chunks = parse_document(target)
        for index, chunk in enumerate(chunks):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    heading=chunk.heading,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    embedding=embed_text(chunk.content),
                )
            )
        candidates = extract_candidates(chunks)
        for candidate in candidates:
            db.add(
                KnowledgeItem(
                    title=candidate.title,
                    item_type=candidate.item_type,
                    content=candidate.content,
                    applies_to=document.model_codes,
                    source_title=document.title,
                    source_url=document.source_url,
                    source_section=candidate.source_section,
                    version=document.version,
                    confidence=candidate.confidence,
                    review_status="pending",
                    data_classification=document.source_kind,
                )
            )
        document.parse_status = "complete"
        document.parse_message = (
            f"已生成 {len(chunks)} 个知识片段和 {len(candidates)} 条待审核候选知识"
        )
    except ParserUnavailable as exc:
        document.parse_status = "failed"
        document.parse_message = str(exc)
    except Exception:
        logger.exception("Document parsing failed: document_id=%s filename=%s", document.id, filename)
        document.parse_status = "failed"
        document.parse_message = "解析失败，请检查文件内容或服务日志"
    write_audit(db, user, "document.upload", "document", document.id, {"filename": filename})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _discard_uncommitted_upload(target)
        raise HTTPException(status_code=409, detail="相同文件或相同名称版本的资料已经存在") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(
            "Document transaction failed; uploaded file retained for recovery: path=%s",
            target,
        )
        raise HTTPException(status_code=503, detail="资料保存失败，原文件已保留，请联系管理员") from exc
    db.refresh(document)
    return document


@router.patch("/documents/{document_id}/review", response_model=DocumentOut)
def review_document(
    document_id: int,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("reviewer", "admin")),
):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    if payload.status == "published" and document.parse_status != "complete":
        raise HTTPException(status_code=409, detail="解析未完成的文档不能发布")
    document.review_status = payload.status
    document.reviewed_by = user.id
    document.reviewed_at = datetime.now(timezone.utc)
    linked_items = db.scalars(
        select(KnowledgeItem).where(
            KnowledgeItem.source_title == document.title,
            KnowledgeItem.version == document.version,
        )
    ).all()
    if payload.status == "rejected":
        for item in linked_items:
            if item.review_status != "deprecated":
                item.review_status = "rejected"
                item.reviewed_by = user.id
                item.reviewed_at = document.reviewed_at
    elif payload.status == "deprecated":
        for item in linked_items:
            item.review_status = "deprecated"
            item.reviewed_by = user.id
            item.reviewed_at = document.reviewed_at
    write_audit(
        db,
        user,
        f"document.{payload.status}",
        "document",
        document.id,
        {"note": payload.note} if payload.note else {},
    )
    db.commit()
    db.refresh(document)
    return document


@router.get("/knowledge", response_model=list[KnowledgeOut])
def list_knowledge(
    status: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    statement = select(KnowledgeItem)
    if status:
        statement = statement.where(KnowledgeItem.review_status == status)
    return db.scalars(statement.order_by(KnowledgeItem.updated_at.desc())).all()


@router.patch("/knowledge/{item_id}/review", response_model=KnowledgeOut)
def review_knowledge(
    item_id: int,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("reviewer", "admin")),
):
    item = db.get(KnowledgeItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="知识项不存在")
    source_document = db.scalar(
        select(Document).where(
            Document.title == item.source_title,
            Document.version == item.version,
        )
    )
    if payload.status == "published" and source_document and source_document.review_status != "published":
        raise HTTPException(status_code=409, detail="来源文档尚未发布，不能先发布候选知识")
    item.review_status = payload.status
    item.reviewed_by = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    write_audit(db, user, f"knowledge.{payload.status}", "knowledge", item.id)
    db.commit()
    db.refresh(item)
    return item
