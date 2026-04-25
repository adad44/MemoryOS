# MemoryOS

MemoryOS is a local-first memory and search system for your computer. It captures useful context from browser pages, active macOS windows, and local files, stores that data in SQLite on your Mac, and lets you search it later through a local web app.

The short version: run MemoryOS locally, collect a small amount of context, build a search index, then use the web UI to search, pin, review, label, track follow-ups, export, or delete your data.

## Who This Is For

- People who want searchable personal work history without sending captures to a hosted service.
- Developers who want a local FastAPI, React, Swift, and ML project to build on.
- Students or portfolio builders who want a complete local-first AI systems project.
- Anyone using an AI coding agent who wants the agent to launch and operate the repo for them.

## What You Get

- Local FastAPI backend for capture ingest, search, stats, smart collections, weekly digest, todos, privacy settings, export, and delete.
- React web UI for search, recent captures, pinned memories, smart collections, weekly digest, todos, batch labeling, stats, and settings.
- Chrome extension for browser-page capture.
- Swift macOS daemon for native window/file context capture.
- Swift menu bar app for status, opening the UI, refreshing the index, and pausing capture.
- TF-IDF search that works immediately, plus hooks for sentence-transformer and FAISS indexing.
- Storage controls for retention, auto-noise rules, cleanup, and protected useful captures.

## Quick Start

The full beginner-friendly setup guide is here:

[docs/QUICKSTART.md](docs/QUICKSTART.md)

For a tab-by-tab explanation of the web app, see:

[docs/WEB_UI_GUIDE.md](docs/WEB_UI_GUIDE.md)

Fast path if you already know the tooling:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r backend/requirements.txt
scripts/run_backend.sh
```

In a second terminal:

```sh
cd web
npm install
npm run dev
```

Open the web UI:

```text
http://127.0.0.1:5173
```

## Use It With An AI Coding Agent

If you use Codex, Claude Code, Cursor, or another coding agent, point the agent at this repository and ask it to run the quickstart for you.

Copy this prompt:

```text
You are in the MemoryOS repository. Read README.md and docs/QUICKSTART.md, then run MemoryOS locally. Install the needed Python and Node dependencies, start the FastAPI backend, start the React web UI, add one test capture, build a TF-IDF index, verify search works, and tell me the local URLs. Do not delete local data unless I explicitly ask.
```

If the agent is not already inside the repo, give it the path first:

```text
Go to /path/to/memoryos, read README.md and docs/QUICKSTART.md, then run the local MemoryOS quickstart.
```

For this local checkout, the path is usually the folder that contains this README.

## Everyday Workflow

1. Start the backend with `scripts/run_backend.sh`.
2. Start the web UI with `cd web && npm run dev`.
3. Add captures through the Chrome extension, the macOS daemon, or a test API call.
4. Open the Stats tab and click Reindex.
5. Search from the Search tab.
6. Pin high-value results from Search.
7. Review Collections and Digest to see what MemoryOS thinks matters.
8. Add follow-ups in Todo.
9. Use the Label tab to batch-mark visible captures as Keep or Noise.
10. Use Settings to manage privacy lists, storage policy, export JSON, or delete filtered captures.

## Storage Management

MemoryOS is local-first, so storage matters. The web Settings tab includes a Storage panel with:

- Database, index, log, and total disk usage.
- Retention modes: Light, Balanced, Deep memory, and Archive.
- Automatic cleanup for noise, old unprotected captures, exact duplicates, large databases, and oversized logs.
- Protected captures: clicked search results, pinned rows, and user-marked Keep rows are preserved by default.

The default Balanced policy keeps useful captures for 30 days, deletes noise after 24 hours, protects clicked/pinned/kept memories, and caps the database at 1 GB.

## Privacy Model

MemoryOS is designed to run on your Mac. By default:

- The backend binds to `127.0.0.1`.
- Captures are stored in a local SQLite database.
- The web UI talks to the local backend.
- The Chrome extension posts to the local backend.
- You can export or delete captured data from the UI.

Default database path:

```text
~/Library/Application Support/MemoryOS/memoryos.db
```

Use a disposable database while testing:

```sh
MEMORYOS_DB=/tmp/memoryos.db scripts/run_backend.sh
```

The prototype is unsigned. The menu bar app includes local permission onboarding for Accessibility, Full Disk Access review, and Screen Recording fallback setup. If you distribute it outside local development, you should add app signing and notarization.

## Project Structure

```text
memoryos/
├── backend/         # FastAPI search, capture, stats, privacy, export, delete
├── web/             # React UI for search, review, labeling, stats, settings
├── extension/       # Chrome extension for browser capture
├── daemon/          # Swift background capture process
├── menubar/         # Swift menu bar app
├── ml/              # Search/indexing and model training code
├── docs/            # Setup, architecture, deployment, phase notes
├── scripts/         # Build, run, install, benchmark, export helpers
└── config/          # Example privacy configuration
```

## Main Commands

Run backend:

```sh
scripts/run_backend.sh
```

Run web UI:

```sh
cd web
npm run dev
```

Build native daemon:

```sh
scripts/build_daemon.sh
```

Run native daemon:

```sh
daemon/.build/memoryos-daemon
```

Build and open menu bar app:

```sh
scripts/build_menubar.sh
open menubar/dist/MemoryOS.app
```

Build search index:

```sh
curl -X POST http://127.0.0.1:8765/refresh-index \
  -H "Content-Type: application/json" \
  -d '{"backend":"tfidf"}'
```

Search:

```sh
curl -X POST http://127.0.0.1:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"local searchable context","top_k":10}'
```

## Current Status

All planned prototype phases are implemented for local development:

| Phase | Name | Status |
| :-- | :-- | :-- |
| 0 | Setup & Architecture | Complete |
| 1 | Data Capture Layer | Baseline implemented |
| 2 | ML Pipeline | Code complete; needs captured/labeled data |
| 3 | Search Backend | Complete |
| 4 | Web Interface | Complete |
| 5 | Mac Menu Bar App | Complete |
| 6 | Polish & Deploy | Complete |

Remaining real-world work includes training production models on real labeled data, app signing/notarization, and additional permission onboarding.

## More Documentation

- [Quickstart](docs/QUICKSTART.md)
- [Web UI guide](docs/WEB_UI_GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Demo script](docs/DEMO_SCRIPT.md)
- [SQLite schema](docs/schema.sql)
- [Phase 1 notes](docs/PHASE1.md)
- [Phase 2 notes](docs/PHASE2.md)
- [Phase 3 notes](docs/PHASE3.md)
- [Phase 4 notes](docs/PHASE4.md)
- [Phase 5 notes](docs/PHASE5.md)
- [Phase 6 notes](docs/PHASE6.md)
