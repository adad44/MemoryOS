from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import load_settings


SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS organizations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  sso_issuer TEXT,
  sso_audience TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_id INTEGER NOT NULL,
  subject TEXT NOT NULL,
  email TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',
  status TEXT NOT NULL DEFAULT 'active',
  last_seen_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(organization_id, subject),
  FOREIGN KEY(organization_id) REFERENCES organizations(id)
);

CREATE TABLE IF NOT EXISTS devices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  device_name TEXT NOT NULL,
  trust_state TEXT NOT NULL DEFAULT 'pending',
  public_key_hash TEXT,
  policy_version INTEGER NOT NULL DEFAULT 0,
  last_seen_at DATETIME,
  registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(organization_id) REFERENCES organizations(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS teams (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(organization_id) REFERENCES organizations(id)
);

CREATE TABLE IF NOT EXISTS team_memberships (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',
  UNIQUE(team_id, user_id),
  FOREIGN KEY(team_id) REFERENCES teams(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS project_memberships (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',
  UNIQUE(project_id, user_id),
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_id INTEGER NOT NULL,
  version INTEGER NOT NULL,
  capture_sources TEXT NOT NULL,
  blocked_apps TEXT NOT NULL,
  blocked_domains TEXT NOT NULL,
  excluded_path_fragments TEXT NOT NULL,
  redaction_terms TEXT NOT NULL,
  retention_days INTEGER NOT NULL DEFAULT 90,
  sync_enabled INTEGER NOT NULL DEFAULT 1,
  require_explicit_share INTEGER NOT NULL DEFAULT 1,
  published_by_user_id INTEGER,
  published_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(organization_id, version),
  FOREIGN KEY(organization_id) REFERENCES organizations(id),
  FOREIGN KEY(published_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS shared_memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_id INTEGER NOT NULL,
  local_capture_id INTEGER,
  team_id INTEGER,
  project_id INTEGER,
  shared_by_user_id INTEGER NOT NULL,
  policy_version INTEGER NOT NULL,
  share_state TEXT NOT NULL DEFAULT 'shared',
  source_hash TEXT NOT NULL,
  title TEXT,
  summary TEXT NOT NULL,
  redacted_content TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at DATETIME,
  FOREIGN KEY(organization_id) REFERENCES organizations(id),
  FOREIGN KEY(team_id) REFERENCES teams(id),
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(shared_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS memory_sync_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_id INTEGER NOT NULL,
  shared_memory_id INTEGER,
  device_id INTEGER,
  event_type TEXT NOT NULL,
  status TEXT NOT NULL,
  details TEXT NOT NULL DEFAULT '{}',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(organization_id) REFERENCES organizations(id),
  FOREIGN KEY(shared_memory_id) REFERENCES shared_memories(id),
  FOREIGN KEY(device_id) REFERENCES devices(id)
);

CREATE TABLE IF NOT EXISTS agent_access_grants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_id INTEGER NOT NULL,
  agent_name TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  team_id INTEGER,
  project_id INTEGER,
  can_read_shared INTEGER NOT NULL DEFAULT 1,
  can_request_private INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',
  created_by_user_id INTEGER,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used_at DATETIME,
  FOREIGN KEY(organization_id) REFERENCES organizations(id),
  FOREIGN KEY(team_id) REFERENCES teams(id),
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(created_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_id INTEGER,
  actor_user_id INTEGER,
  actor_type TEXT NOT NULL DEFAULT 'user',
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  ip_address TEXT,
  details TEXT NOT NULL DEFAULT '{}',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(organization_id) REFERENCES organizations(id),
  FOREIGN KEY(actor_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_devices_org ON devices(organization_id);
CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(organization_id);
CREATE INDEX IF NOT EXISTS idx_projects_team ON projects(team_id);
CREATE INDEX IF NOT EXISTS idx_shared_memories_org ON shared_memories(organization_id);
CREATE INDEX IF NOT EXISTS idx_shared_memories_project ON shared_memories(project_id);
CREATE INDEX IF NOT EXISTS idx_sync_events_org ON memory_sync_events(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_org_time ON audit_events(organization_id, created_at DESC);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    db_url = path or load_settings().database_url
    db_path = Path(db_url).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn

