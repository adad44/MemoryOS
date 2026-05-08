# Phase 4 Web Interface

Phase 4 adds a React/Vite/Tailwind web UI for the local MemoryOS backend.

## Run

Normal users should run the full installer:

```sh
scripts/install_memoryos.sh
```

For web UI debugging, start the backend:

```sh
scripts/run_backend.sh
```

Start the web app:

```sh
cd web
npm install
npm run dev
```

Default URL:

```text
http://127.0.0.1:5173
```

## Views

### Search

- Debounced semantic search.
- Result cards with title, app, source, relative timestamp, snippet, similarity/rerank scores, and label state.
- Search metadata shows index backend, candidate count, re-ranker mode, and measured latency.
- Open action sends the capture to the local backend so macOS can open URLs and file paths directly.
- Click logging through `POST /click`, including result dwell time for re-ranker training.

### Recent

- Latest captures from `GET /recent`.
- App and source filters.

### Label

- Batch keep/noise/manual clear controls for visible or selected captures.
- Filters by label state, app, and source.
- Uses `PATCH /captures/{id}/noise`.
- Uses `PATCH /captures/noise/bulk` for batch review.

### Stats

- Capture totals.
- Index availability.
- App/source breakdowns.
- Keep/noise/unlabeled counts.
- Index refresh through `POST /refresh-index`.

### Settings

- Backend URL.
- Backend health check.
- Privacy blocklists.
- Storage dashboard with database, index, log, and total usage.
- Retention mode, noise rules, database cap, and protected-capture controls.
- One-click cleanup and cleanup-plus-reindex actions.
- JSON export.
- Filtered forget/delete controls.

## Environment

| Variable | Default | Purpose |
| :-- | :-- | :-- |
| `VITE_API_URL` | `http://127.0.0.1:8765` | Backend URL |

The UI stores the backend URL in browser local storage.

## Completion Notes

The app is built as an operator console for collecting and improving real data. It intentionally includes labeling and index refresh controls because those are needed before the ML models become useful.
