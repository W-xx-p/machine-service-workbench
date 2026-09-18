from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Conversation, ConversationContext, Feedback, Message, User
from app.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    ConversationContextOut,
    FeedbackCreate,
    RelationPath,
)
from app.services.audit import write_audit
from app.services.conversation_context import clear_context, resolve_context
from app.services.qa import answer_question

router = APIRouter(prefix="/qa", tags=["辅助问答"])


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = db.get(Conversation, payload.conversation_id) if payload.conversation_id else None
    if conversation and conversation.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="不能访问其他用户的会话")
    if not conversation:
        conversation = Conversation(user_id=user.id, title=payload.question[:80])
        db.add(conversation)
        db.flush()
    context = resolve_context(
        db,
        conversation.id,
        payload.question,
        payload.model_code,
        payload.serial_number,
    )
    db.add(Message(conversation_id=conversation.id, role="user", content=payload.question, citations=[]))

    result = answer_question(
        db,
        context.search_question,
        context.row.model_code,
        context.row.serial_number,
        alarm_code=context.row.alarm_code,
        completed_checks=list(context.row.completed_checks or []),
        latest_feedback=context.row.latest_feedback,
        context_status=context.row.status,
    )
    citations = [item.citation() for item in result.evidence]
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.answer,
        citations=citations,
    )
    db.add(assistant_message)
    db.flush()
    write_audit(
        db,
        user,
        "qa.ask",
        "conversation",
        conversation.id,
        {
            "model_code": payload.model_code,
            "serial_supplied": bool(payload.serial_number),
            "evidence_count": len(citations),
            "context_inherited_fields": context.inherited_fields,
            "history_turns_used": context.history_turns_used,
        },
    )
    db.commit()
    return AskResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        answer=result.answer,
        confidence=result.confidence,
        missing_information=result.missing_information,
        citations=[Citation(**item) for item in citations],
        relation_paths=[RelationPath(**item) for item in result.relation_paths],
        graph_notice=result.graph_notice,
        context=ConversationContextOut(**context.public()),
        context_notice=context.notice,
    )


@router.post("/conversations/{conversation_id}/context/reset", response_model=ConversationContextOut)
def reset_conversation_context(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    if conversation.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="不能修改其他用户的会话")
    context = db.get(ConversationContext, conversation_id)
    if not context:
        context = ConversationContext(conversation_id=conversation_id)
        db.add(context)
    clear_context(db, context)
    write_audit(db, user, "qa.context.reset", "conversation", conversation_id, {})
    db.commit()
    return ConversationContextOut()


@router.post("/feedback", status_code=201)
def feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    message = db.get(Message, payload.message_id)
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    conversation = db.get(Conversation, message.conversation_id)
    if not conversation or (conversation.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=403, detail="不能评价其他用户的会话")
    row = Feedback(
        message_id=payload.message_id,
        user_id=user.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(row)
    write_audit(db, user, "qa.feedback", "message", message.id, {"rating": payload.rating})
    db.commit()
    return {"id": row.id, "status": "recorded"}
