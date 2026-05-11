# Deployment

MemoryOS is local-first. The intended deployment runs all services on the user's Mac.

For a first local run, use the end-to-end [Quickstart](QUICKSTART.md).

## Recommended Install

Fresh Mac:

```sh
curl -fsSL https://memoryos-mac.netlify.app/install.sh | bash
```

Existing checkout:

```sh
scripts/install_memoryos.sh
```

The installer builds the backend, web UI, Swift daemon, compact menu bar app, local user-model scheduler, and launch agents.

## Local Services

Use these commands only when debugging individual services.

Backend:

```sh
scripts/run_backend.sh
```

Web UI:

```sh
cd web
npm install
npm run dev
```

Daemon:

```sh
scripts/build_daemon.sh
daemon/.build/memoryos-daemon
```

Menu bar app:

```sh
scripts/build_menubar.sh
open menubar/dist/MemoryOS.app
```

## Login Startup

The main installer registers launch agents automatically. These lower-level commands are available for targeted debugging.

Install daemon:

```sh
scripts/install_daemon_launch_agent.sh
```

Install backend:

```sh
scripts/install_backend_launch_agent.sh
```

Install menu bar app:

```sh
scripts/install_menubar_launch_agent.sh
```

Install web UI:

```sh
scripts/install_web_launch_agent.sh
```

Install local user-model scheduler:

```sh
scripts/install_scheduler_launch_agent.sh
```

Uninstall:

```sh
scripts/uninstall_daemon_launch_agent.sh
scripts/uninstall_backend_launch_agent.sh
scripts/uninstall_menubar_launch_agent.sh
```

## Web Hosting

The web UI can be deployed as a static Vite app, but it still talks to the local backend.

Build:

```sh
cd web
npm run build
```

Output:

```text
web/dist/
```

Set `VITE_API_URL` if the backend URL differs:

```sh
VITE_API_URL=http://127.0.0.1:8765 npm run build
```

## Enterprise Teams Backend

MemoryOS Teams Enterprise is deployed separately from the personal local MemoryOS app.

Deployment templates live in:

```text
deploy/enterprise/
```

Included:

- Dockerfile for the enterprise API.
- Docker Compose pilot stack with persistent enterprise data volume.
- Render blueprint with required secret placeholders.
- Environment example for SSO, SCIM, envelope encryption, KMS, and CORS.
- Postgres schema contract in `enterprise/backend/schema_postgres.sql`.

Local pilot:

```sh
cd deploy/enterprise
docker compose up --build
```

Enterprise API health:

```sh
curl http://127.0.0.1:8775/health
```

Admin console:

```text
http://127.0.0.1:8775/admin/console
```

The current runtime adapter is SQLite-first. `MEMORYOS_ENTERPRISE_DATABASE_ENGINE=postgres` and `MEMORYOS_ENTERPRISE_DATABASE_URL` are reserved for the hosted managed-Postgres rollout; the Postgres schema and deployment contract are present, but the runtime adapter should only be enabled after a Postgres smoke test is added.

## Distribution Notes

For local development, the unsigned app bundle is enough. For broader distribution:

- Add a proper Xcode project or package workflow.
- Sign the menu bar app.
- Notarize the app bundle.
- Provide a permissions onboarding flow for Accessibility and Screen Recording.
