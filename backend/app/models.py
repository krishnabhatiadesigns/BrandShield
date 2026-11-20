"""Typed request/response models. These drive the OpenAPI docs at /docs."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Role = Literal["creator", "manager", "approver", "admin"]
ContentType = Literal["social", "ad", "email", "document"]
Severity = Literal["low", "medium", "high"]
EvidenceStatus = Literal["supported", "contradicted", "unsupported", "needs_verification"]
Decision = Literal["pending", "accepted", "edited", "rejected"]


# --- session ---------------------------------------------------------------
class DemoSessionRequest(BaseModel):
    role: Literal["creator", "manager", "approver"] = Field(
        description="Which demo persona to enter as."
    )


class SessionResponse(BaseModel):
    token: str
    role: Role
    display_name: str
    workspace_id: int
    workspace_name: str


class WorkspaceMemberOut(BaseModel):
    user_id: str
    email: str | None
    display_name: str
    role: Role
    is_active: bool
    created_at: str


class MemberInviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=120)
    role: Role

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("display_name")
    @classmethod
    def non_blank_display_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Display name cannot be blank.")
        return value.strip()


class MemberUpdateRequest(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    brand_name: str | None = Field(default=None, min_length=2, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("name", "display_name")
    @classmethod
    def normalized_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field cannot be blank.")
        return value.strip()

    @field_validator("brand_name")
    @classmethod
    def normalized_brand_name(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class OrganizationCreateResponse(BaseModel):
    organization_id: int
    organization_name: str
    workspace_id: int
    workspace_name: str
    role: Role


class WorkspaceOut(BaseModel):
    id: int
    name: str
    role: Role
    organization_id: int
    organization_name: str


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Brand name cannot be blank.")
        return value.strip()


class MeResponse(BaseModel):
    user_id: str
    display_name: str
    role: Role
    workspace_id: int
    workspace_name: str
    is_demo: bool
    llm_enabled: bool


# --- content ---------------------------------------------------------------
class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content_type: ContentType
    body: str = Field(min_length=1, max_length=20000)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("The title cannot be blank.")
        return value.strip()

    @field_validator("body")
    @classmethod
    def body_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("The draft cannot be blank.")
        return value


class SampleInfo(BaseModel):
    key: str
    title: str
    content_type: ContentType
    body: str


class FindingOut(BaseModel):
    id: int
    category: str
    severity: Severity
    span_start: int | None
    span_end: int | None
    affected_text: str
    rule: str
    explanation: str
    source_passage_id: int | None
    source_rule_id: int | None = None
    source_rule_version: int | None = None
    source_rule_title: str | None = None
    source_rule_text: str | None = None
    source_quote: str | None = None
    source_title: str | None = None
    evidence_status: EvidenceStatus
    confidence: float
    suggestion: str | None
    creator_decision: Decision
    edited_text: str | None
    detector: str


class VersionOut(BaseModel):
    id: int
    version_no: int
    body: str
    status: str
    review_state: str
    created_at: str
    created_by: str


class ReviewRunOut(BaseModel):
    llm_status: str
    llm_message: str
    deterministic_count: int
    llm_count: int
    duration_ms: int


class ContentDetail(BaseModel):
    id: int
    title: str
    content_type: ContentType
    status: str
    created_by: str
    created_at: str
    updated_at: str
    source_filename: str | None = None
    current_version: VersionOut | None
    findings: list[FindingOut]
    review_run: ReviewRunOut | None
    comments: list["CommentOut"]
    approvals: list["ApprovalOut"]


class ContentSummary(BaseModel):
    id: int
    title: str
    content_type: ContentType
    status: str
    created_by: str
    updated_at: str
    version_no: int
    open_high: int
    needs_verification: int


class FindingDecisionRequest(BaseModel):
    decision: Literal["accepted", "edited", "rejected", "pending"]
    edited_text: str | None = Field(
        default=None, description="Required when decision is 'edited'."
    )


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def body_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A comment cannot be blank.")
        return value.strip()


class CommentOut(BaseModel):
    id: int
    author: str
    body: str
    created_at: str


class DraftEditRequest(BaseModel):
    """A reviewer editing the draft text directly.

    This always creates a NEW version and resets review state, so any prior
    approval for the previous version is invalidated.
    """

    body: str = Field(min_length=1, max_length=20000)
    note: str | None = Field(default=None, max_length=500)


class ApprovalRequest(BaseModel):
    decision: Literal["approved", "changes_requested", "rejected"]
    reason: str | None = Field(default=None, max_length=2000)
    high_severity_signoff: bool = False


class SendBackRequest(BaseModel):
    """Send a version back one level. The note is mandatory."""

    note: str = Field(min_length=1, max_length=2000)


class ApprovalOut(BaseModel):
    id: int
    version_id: int
    decision: str
    reason: str | None
    reviewer: str
    high_severity_signoff: bool
    created_at: str


class AuditEventOut(BaseModel):
    id: int
    actor: str
    action: str
    entity_type: str
    entity_id: int | None
    detail: str | None
    created_at: str


# --- brand profile ---------------------------------------------------------
class PassageOut(BaseModel):
    id: int
    source: str
    section: str | None
    page: int | None
    text: str


class TermOut(BaseModel):
    id: int
    term: str
    kind: str
    replacement: str | None
    notes: str | None


class FactOut(BaseModel):
    id: int
    fact_key: str
    value: str
    unit: str | None
    source_passage_id: int | None


class PaletteOut(BaseModel):
    id: int
    name: str
    hex: str
    role: str | None


RuleCategory = Literal[
    "tone", "messaging", "claim", "terminology", "fact", "disclaimer",
    "visual", "logo", "typography", "other",
]


class GuidelineRuleOut(BaseModel):
    id: int
    category: RuleCategory
    title: str
    description: str
    good_example: str | None
    bad_example: str | None
    severity: Severity
    mandatory: bool
    content_types: list[ContentType]
    source_passage_id: int | None
    enabled: bool
    version: int
    effective_date: str


class GuidelineRuleCreate(BaseModel):
    category: RuleCategory
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    good_example: str | None = Field(default=None, max_length=1000)
    bad_example: str | None = Field(default=None, max_length=1000)
    severity: Severity = "medium"
    mandatory: bool = True
    content_types: list[ContentType] = Field(
        default_factory=lambda: ["social", "ad", "email", "document"], min_length=1
    )
    source_passage_id: int | None = None
    enabled: bool = True
    effective_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("title", "description")
    @classmethod
    def rule_text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field cannot be blank.")
        return value.strip()

    @field_validator("content_types")
    @classmethod
    def content_types_must_be_unique(cls, value: list[ContentType]) -> list[ContentType]:
        if len(set(value)) != len(value):
            raise ValueError("Content types cannot be repeated.")
        return value


class GuidelineRuleUpdate(BaseModel):
    category: RuleCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    good_example: str | None = Field(default=None, max_length=1000)
    bad_example: str | None = Field(default=None, max_length=1000)
    severity: Severity | None = None
    mandatory: bool | None = None
    content_types: list[ContentType] | None = Field(default=None, min_length=1)
    source_passage_id: int | None = None
    enabled: bool | None = None
    effective_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("title", "description")
    @classmethod
    def updated_rule_text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None:
            if not value.strip():
                raise ValueError("This field cannot be blank.")
            return value.strip()
        return value

    @field_validator("content_types")
    @classmethod
    def updated_content_types_must_be_unique(
        cls, value: list[ContentType] | None
    ) -> list[ContentType] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("Content types cannot be repeated.")
        return value


class BrandProfile(BaseModel):
    workspace_id: int
    workspace_name: str
    company_context: str
    passages: list[PassageOut]
    terms: list[TermOut]
    facts: list[FactOut]
    palette: list[PaletteOut]
    rules: list[GuidelineRuleOut] = Field(default_factory=list)
    disclaimers: dict[str, str | None]


class CompanyContextUpdate(BaseModel):
    company_context: str = Field(max_length=10000)


class TermCreate(BaseModel):
    term: str = Field(min_length=1, max_length=120)
    kind: Literal["approved", "prohibited"]
    replacement: str | None = None
    notes: str | None = None


class FactCreate(BaseModel):
    fact_key: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=200)
    unit: str | None = None


class PassageCreate(BaseModel):
    source: str = Field(min_length=1, max_length=200)
    section: str | None = None
    text: str = Field(min_length=1, max_length=4000)


class PaletteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    role: str | None = None


# --- visual ----------------------------------------------------------------
class VisualCheckRequest(BaseModel):
    hex_colors: list[str] = Field(default_factory=list, max_length=12)
    text_hex: str | None = None
    background_hex: str | None = None


class VisualIssue(BaseModel):
    category: str
    severity: Severity
    rule: str
    explanation: str
    affected_text: str
    suggestion: str | None = None


class VisualCheckResponse(BaseModel):
    issues: list[VisualIssue]
    contrast_ratio: float | None = None
    palette_match: list[dict] = Field(default_factory=list)


class ImageVisualCheckResponse(VisualCheckResponse):
    image: dict
    limitations: list[str] = Field(default_factory=list)


class ReviewAssignmentUpdate(BaseModel):
    assignee_user_id: str | None = None
    assignee_name: str | None = Field(default=None, max_length=120)
    due_at: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}[T ].*$")


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[Literal["read", "submit", "review"]] = Field(
        default_factory=lambda: ["read"],
        min_length=1,
    )


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=8, max_length=2000)
    secret: str = Field(min_length=16, max_length=200)
    events: list[str] = Field(default_factory=lambda: ["*"], min_length=1)


ContentDetail.model_rebuild()
