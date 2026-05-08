# Phase 3 Search Backend

Phase 3 adds the local FastAPI service that serves MemoryOS search, stats, recent captures, browser ingest, click logging, and index refresh.

## Run

Normal users should run the full installer:

```sh
scripts/install_memoryos.sh
```

For backend-only debugging:

```sh
scripts/run_backend.sh
```

Default URL:

```text
http://127.0.0.1:8765
```

The backend intentionally binds to localhost by default.

## Endpoints

### Health

```sh
curl http://127.0.0.1:8765/health
```

### Stats

```sh
curl http://127.0.0.1:8765/stats
```

Returns capture totals, app/source breakdowns, noise-label counts, latest capture timestamp, protected capture count, total storage bytes, and whether an index artifact exists.

### Recent

```sh
curl "http://127.0.0.1:8765/recent?limit=25"
```

Optional filters:

```text
app_name=Safari
source_type=browser
```

### Refresh Index

Build or rebuild the Phase 2 search index:

```sh
curl -X POST http://127.0.0.1:8765/refresh-index \
  -H "Content-Type: application/json" \
  -d '{"backend":"tfidf"}'
```

Use the full semantic path after installing `ml/requirements.txt`:

```sh
curl -X POST http://127.0.0.1:8765/refresh-index \
  -H "Content-Type: application/json" \
  -d '{"backend":"sentence","model":"ml/models/memoryos-embedder"}'
```

### Search

```sh
curl -X POST http://127.0.0.1:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"python traceback embedding search","top_k":10}'
```

If the index has not been built yet, this returns `409` with instructions to refresh the index.

Search retrieves up to 50 candidates by default, re-ranks them with the temporal re-ranker, and returns the requested top results with index backend, candidate count, and measured latency metadata. If a trained re-ranker artifact exists, it is used; otherwise MemoryOS uses a live heuristic based on similarity, recency, and historical dwell time.

### Browser Capture

The Chrome extension posts here:

```text
POST /capture/browser
```

Request body:

```json
{
  "url": "https://example.com",
  "title": "Example",
  "content": "Visible page text...",
  "timestamp": 1777017600000
}
```

### Click Logging

The web UI uses this endpoint to collect labels for the re-ranker:

```sh
curl -X POST "http://127.0.0.1:8765/click?query=python&capture_id=1&rank=1&dwell_ms=4200"
```

Clicks are positive labels for future re-ranker training. `dwell_ms` records how long the result was visible before the user opened it.

### Open Capture

Open a captured URL or file through the local macOS `open` command:

```sh
curl -X POST http://127.0.0.1:8765/open \
  -H "Content-Type: application/json" \
  -d '{"capture_id":1}'
```

### Noise Labeling

```sh
curl -X PATCH http://127.0.0.1:8765/captures/1/noise \
  -H "Content-Type: application/json" \
  -d '{"is_noise":0}'
```

Bulk label captures:

```sh
curl -X PATCH http://127.0.0.1:8765/captures/noise/bulk \
  -H "Content-Type: application/json" \
  -d '{"capture_ids":[1,2,3],"is_noise":0}'
```

### Privacy Settings

```sh
curl http://127.0.0.1:8765/privacy
```

```sh
curl -X PUT http://127.0.0.1:8765/privacy \
  -H "Content-Type: application/json" \
  -d '{"blocked_apps":["1Password"],"blocked_domains":["bank"],"excluded_path_fragments":["/.ssh/"]}'
```

### Storage Policy and Cleanup

Inspect local storage:

```sh
curl http://127.0.0.1:8765/storage
```

Update retention and cleanup policy:

```sh
curl -X PUT http://127.0.0.1:8765/storage-policy \
  -H "Content-Type: application/json" \
  -d '{"mode":"balanced","auto_noise_enabled":true,"min_text_chars":180,"retention_days":30,"noise_retention_hours":24,"max_database_mb":1024,"keep_clicked":true,"protect_keep_labels":true,"noise_apps":["Netflix","Spotify"],"noise_domains":["netflix.com","youtube.com"]}'
```

Run cleanup:

```sh
curl -X POST http://127.0.0.1:8765/cleanup \
  -H "Content-Type: application/json" \
  -d '{"confirm":true,"rebuild_index":true}'
```

Cleanup deletes old noise, exact duplicates, old unprotected captures, and oversized logs. Clicked captures and captures marked Keep are protected by default.

### Export

```sh
curl http://127.0.0.1:8765/export
```

### Forget Captures

```sh
curl -X POST http://127.0.0.1:8765/forget \
  -H "Content-Type: application/json" \
  -d '{"from_timestamp":"2026-04-24T00:00:00Z","source_type":"browser","confirm":true}'
```

## Environment

| Variable | Default | Purpose |
| :-- | :-- | :-- |
| `MEMORYOS_HOST` | `127.0.0.1` | Bind address |
| `MEMORYOS_PORT` | `8765` | Port |
| `MEMORYOS_DB` | `~/Library/Application Support/MemoryOS/memoryos.db` | SQLite path |
| `MEMORYOS_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Web UI origins |
| `MEMORYOS_INDEX_INTERVAL_SECONDS` | `1800` | Background reindex interval while backend is running |
| `MEMORYOS_INDEX_BACKEND` | `auto` | Background index backend |
| `MEMORYOS_INDEX_MODEL` | unset | Optional sentence-transformer model path/name |

## Completion Notes

The backend is functional with the TF-IDF search fallback today. Full semantic search requires captured data plus the Phase 2 ML dependencies and trained/indexed artifacts.
