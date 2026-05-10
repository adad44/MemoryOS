from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Principal(BaseModel):
    organization_id: int
    user_id: int
    subject: str
    email: str
    name: str
    role: str


class EnterprisePolicy(BaseModel):
    version: int = 1
    capture_sources: list[str] = Field(default_factory=lambda: ["meetings", "docs", "tickets", "browser", "github", "local_files"])
    blocked_apps: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    excluded_path_fragments: list[str] = Field(default_factory=list)
    redaction_terms: list[str] = Field(default_factory=lambda: ["password", "secret", "token", "api key"])
    retention_days: int = Field(default=90, ge=1, le=3650)
    sync_enabled: bool = True
    require_explicit_share: bool = True
    published_at: Optional[str] = None


class BootstrapRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=160)
    organization_slug: str = Field(min_length=1, max_length=80)
    owner_email: str = Field(min_length=3, max_length=254)
    owner_name: str = Field(min_length=1, max_length=120)
    owner_subject: str = Field(default="bootstrap-owner", min_length=1, max_length=240)
    sso_issuer: Optional[str] = None
    sso_audience: Optional[str] = None


class BootstrapResponse(BaseModel):
    organization_id: int
    owner_user_id: int
    policy: EnterprisePolicy


class OverviewResponse(BaseModel):
    principal: Principal
    organization: dict[str, Any]
    policy: EnterprisePolicy
    users: list[dict[str, Any]]
    devices: list[dict[str, Any]]
    teams: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    shared_memory_count: int
    audit_event_count: int


class TeamRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=500)


class UserRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=240)
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="member", pattern="^(member|manager|admin|owner|auditor)$")
    status: Literal["active", "suspended"] = "active"


class ProjectRequest(BaseModel):
    team_id: int
    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=500)


class MembershipRequest(BaseModel):
    user_id: int
    role: str = Field(default="member", pattern="^(member|manager|admin|owner|auditor)$")


class DeviceRequest(BaseModel):
    device_name: str = Field(min_length=1, max_length=180)
    public_key: Optional[str] = Field(default=None, max_length=4000)
    trust_state: Literal["pending", "trusted", "revoked"] = "pending"


class DeviceTrustRequest(BaseModel):
    trust_state: Literal["pending", "trusted", "revoked"]


class ShareMemoryRequest(BaseModel):
    local_capture_id: int
    device_id: int
    content: str = Field(min_length=1, max_length=100000)
    team_id: Optional[int] = None
    project_id: Optional[int] = None
    title: Optional[str] = Field(default=None, max_length=300)
    summary: Optional[str] = Field(default=None, max_length=2000)
    app_name: Optional[str] = Field(default=None, max_length=180)
    window_title: Optional[str] = Field(default=None, max_length=300)
    source_type: Optional[str] = Field(default=None, max_length=80)
    url: Optional[str] = Field(default=None, max_length=2000)
    file_path: Optional[str] = Field(default=None, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_scope(self) -> "ShareMemoryRequest":
        if self.team_id is None and self.project_id is None:
            raise ValueError("Team memory sync requires a team_id or project_id.")
        return self


class SharedMemory(BaseModel):
    id: int
    local_capture_id: Optional[int]
    team_id: Optional[int]
    project_id: Optional[int]
    shared_by_user_id: int
    policy_version: int
    share_state: str
    title: Optional[str]
    summary: str
    redacted_content: str
    metadata: dict[str, Any]
    created_at: str


class AgentGrantRequest(BaseModel):
    agent_name: str = Field(default="Hermes Agent", min_length=1, max_length=120)
    token: str = Field(min_length=24, max_length=500)
    team_id: Optional[int] = None
    project_id: Optional[int] = None
    can_request_private: bool = False

    @model_validator(mode="after")
    def require_scope(self) -> "AgentGrantRequest":
        if self.team_id is None and self.project_id is None:
            raise ValueError("Agent grants require a team_id or project_id.")
        return self


class AgentContextRequest(BaseModel):
    query: Optional[str] = Field(default=None, max_length=1000)
    team_id: Optional[int] = None
    project_id: Optional[int] = None
    include_private_recent: bool = False
    limit: int = Field(default=8, ge=1, le=50)


class AgentContextResponse(BaseModel):
    agent_name: str
    shared_memories: list[SharedMemory]
    private_recent: list[dict[str, Any]]
    policy_version: int
    audit_event_id: int


class AuditExport(BaseModel):
    exported_at: str
    count: int
    events: list[dict[str, Any]]
