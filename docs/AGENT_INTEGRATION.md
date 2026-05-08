# Agent Integration

MemoryOS can act as a local memory layer for desktop agents. Agents should talk to the localhost FastAPI backend instead of reading the SQLite database directly.

## Install For Agents

From the repository root:

```sh
scripts/install_memoryos.sh
```

For headless agent setup:

```sh
scripts/install_memoryos.sh --no-open
```

Then verify:

```sh
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:5173
```

## Recommended Tool Surface

Expose these as agent tools:

| Tool | Endpoint | Purpose |
| :-- | :-- | :-- |
| `memoryos_search` | `POST /search` | Search local captured memory. |
| `memoryos_recent` | `GET /recent` | Inspect recent captures. |
| `memoryos_user_model` | `GET /user-model` | Read the local You model. |
| `memoryos_beliefs` | `GET /beliefs` | Read structured interests, projects, gaps, and patterns. |
| `memoryos_open` | `POST /open` | Open a captured URL or file on the Mac. |
| `memoryos_add_todo` | `POST /todos` | Add a local follow-up task. |
| `memoryos_run_abstraction` | `POST /run-abstraction` | Trigger a background user-model update. |

## Example Calls

Search:

```sh
curl -X POST http://127.0.0.1:8765/search \
  -H "Content-Type: application/json" \
  -d '{"query":"that transformer paper I read last week","top_k":5}'
```

Read the local user model:

```sh
curl http://127.0.0.1:8765/user-model
```

Open a remembered item:

```sh
curl -X POST http://127.0.0.1:8765/open \
  -H "Content-Type: application/json" \
  -d '{"capture_id":123}'
```

## Safety Defaults

- Keep MemoryOS bound to `127.0.0.1`.
- Treat `/open`, `/forget`, `/cleanup`, and delete endpoints as confirmation-required tools.
- Prefer `/search`, `/recent`, `/user-model`, `/beliefs`, and `/todos` as low-risk read/write surfaces.
- Do not expose the backend over a public network. MemoryOS is designed for localhost-first use.

## Hermes / OpenClaw Pattern

Use MemoryOS as the local retrieval and user-model backend:

```text
agent -> MemoryOS FastAPI -> SQLite/search/user model -> agent response
```

The agent can keep its own planning or note-writing system while delegating personal computer-memory recall to MemoryOS.
