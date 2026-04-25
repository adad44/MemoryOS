# Quickstart

This guide gets MemoryOS running locally on macOS. It is written for first-time users and for AI coding agents that are being asked to launch the software.

MemoryOS has three main pieces:

- Backend: the local API at `http://127.0.0.1:8765`.
- Web UI: the browser app at `http://127.0.0.1:5173`.
- Capture tools: the Chrome extension and optional macOS daemon/menu bar app.

## Ask An Agent To Run It

If you are using an AI coding agent, point it at this repository and paste this:

```text
You are in the MemoryOS repository. Read README.md and docs/QUICKSTART.md, then run MemoryOS locally. Install the needed Python and Node dependencies, start the FastAPI backend, start the React web UI, add one test capture, build a TF-IDF index, verify search works, and tell me the local URLs. Do not delete local data unless I explicitly ask.
```

If the agent is outside the repo, include the folder path:

```text
Go to /path/to/memoryos, read README.md and docs/QUICKSTART.md, then run the local MemoryOS quickstart.
```

The agent should use separate terminals or background processes for the backend and web UI.

For a full explanation of every web UI tab and setting, read [WEB_UI_GUIDE.md](WEB_UI_GUIDE.md).

## Before You Start

You need:

- macOS 13 or newer.
- Python 3.10 or newer.
- Node.js 18 or newer.
- Chrome or another Chromium browser if you want browser capture.
- Xcode Command Line Tools if you want the native macOS daemon or menu bar app.

Install Apple developer tools if `swiftc` is missing:

```sh
xcode-select --install
```

## 1. Open The Repo

If you have not cloned it yet:

```sh
git clone <repo-url> memoryos
cd memoryos
```

If you already have it, open a terminal in the folder that contains `README.md`.

## 2. Install Python Dependencies

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r backend/requirements.txt
```

This installs the backend plus the local search dependencies. The first run uses TF-IDF search, which works without training a model.

## 3. Start The Backend

Keep this terminal open:

```sh
scripts/run_backend.sh
```

Expected URL:

```text
http://127.0.0.1:8765
```

In another terminal, check that it is alive:

```sh
curl http://127.0.0.1:8765/health
```

Expected response:

```json
{"ok":true,"api_key_enabled":false}
```

For the simplest local setup, leave `MEMORYOS_API_KEY` unset.

## 4. Start The Web UI

Open a new terminal from the repository root:

```sh
cd web
npm install
npm run dev
```

Open the URL printed by Vite. It is usually:

```text
http://127.0.0.1:5173
```

If port `5173` is already busy, Vite may choose another port such as `5174`.

## 5. Add One Test Capture

Before turning on real capture, add one fake capture so you can verify the full flow:

```sh
curl -X POST http://127.0.0.1:8765/capture/browser \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","title":"MemoryOS quickstart","content":"MemoryOS captures local context and makes it searchable with a local TF-IDF or embedding index.","timestamp":1777017600000}'
```

Open the web UI and check the Recent tab. You should see the test capture.

## 6. Build The Search Index

From the terminal:

```sh
curl -X POST http://127.0.0.1:8765/refresh-index \
  -H "Content-Type: application/json" \
  -d '{"backend":"tfidf"}'
```

Or use the web UI:

1. Open the Stats tab.
2. Click Reindex.

## 7. Search

From the terminal:

```sh
curl -X POST http://127.0.0.1:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"local searchable context","top_k":5}'
```

Or use the Search tab in the web UI.

If search returns `409`, it means the index has not been built yet. Run the Reindex step again after you have at least one capture.

## 8. Pin, Review, And Track Follow-Ups

Use the web UI to manage memories after search starts working:

- Open Search and click Pin on high-value memories you want protected.
- Open Collections to browse automatic groups like Pinned, Papers and Research, Coding and Debugging, Notes and Documents, and Career and Work.
- Open Digest for a weekly summary of captures, opened search results, pinned memories, source breakdowns, and active todos.
- Open Todo to add follow-up tasks such as `review transformer paper` or `finish debugging train.py`.

These features are local-first. They use the same SQLite database as captures and do not require a cloud account.

## 9. Label Captures The Easy Way

Open the Label tab in the web UI.

Use the filters at the top to show the group you care about, such as:

- Unlabeled captures.
- Captures from one app.
- Captures from one source, such as `browser`.

Then click:

- Keep visible: mark the whole visible group as useful.
- Noise visible: mark the whole visible group as not useful.
- Clear visible: remove labels from the visible group.

If only a few items are exceptions, select those checkboxes first. The buttons will switch to selected mode and apply only to those captures.

## 10. Enable Browser Capture

1. Keep the backend running on `http://127.0.0.1:8765`.
2. Open Chrome.
3. Go to `chrome://extensions`.
4. Enable Developer mode.
5. Click Load unpacked.
6. Select the repo's `extension/` folder.
7. Browse a normal page for about 45 seconds.
8. Check the Recent tab in the web UI.

The extension sends page title, URL, visible text, and timestamp to your local backend. It does not capture incognito tabs, obvious sensitive domains, very short pages, or common entertainment domains.

## 11. Optional: Native macOS Capture

Build the Swift daemon:

```sh
scripts/build_daemon.sh
```

Run it:

```sh
daemon/.build/memoryos-daemon
```

On first run, macOS may ask for Accessibility permission. If it does not, open System Settings, then Privacy & Security, then Accessibility, and allow the terminal app running the daemon.

Build and open the menu bar app:

```sh
scripts/build_menubar.sh
open menubar/dist/MemoryOS.app
```

The menu bar app can open the web UI, check backend status, refresh the index, and pause or resume native capture.

## 12. Manage Storage

Open the Settings tab, then use the Storage panel.

Useful defaults:

- Balanced mode keeps unprotected captures for 30 days.
- Noise captures are deleted after 24 hours.
- Clicked search results, pinned captures, and captures marked Keep are protected.
- Exact duplicates are removed during cleanup.
- The database cap defaults to 1 GB.

Recommended routine:

1. Mark useful captures as Keep from the Label tab.
2. Mark junk groups as Noise.
3. Open Settings.
4. Click Clean Up.
5. Click Clean + Reindex after large cleanups.

## 13. Optional: Start At Login

Install login startup:

```sh
scripts/install_backend_launch_agent.sh
scripts/install_daemon_launch_agent.sh
scripts/install_menubar_launch_agent.sh
```

Uninstall login startup:

```sh
scripts/uninstall_backend_launch_agent.sh
scripts/uninstall_daemon_launch_agent.sh
scripts/uninstall_menubar_launch_agent.sh
```

## Where Data Lives

Default database:

```text
~/Library/Application Support/MemoryOS/memoryos.db
```

Use a disposable test database:

```sh
MEMORYOS_DB=/tmp/memoryos.db scripts/run_backend.sh
```

If you use a custom `MEMORYOS_DB`, use the same value for the backend and daemon so they read and write the same database.

## Common Commands

Backend API docs:

```text
http://127.0.0.1:8765/docs
```

Recent captures:

```sh
curl "http://127.0.0.1:8765/recent?limit=10"
```

Stats:

```sh
curl http://127.0.0.1:8765/stats
```

Export local data:

```sh
scripts/export_memoryos.sh
```

Benchmark backend latency:

```sh
scripts/benchmark_backend.py --captures 500 --runs 20
```

## Troubleshooting

Backend port is already in use:

```sh
MEMORYOS_PORT=8766 scripts/run_backend.sh
```

Then set the web UI backend URL to `http://127.0.0.1:8766` in Settings.

Web UI port is already in use:

```sh
cd web
npm run dev -- --port 5174
```

Chrome extension records nothing:

- Confirm the backend is running.
- Confirm `MEMORYOS_API_KEY` is unset, or update the extension/backend flow before requiring a key.
- Confirm you loaded the repo's `extension/` folder as an unpacked extension.

Native capture records nothing:

- Confirm Accessibility permission is granted for the terminal or app running the daemon.
- Restart the daemon after changing macOS permissions.

Swift build fails:

- Install or refresh Xcode Command Line Tools.
- If the compiler and SDK are mismatched, select a full Xcode install or reinstall the tools.
