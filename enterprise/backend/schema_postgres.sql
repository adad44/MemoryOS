CREATE TABLE IF NOT EXISTS organizations (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  sso_issuer TEXT,
  sso_audience TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  organization_id BIGINT NOT NULL REFERENCES organizations(id),
  subject TEXT NOT NULL,
  external_id TEXT,
  email TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',
  status TEXT NOT NULL DEFAULT 'active',
  last_seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(organization_id, subject)
);

CREATE TABLE IF NOT EXISTS devices (
  id BIGSERIAL PRIMARY KEY,
  organization_id BIGINT NOT NULL REFERENCES organizations(id),
  user_id BIGINT NOT NULL REFERENCES users(id),
  device_name TEXT NOT NULL,
  trust_state TEXT NOT NULL DEFAULT 'pending',
  public_key_hash TEXT,
  policy_version INTEGER NOT NULL DEFAULT 0,
  last_seen_at TIMESTAMPTZ,
  registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS teams (
  id BIGSERIAL PRIMARY KEY,
  organization_id BIGINT NOT NULL REFERENCES organizations(id),
  external_id TEXT,
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS team_memberships (
  id BIGSERIAL PRIMARY KEY,
  team_id BIGINT NOT NULL REFERENCES teams(id),
  user_id BIGINT NOT NULL REFERENCES users(id),
  role TEXT NOT NULL DEFAULT 'member',
  UNIQUE(team_id, user_id)
);

CREATE TABLE IF NOT EXISTS projects (
  id BIGSERIAL PRIMARY KEY,
  team_id BIGINT NOT NULL REFERENCES teams(id),
  name TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_memberships (
  id BIGSERIAL PRIMARY KEY,
  project_id BIGINT NOT NULL REFERENCES projects(id),
  user_id BIGINT NOT NULL REFERENCES users(id),
  role TEXT NOT NULL DEFAULT 'member',
  UNIQUE(project_id, user_id)
);

CREATE TABLE IF NOT EXISTS policies (
  id BIGSERIAL PRIMARY KEY,
  organization_id BIGINT NOT NULL REFERENCES organizations(id),
  version INTEGER NOT NULL,
  capture_sources JSONB NOT NULL,
  blocked_apps JSONB NOT NULL,
  blocked_domains JSONB NOT NULL,
  excluded_path_fragments JSONB NOT NULL,
  redaction_terms JSONB NOT NULL,
  retention_days INTEGER NOT NULL DEFAULT 90,
  sync_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  require_explicit_share BOOLEAN NOT NULL DEFAULT TRUE,
  published_by_user_id BIGINT REFERENCES users(id),
  published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(organization_id, version)
);

CREATE TABLE IF NOT EXISTS shared_memories (
  id BIGSERIAL PRIMARY KEY,
  organization_id BIGINT NOT NULL REFERENCES organizations(id),
  local_capture_id BIGINT,
  team_id BIGINT REFERENCES teams(id),
  project_id BIGINT REFERENCES projects(id),
  shared_by_user_id BIGINT NOT NULL REFERENCES users(id),
  policy_version INTEGER NOT NULL,
  share_state TEXT NOT NULL DEFAULT 'shared',
  source_hash TEXT NOT NULL,
  title TEXT,
  summary TEXT NOT NULL,
  redacted_content TEXT NOT NULL,
  redacted_content_ciphertext TEXT,
  redacted_content_nonce TEXT,
  encrypted_dek TEXT,
  dek_nonce TEXT,
  kms_key_id TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at TIMESTAMPTZ,
  CHECK (team_id IS NOT NULL OR project_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS shared_memory_search_terms (
  id BIGSERIAL PRIMARY KEY,
  shared_memory_id BIGINT NOT NULL REFERENCES shared_memories(id),
  term_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(shared_memory_id, term_hash)
);

CREATE TABLE IF NOT EXISTS memory_sync_events (
  id BIGSERIAL PRIMARY KEY,
  organization_id BIGINT NOT NULL REFERENCES organizations(id),
  shared_memory_id BIGINT REFERENCES shared_memories(id),
  device_id BIGINT REFERENCES devices(id),
  event_type TEXT NOT NULL,
  status TEXT NOT NULL,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_access_grants (
  id BIGSERIAL PRIMARY KEY,
  organization_id BIGINT NOT NULL REFERENCES organizations(id),
  agent_name TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  team_id BIGINT REFERENCES teams(id),
  project_id BIGINT REFERENCES projects(id),
  can_read_shared BOOLEAN NOT NULL DEFAULT TRUE,
  can_request_private BOOLEAN NOT NULL DEFAULT FALSE,
  status TEXT NOT NULL DEFAULT 'active',
  created_by_user_id BIGINT REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_used_at TIMESTAMPTZ,
  CHECK (team_id IS NOT NULL OR project_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS audit_events (
  id BIGSERIAL PRIMARY KEY,
  organization_id BIGINT REFERENCES organizations(id),
  actor_user_id BIGINT REFERENCES users(id),
  actor_type TEXT NOT NULL DEFAULT 'user',
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  ip_address TEXT,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(organization_id);
CREATE INDEX IF NOT EXISTS idx_shared_memories_org ON shared_memories(organization_id);
CREATE INDEX IF NOT EXISTS idx_shared_search_term ON shared_memory_search_terms(term_hash);
CREATE INDEX IF NOT EXISTS idx_audit_org_time ON audit_events(organization_id, created_at DESC);
