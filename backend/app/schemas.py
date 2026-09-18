from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(ORMModel):
    id: int
    username: str
    display_name: str
    role: str
    active: bool
    locked_until: datetime | None = None
    last_login_at: datetime | None = None


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]{2,64}$")
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["viewer", "engineer", "reviewer", "admin"] = "engineer"


class UserStatusUpdate(BaseModel):
    active: bool


class SeriesOut(ORMModel):
    id: int
    code: str
    name: str
    description: str
    manufacturer: str
    source_url: str
    source_title: str
    data_classification: str


class MachineOut(ORMModel):
    id: int
    code: str
    name: str
    model_version: str
    specs: dict[str, Any]
    source_url: str
    source_title: str
    status: str
    data_classification: str
    series: SeriesOut | None = None


class AlarmOut(ORMModel):
    id: int
    code: str
    title: str
    severity: str
    system: str
    applies_to: list
    symptoms: list
    possible_causes: list
    checks: list
    actions: list
    stop_conditions: list
    source_title: str
    source_url: str | None
    source_section: str
    knowledge_version: str
    review_status: str
    data_classification: str


class PartOut(ORMModel):
    id: int
    part_no: str
    name: str
    category: str
    applies_to: list
    replaces: list
    key_specs: dict
    verification_notes: list
    source_title: str
    source_url: str | None
    review_status: str
    data_classification: str


class CaseOut(ORMModel):
    id: int
    case_no: str
    title: str
    model_code: str
    alarm_code: str | None
    symptom: str
    root_cause: str
    resolution: str
    verification: str
    risk_level: str
    review_status: str
    data_classification: str


class DocumentOut(ORMModel):
    id: int
    title: str
    filename: str
    doc_type: str
    version: str
    model_codes: list
    source_url: str | None
    source_kind: str
    review_status: str
    parse_status: str
    parse_message: str | None
    uploaded_by: int
    reviewed_by: int | None
    reviewed_at: datetime | None
    created_at: datetime


class ReviewRequest(BaseModel):
    status: Literal["approved", "published", "rejected", "deprecated"]
    note: str | None = Field(default=None, max_length=1000)


class KnowledgeOut(ORMModel):
    id: int
    title: str
    item_type: str
    content: str
    applies_to: list
    source_title: str
    source_url: str | None
    source_section: str | None
    version: str
    confidence: float
    review_status: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    data_classification: str


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    model_code: str | None = Field(default=None, max_length=64)
    serial_number: str | None = Field(default=None, max_length=80)
    conversation_id: int | None = None


class Citation(BaseModel):
    title: str
    source_type: str
    source_url: str | None = None
    section: str | None = None
    version: str | None = None
    model_codes: list[str] = Field(default_factory=list)
    data_classification: str


class RelationPath(BaseModel):
    path: list[str] = Field(min_length=2)
    relation: str
    source_title: str
    source_url: str | None = None
    source_section: str | None = None
    data_classification: str


class ConversationContextOut(BaseModel):
    model_code: str | None = None
    serial_number: str | None = None
    alarm_code: str | None = None
    symptom: str | None = None
    completed_checks: list[str] = Field(default_factory=list)
    latest_feedback: str | None = None
    status: str = "collecting_information"
    inherited_fields: list[str] = Field(default_factory=list)
    history_turns_used: int = 0


class AskResponse(BaseModel):
    conversation_id: int
    message_id: int
    answer: str
    confidence: float
    requires_engineer_confirmation: bool = True
    missing_information: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    relation_paths: list[RelationPath] = Field(default_factory=list)
    graph_notice: str | None = None
    context: ConversationContextOut
    context_notice: str | None = None


class FeedbackCreate(BaseModel):
    message_id: int
    rating: int = Field(ge=-1, le=1)
    comment: str | None = Field(default=None, max_length=1000)


class GraphCoverageOut(BaseModel):
    available: bool = False
    subsystems: int = 0
    models: int = 0
    alarms: int = 0
    parts: int = 0
    cases: int = 0


class DashboardOut(BaseModel):
    products: int
    published_documents: int
    pending_reviews: int
    published_alarms: int
    cases: int
    questions_7d: int
    graph_coverage: GraphCoverageOut = Field(default_factory=GraphCoverageOut)


class AuditOut(ORMModel):
    id: int
    username: str
    action: str
    target_type: str
    target_id: str | None
    detail: dict
    created_at: datetime
