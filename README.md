# MemoryOS

MemoryOS is a local-first memory and search system for your computer. It captures useful context from browser pages, active macOS windows, and local files, stores that data in SQLite on your Mac, and lets you search it later through a local web app.

The short version: run MemoryOS locally, collect a small amount of context, build a search index, then use the web UI to search, pin, review, label, track follow-ups, export, or delete your data.

## Who This Is For

- People who want searchable personal work history without sending captures to a hosted service.
- Developers who want a local FastAPI, React, Swift, and ML project to build on.
- Students or portfolio builders who want a complete local-first AI systems project.
- Anyone using an AI coding agent who wants the agent to launch and operate the repo for them.

## What You Get

- Local FastAPI backend for capture ingest, search, stats, smart collections, weekly digest, todos, local user model, privacy settings, export, and delete.
- React web UI for search, recent captures, pinned memories, smart collections, weekly digest, todos, the You user-model tab, batch labeling, stats, and settings.
- Chrome extension for browser-page capture.
- Swift macOS daemon for native window/file context capture.
- Swift menu bar app for status, opening the UI, refreshing the index, and pausing capture.
- TF-IDF search that works immediately, plus hooks for sentence-transformer and FAISS indexing.
- Storage controls for retention, auto-noise rules, cleanup, and protected useful captures.

## Quick Start

From a fresh Mac, use the public installer:

```sh
curl -fsSL https://memoryos-mac.netlify.app/install.sh | bash
```

On Linux, the same public installer installs the backend and web UI under
`~/.local/share/memoryos` and uses `systemd --user` when available:

```sh
curl -fsSL https://memoryos-mac.netlify.app/install.sh | bash
```

From an existing checkout, use the repo-local installer:

```sh
scripts/install_memoryos.sh
```

From an existing Linux checkout, use:

```sh
scripts/install_memoryos_linux.sh
```

The macOS installer copies app files to `~/Library/Application Support/MemoryOS/app`, creates the Python virtual environment, installs backend and web dependencies, builds the React UI, installs/starts Ollama, pulls the local `mistral` model if needed, builds the Swift daemon/menu bar app, registers launch agents, starts MemoryOS on login, and opens the web UI.

The Linux installer installs the FastAPI backend, React web UI, Linux capture
agent, optional Ollama model, and optional user systemd services. The Linux
agent polls watched folders and uses `xdotool` for X11 active-window title
capture when available. The Swift daemon and menu bar app are macOS-only.

The default install uses the lightweight TF-IDF search runtime. Install the heavier sentence-transformer/FAISS extras only if you want embedding search or model training:

```sh
scripts/install_memoryos.sh --with-embeddings
```

Fast install without the local LLM download:

```sh
scripts/install_memoryos.sh --skip-model-pull
```

The full beginner-friendly setup guide is here:

[docs/QUICKSTART.md](docs/QUICKSTART.md)

For a tab-by-tab explanation of the web app, see:

[docs/WEB_UI_GUIDE.md](docs/WEB_UI_GUIDE.md)

Manual backend path if you are debugging individual pieces:

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

1. Run `scripts/install_memoryos.sh` once, or use the public `curl ... | bash` installer.
2. Grant Accessibility and Full Disk Access when prompted.
3. Open the web UI at `http://127.0.0.1:5173`.
4. Add captures through the Chrome extension, the macOS daemon, or a test API call.
5. Open the Stats tab and click Reindex.
6. Use the web UI to search your history, label captures, and view your personal memory stats.
7. Open You to inspect the local user model when Ollama is running.
8. Use Settings to manage privacy lists, storage policy, export JSON, or delete filtered captures.

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

The local app bundle is currently unsigned. The menu bar app includes local permission onboarding for Accessibility, Full Disk Access review, and Screen Recording fallback setup. If you distribute it outside local development, add app signing and notarization.

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

Run backend manually:

```sh
scripts/run_backend.sh
```

Run web UI manually:

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

Run Linux capture agent:

```sh
.venv/bin/python scripts/linux_capture_agent.py
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