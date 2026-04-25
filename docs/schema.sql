PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS captures (
  id           INTEGER PRIMARY KEY,
  timestamp    DATETIME NOT NULL,
  app_name     TEXT NOT NULL,
  window_title TEXT,
  content      TEXT NOT NULL,
  source_type  TEXT NOT NULL CHECK (
    source_type IN ('accessibility', 'browser', 'file', 'screenshot')
  ),
  url          TEXT,
  file_path    TEXT,
  is_noise     INTEGER DEFAULT NULL CHECK (
    is_noise IS NULL OR is_noise IN (0, 1)
  ),
  is_pinned    INTEGER NOT NULL DEFAULT 0 CHECK (
    is_pinned IN (0, 1)
  ),
  embedding    BLOB
);

CREATE TABLE IF NOT EXISTS sessions (
  id          INTEGER PRIMARY KEY,
  app_name    TEXT NOT NULL,
  start_time  DATETIME NOT NULL,
  end_time    DATETIME,
  duration_s  INTEGER
);

CREATE TABLE IF NOT EXISTS search_clicks (
  id          INTEGER PRIMARY KEY,
  query       TEXT NOT NULL,
  capture_id  INTEGER NOT NULL,
  rank        INTEGER,
  dwell_ms    INTEGER,
  clicked_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(capture_id) REFERENCES captures(id)
);

CREATE TABLE IF NOT EXISTS todos (
  id          INTEGER PRIMARY KEY,
  title       TEXT NOT NULL,
  notes       TEXT,
  status      TEXT NOT NULL DEFAULT 'open' CHECK (
    status IN ('open', 'done')
  ),
  priority    INTEGER NOT NULL DEFAULT 2,
  due_at      DATETIME,
  source_capture_id INTEGER,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(source_capture_id) REFERENCES captures(id)
);

CREATE TABLE IF NOT EXISTS beliefs (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  topic             TEXT NOT NULL,
  belief_type       TEXT NOT NULL CHECK (
    belief_type IN ('interest', 'knowledge', 'gap', 'pattern', 'project')
  ),
  summary           TEXT NOT NULL,
  confidence        REAL NOT NULL DEFAULT 0.5 CHECK (
    confidence BETWEEN 0 AND 1
  ),
  depth             TEXT CHECK (
    depth IN ('surface', 'familiar', 'intermediate', 'deep')
  ),
  evidence          TEXT,
  first_seen        DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_updated      DATETIME DEFAULT CURRENT_TIMESTAMP,
  times_reinforced  INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_model (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  summary         TEXT NOT NULL,
  top_interests   TEXT NOT NULL,
  active_projects TEXT,
  work_rhythm     TEXT,
  knowledge_gaps  TEXT,
  raw_json        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS abstraction_runs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  finished_at     DATETIME,
  captures_read   INTEGER DEFAULT 0,
  beliefs_written INTEGER DEFAULT 0,
  beliefs_updated INTEGER DEFAULT 0,
  status          TEXT DEFAULT 'running' CHECK (
    status IN ('running', 'complete', 'failed')
  ),
  error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_captures_timestamp ON captures(timestamp);
CREATE INDEX IF NOT EXISTS idx_captures_app ON captures(app_name);
CREATE INDEX IF NOT EXISTS idx_captures_source_type ON captures(source_type);
CREATE INDEX IF NOT EXISTS idx_captures_noise ON captures(is_noise);
CREATE INDEX IF NOT EXISTS idx_captures_pinned ON captures(is_pinned);
CREATE INDEX IF NOT EXISTS idx_sessions_app ON sessions(app_name);
CREATE INDEX IF NOT EXISTS idx_search_clicks_capture ON search_clicks(capture_id);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_beliefs_topic ON beliefs(topic);
CREATE INDEX IF NOT EXISTS idx_beliefs_type ON beliefs(belief_type);
CREATE INDEX IF NOT EXISTS idx_beliefs_confidence ON beliefs(confidence DESC);
