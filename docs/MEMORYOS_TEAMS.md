# MemoryOS Teams Enterprise

MemoryOS Teams Enterprise is the separate enterprise product surface for MemoryOS. It keeps the local-first personal memory model, then adds an organization layer that lets employees, teams, and workplace AI agents share approved context without turning MemoryOS into employee surveillance software.

The core product rule:

```text
Employees own private work memory.
Companies own shared project memory.
Policies decide what crosses the boundary.
```

## Current Status

MemoryOS Teams now has a separate enterprise backend under `enterprise/backend`. It is not mixed into the personal localhost MemoryOS app. Enterprises can self-host this backend and configure SSO/JWT validation, SCIM provisioning, RBAC, admin policy sync, team memory sync, audit exports, envelope encryption, and Hermes Agent enterprise access.

Operator setup notes live in [enterprise/README.md](../enterprise/README.md).
The end-to-end verification script is `scripts/smoke_enterprise_backend.py`.

Implemented now:

- Separate FastAPI enterprise backend.
- SSO/OIDC hooks through JWKS-backed JWT validation or HS256 JWT validation for controlled deployments.
- SCIM 2.0 user and group provisioning endpoints.
- Browser admin console at `/admin/console`.
- Bootstrap token for first organization setup.
- Organization, user, device, team, project, membership, policy, shared-memory, sync-event, agent-grant, and audit-event tables.
- Provisioned-user RBAC for member, manager, admin, auditor, and owner roles; token role claims do not override stored enterprise roles.
- Membership-aware access controls for team/project shared memory.
- Admin policy publishing with versioned policies.
- Device policy sync that renders local `privacy.json` and storage policy shapes.
- Team memory sync from employee-side approved capture payloads into redacted shared memory.
- Scoped Hermes Agent grants and `/agent/context` access that cannot read outside the grant's team/project scope or read private local memory.
- Optional envelope encryption for shared-memory payloads and blind search terms for encrypted retrieval.
- JSONL and CSV audit exports.
- Docker Compose and Render deployment templates under `deploy/enterprise`.

Required production configuration:

- `MEMORYOS_ENTERPRISE_ENABLED=true`
- SQLite DB path through `MEMORYOS_ENTERPRISE_DB`, or managed database contract through `MEMORYOS_ENTERPRISE_DATABASE_ENGINE` and `MEMORYOS_ENTERPRISE_DATABASE_URL`
- OIDC issuer, audience, and JWKS URL, or a deployment-managed HS256 JWT secret
- SCIM token for identity-provider provisioning
- KMS provider/key configuration and search index HMAC key when encryption is enabled; local KMS is smoke-tested, AWS KMS has provider hooks and still needs cloud credential smoke before production use
- Bootstrap token for first organization setup
- TLS, reverse proxy, secret storage, backup policy, monitoring, and deployment hardening supplied by the enterprise environment

## Product Positioning

MemoryOS Teams gives every worker and every approved workplace agent durable company context. It helps teams stop losing knowledge across meetings, docs, chats, tickets, code reviews, handoffs, and daily work.

The enterprise product should be positioned as:

- A private work memory for each employee.
- A shared memory layer for projects, departments, and accounts.
- A context API for workplace agents such as Hermes Agent.
- A controlled system for onboarding, handoffs, project recall, and institutional knowledge.

It should not be positioned as raw activity monitoring. The winning enterprise version is private-first, employee-visible, admin-governed, and built around explicit sharing boundaries.

## Pipeline Checklist

The enterprise pipeline works in this order:

1. **Personal MemoryOS stays local**: each employee keeps a private local memory on their work machine.
2. **Enterprise policy service**: admins define approved capture sources, exclusions, retention, redaction, sharing, and sync rules.
3. **Identity and access**: provisioned organization, employee, team, project, role, and device state control access.
4. **Team memory sync**: the employee-side sync worker posts selected or policy-approved captures into shared project memory.
5. **Hermes Agent connector**: approved agents request bounded context by team or project through scoped grants.
6. **Admin control plane**: companies manage policies, teams, shared memories, device trust, audit logs, retention, and access reviews through the enterprise API, with browser-console coverage for overview, policy, devices, SCIM status, and audit export.
7. **Enterprise security**: encryption, redaction, SSO, device trust, export/delete controls, and audit trails make the system acceptable for real organizations.

Every step must preserve the product rule: employees own private work memory, companies own shared project memory, and policies decide what crosses the boundary.

## Enterprise Sequence

### 1. Company setup

The company installs MemoryOS Enterprise across approved work machines.

Admins configure:

- Organization identity and SSO.
- Employee groups, teams, projects, and departments.
- Approved capture sources such as meetings, docs, tickets, chats, browser research, GitHub, Jira, Linear, and local files.
- Apps, domains, folders, and data types that must never be captured.
- Retention policies for private memory and shared project memory.
- Role-based access for managers, teammates, auditors, and agents.
- Audit logging, export, deletion, and compliance rules.

### 2. Employee onboarding

Each employee signs in with their work account. MemoryOS creates:

- A private local work memory on the employee's machine.
- Membership in the correct teams and projects.
- A list of shared memories the employee can query.
- Agent permissions for tools such as Hermes Agent.
- A visible capture history so the employee can see what is being remembered.

The employee can pause capture, review captures, mark noise, keep important memories, and understand which items are private or shareable.

### 3. Daily work capture

MemoryOS captures approved work context from the employee's normal workflow:

- Meeting notes and transcripts.
- Slack or Teams decisions.
- Docs, sheets, and presentations.
- GitHub issues, PRs, commits, and code review discussion.
- Jira, Linear, support tickets, and customer notes.
- Browser research, internal wiki pages, and local files.
- Follow-ups, blockers, commitments, and open questions.

Sensitive apps, excluded domains, excluded folders, private content, and blocked data patterns are filtered before anything becomes searchable or shareable.

### 4. Personal agent sync

Hermes Agent or another approved desktop agent can query the employee's local MemoryOS context.

Example employee prompts:

- What did I miss yesterday?
- Summarize my blockers.
- Prep me for my 2 PM client meeting.
- What did we decide about pricing?
- Draft a reply using the latest project context.
- What should I work on next?

The agent starts from the employee's real work context instead of a blank prompt.

### 5. Team memory formation

MemoryOS promotes approved context from private local memory into shared project memory.

Shared memory can include:

- Product decisions from meetings.
- Customer requirements from sales or support.
- Design constraints from Figma or review notes.
- Deployment issues from engineering.
- Legal, finance, or security constraints.
- Unresolved blockers and owners.
- Final decisions and the evidence behind them.

Private notes and employee-only captures stay private unless the employee shares them or the company policy explicitly allows that class of content to be shared.

### 6. Peer catch-up

Team members query shared project memory instead of interrupting peers for status.

Example team prompts:

- What changed on the Acme account this week?
- Why did engineering delay the release?
- What did design decide about onboarding?
- What objections did sales hear from enterprise customers?
- What does support know about this bug?
- Who owns the current launch blockers?

The product reduces repeated meetings, repeated status messages, and stale project docs.

### 7. Cross-team coordination

Managers, project leads, and executives can query high-level shared memory without reading every raw capture.

Example leadership prompts:

- What are the open launch risks?
- Which teams are waiting on legal?
- What decisions were made but not documented?
- Which enterprise deals are blocked?
- Where are teams duplicating work?
- Which projects lost context during handoff?

Leadership gets summarized operational context while raw private employee memory remains protected.

### 8. New employee ramp-up

A new employee joins a team and receives a guided memory brief:

- Project history.
- Current goals.
- Key decisions.
- Important people.
- Open risks.
- Recent meetings.
- Relevant docs.
- Active tickets.
- Customer context.

Their Hermes Agent can also answer follow-up questions from approved team memory, making onboarding faster and less dependent on interrupting senior teammates.

### 9. Handoff and continuity

When someone goes on vacation, switches teams, or leaves the company, approved shared context remains available.

The company keeps:

- Why decisions were made.
- What customers asked for.
- Which blockers existed.
- What was promised.
- What work was half-finished.
- Which docs, tickets, and people mattered.

This is one of the strongest enterprise use cases: MemoryOS protects company continuity without requiring every employee to manually document every detail.

### 10. Executive and compliance layer

Enterprise admins and compliance teams need controls that make the system acceptable in real organizations:

- Audit trails.
- Access logs.
- Retention and deletion controls.
- Redaction rules.
- Permission history.
- Source-level capture policy.
- Export controls.
- Employee-visible capture and sharing history.

Executives should see summarized business memory. Compliance should see policy and audit evidence. Employees should see and control their own private memory.

## Implemented Foundation

The enterprise foundation gives enterprises a deployable control plane and API surface while preserving the separate personal MemoryOS app.

Included:

- Organization, user, team, project, membership, and device concepts.
- Private local memory stays in the personal MemoryOS DB.
- Shared team memory is stored separately as redacted `shared_memories`.
- Admin-managed policy publishing and device policy sync.
- SCIM user and group provisioning.
- Browser admin console for overview, policy, users, teams, device trust, SCIM status, and audit export.
- Optional envelope encryption and blind search for shared memory.
- Hermes Agent context endpoint for scoped team/project context.
- Audit rows for bootstrap, user provisioning, policy publish, device registration, team/project creation, memory share, agent grant, agent context read, and audit export.

Still recommended next:

- SAML/OIDC provider mapping templates for Okta, Microsoft Entra, and Google Workspace.
- Cloud KMS deployment smoke tests and provider templates beyond the current local/AWS provider hooks.
- Runtime Postgres adapter for hosted multi-org deployments.

## Data Model Direction

The enterprise layer extends the local model instead of replacing it.

Implemented entities:

- `organizations`
- `users`
- `devices`
- `teams`
- `projects`
- `team_memberships`
- `project_memberships`
- `policies`
- `shared_memories`
- `memory_sync_events`
- `agent_access_grants`
- `audit_events`

The local SQLite store can remain the personal source of truth. Shared project memory can be synced to a hosted organization service or a company-controlled deployment.

## Agent API Direction

Hermes Agent can ask MemoryOS Teams for bounded context through scoped grants.

Useful endpoints:

- `POST /agent/context`
- `POST /admin/agent-grants`

Agent access is policy-bound, auditable, and scoped to the team/project grant created by an admin.

## Enterprise Backend Endpoints

- `POST /bootstrap`
- `GET /auth/me`
- `GET /admin/overview`
- `GET /admin/console`
- `GET /admin/scim/status`
- `GET /admin/policy`
- `PUT /admin/policy`
- `POST /admin/users`
- `POST /admin/teams`
- `POST /admin/teams/{team_id}/members`
- `POST /admin/projects`
- `POST /sync/devices`
- `GET /sync/policy`
- `POST /sync/share`
- `GET /sync/shared`
- `POST /admin/agent-grants`
- `POST /agent/context`
- `GET /audit/events`
- `GET /audit/export`
- `GET /scim/v2/ServiceProviderConfig`
- `GET /scim/v2/Users`
- `POST /scim/v2/Users`
- `PATCH /scim/v2/Users/{user_id}`
- `DELETE /scim/v2/Users/{user_id}`
- `GET /scim/v2/Groups`
- `POST /scim/v2/Groups`

## Privacy and Trust Requirements

MemoryOS for Teams only works if employees trust it and companies can govern it.

Required controls:

- Capture pause and source visibility.
- Employee-visible local history.
- Private memory by default.
- Explicit share state for team memory.
- App, domain, folder, and file-type exclusions.
- Sensitive data redaction before sharing.
- Role-based access control.
- Audit logs for shared memory and agent reads.
- Retention policies per organization, project, and source.
- Export and delete workflows.
- Clear separation between raw personal captures and summarized shared memory.

## Long-Term Outcome

The end state is a local-first enterprise memory network:

- Every employee has a private work memory.
- Every team has shared project memory.
- Every approved agent has current context.
- Every handoff preserves what matters.
- Every new employee can ramp faster.
- Every project keeps decision history instead of losing it across tools.

MemoryOS becomes the memory layer for humans and workplace agents.
