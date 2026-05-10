# MemoryOS Teams Enterprise Backend

This folder contains the separate enterprise backend for MemoryOS Teams. It is intentionally outside the personal local MemoryOS backend so companies can run organization policy, SSO, shared memory, audit, and Hermes Agent access without changing the private local MemoryOS app.

## What It Provides

- OIDC/JWKS or deployment-managed HS256 JWT validation.
- SCIM 2.0 user and group provisioning endpoints.
- Organization, user, device, team, project, membership, policy, shared memory, agent grant, and audit tables.
- RBAC for member, manager, admin, auditor, and owner roles.
- Browser admin console at `/admin/console`.
- Admin policy publishing and device policy sync.
- Team memory sync from employee-side approved capture payloads into redacted shared memory.
- Scoped Hermes Agent enterprise grants through `/agent/context`.
- Audit events and JSONL/CSV exports.
- Optional envelope encryption for shared-memory payloads plus blind search terms for encrypted retrieval.

## Production Configuration

Set these environment variables before starting the service:

```sh
export MEMORYOS_ENTERPRISE_ENABLED=true
export MEMORYOS_ENTERPRISE_DB=/var/lib/memoryos-enterprise/enterprise.db
export MEMORYOS_ENTERPRISE_BOOTSTRAP_TOKEN="replace-with-bootstrap-secret"
export MEMORYOS_ENTERPRISE_OIDC_ISSUER="https://issuer.example.com"
export MEMORYOS_ENTERPRISE_OIDC_AUDIENCE="memoryos-enterprise"
export MEMORYOS_ENTERPRISE_OIDC_JWKS_URL="https://issuer.example.com/.well-known/jwks.json"
export MEMORYOS_ENTERPRISE_SCIM_TOKEN="replace-with-scim-secret"
export MEMORYOS_ENTERPRISE_SCIM_ORG="acme"
export MEMORYOS_ENTERPRISE_ENCRYPTION_ENABLED=true
export MEMORYOS_ENTERPRISE_KMS_PROVIDER=local
export MEMORYOS_ENTERPRISE_LOCAL_KMS_MASTER_KEY="replace-with-32-byte-base64-or-secret-manager-value"
export MEMORYOS_ENTERPRISE_KMS_KEY_ID="memoryos-enterprise-production"
export MEMORYOS_ENTERPRISE_SEARCH_INDEX_KEY="replace-with-random-search-hmac-key"
```

For controlled local pilots, `MEMORYOS_ENTERPRISE_JWT_HS256_SECRET` can be used instead of `MEMORYOS_ENTERPRISE_OIDC_JWKS_URL`. Production deployments should prefer the enterprise IdP's JWKS endpoint and store secrets in the deployment platform or company secret manager. For managed KMS, set `MEMORYOS_ENTERPRISE_KMS_PROVIDER=aws`, `MEMORYOS_ENTERPRISE_KMS_KEY_ID` to the AWS KMS key ARN, and optionally `MEMORYOS_ENTERPRISE_KMS_REGION`.

The service should run behind enterprise TLS, reverse proxy controls, backup policy, log retention, monitoring, and a managed secret store. The current backend stores data in SQLite; hosted multi-org deployments should add a Postgres adapter before broad SaaS rollout.

## Run

```sh
scripts/run_enterprise_backend.sh
```

Default URL:

```text
http://127.0.0.1:8775
```

Admin console:

```text
http://127.0.0.1:8775/admin/console
```

## Smoke Test

Run the end-to-end enterprise pipeline against disposable databases:

```sh
.venv/bin/python scripts/smoke_enterprise_backend.py
```

The smoke test verifies health, admin console rendering, SCIM service metadata, SCIM user provisioning, blocked pre-bootstrap SSO access, bootstrap, SSO/JWT role mapping from provisioned users, RBAC denial for auditor policy writes, device ownership checks, policy sync, team/project memory sharing, redaction, envelope encryption at rest, encrypted search through Hermes Agent, non-member team-read denial, member team-read approval, scoped Hermes Agent access, scoped-grant denial, private-memory denial, and audit export.

## Bootstrap

Use the bootstrap token once to create the first organization and owner:

```sh
curl -X POST http://127.0.0.1:8775/bootstrap \
  -H "Authorization: Bearer $MEMORYOS_ENTERPRISE_BOOTSTRAP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "organization_name": "Acme",
    "organization_slug": "acme",
    "owner_email": "owner@acme.com",
    "owner_name": "Acme Owner",
    "owner_subject": "owner-subject"
  }'
```

After bootstrap, admins provision enterprise users through `/admin/users`, then users authenticate with SSO/JWT bearer tokens. The backend uses token claims only to identify the organization and subject, then loads the stored enterprise role from the provisioned user row:

- `sub`: required stable user subject.
- `email` or `upn`: required user email.
- `name`: optional display name.
- `memoryos_org`, `org`, or `hd`: organization slug.
- Role claims are not trusted as authorization by default; provisioned server-side user roles decide access.

## Core Flow

1. Admin provisions users with `/admin/users`.
2. Admin publishes a policy with `/admin/policy`.
3. Employee devices call `/sync/devices` and `/sync/policy`.
4. Employee-side sync workers post approved capture payloads through `/sync/share`; the enterprise service validates device ownership/trust, redacts, stores, and audits the shared memory.
5. Teammates read allowed shared memory through `/sync/shared`.
6. Admins create scoped Hermes Agent grants with `/admin/agent-grants`.
7. Hermes Agent reads bounded enterprise context through `/agent/context`.
8. Auditors export evidence through `/audit/export?format=jsonl` or `/audit/export?format=csv`.

## Trust Boundary

Personal MemoryOS remains local and employee-visible. The enterprise backend only receives approved capture payloads posted by the employee-side sync worker; it does not read private local SQLite databases directly. Shared memories are redacted before they are stored in the enterprise database, and every share, agent read, policy publish, and audit export is recorded in `audit_events`.
