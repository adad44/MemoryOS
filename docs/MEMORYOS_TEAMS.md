# MemoryOS for Teams

MemoryOS for Teams is the planned enterprise version of MemoryOS. The product direction is to keep the local-first personal memory model, then add an organization layer that lets employees, teams, and workplace AI agents share approved context without turning MemoryOS into employee surveillance software.

The core product rule:

```text
Employees own private work memory.
Companies own shared project memory.
Policies decide what crosses the boundary.
```

## Product Positioning

MemoryOS for Teams gives every worker and every approved workplace agent durable company context. It helps teams stop losing knowledge across meetings, docs, chats, tickets, code reviews, handoffs, and daily work.

The enterprise product should be positioned as:

- A private work memory for each employee.
- A shared memory layer for projects, departments, and accounts.
- A context API for workplace agents such as Hermes Agent.
- A controlled system for onboarding, handoffs, project recall, and institutional knowledge.

It should not be positioned as raw activity monitoring. The winning enterprise version is private-first, employee-visible, admin-governed, and built around explicit sharing boundaries.

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

## MVP Scope

The first Teams MVP should be small enough to ship but strong enough to prove the enterprise model.

Recommended MVP:

- Add organization, user, team, project, and memory-share concepts.
- Add an explicit private vs shared memory state.
- Add a local-to-team sync path for approved captures.
- Add admin-managed privacy policy that can be pulled onto the local machine.
- Add a team memory page in the web UI.
- Add a Hermes Agent context endpoint for "current employee context" and "current project context".
- Add audit rows for shared, opened, exported, and deleted memory.
- Add a product-level onboarding flow that explains what stays private and what can be shared.

## Data Model Direction

The enterprise layer should extend the local model rather than replace it.

Likely entities:

- `organizations`
- `users`
- `devices`
- `teams`
- `projects`
- `team_memberships`
- `project_memberships`
- `enterprise_policies`
- `memory_shares`
- `shared_memories`
- `agent_access_grants`
- `audit_events`

The local SQLite store can remain the personal source of truth. Shared project memory can be synced to a hosted organization service or a company-controlled deployment.

## Agent API Direction

Hermes Agent should be able to ask MemoryOS for bounded context.

Useful endpoints:

- `GET /agent/context/recent`
- `POST /agent/context/search`
- `GET /agent/context/project/{project_id}`
- `GET /agent/context/team/{team_id}`
- `POST /agent/context/brief`
- `POST /agent/actions/share-request`

Agent access should always be policy-bound, auditable, and scoped to the employee, team, project, or organization role that granted it.

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
