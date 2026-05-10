# MemoryOS Enterprise Deployment

These templates package the separate MemoryOS Teams enterprise backend.

## Docker Compose

```sh
cd deploy/enterprise
docker compose up --build
```

The compose template runs the enterprise API on `http://127.0.0.1:8775` with a persistent SQLite volume. It is suitable for a self-hosted pilot.

## Render Pilot Blueprint

`render.yaml` defines the enterprise API container, a persistent `/data` disk for SQLite pilot storage, and required secrets. Set the `sync: false` values in Render before the first pilot deploy. For broad hosted SaaS, use the managed Postgres contract below after the runtime adapter is enabled and smoke-tested.

## Managed Database Contract

The backend uses SQLite by default:

```sh
MEMORYOS_ENTERPRISE_DATABASE_ENGINE=sqlite
MEMORYOS_ENTERPRISE_DB=/data/enterprise.db
```

The environment contract for managed Postgres is reserved and documented for the hosted SaaS rollout:

```sh
MEMORYOS_ENTERPRISE_DATABASE_ENGINE=postgres
MEMORYOS_ENTERPRISE_DATABASE_URL=postgresql://user:password@host:5432/memoryos
```

The current PR includes deploy templates, a durable SQLite pilot path, and the managed database configuration contract. The runtime Postgres adapter remains guarded until the query adapter layer is completed and smoke-tested against a real Postgres URL.

## Required Secrets

- `MEMORYOS_ENTERPRISE_BOOTSTRAP_TOKEN`
- `MEMORYOS_ENTERPRISE_OIDC_ISSUER`
- `MEMORYOS_ENTERPRISE_OIDC_AUDIENCE`
- `MEMORYOS_ENTERPRISE_OIDC_JWKS_URL`
- `MEMORYOS_ENTERPRISE_SCIM_TOKEN`
- `MEMORYOS_ENTERPRISE_KMS_PROVIDER`
- `MEMORYOS_ENTERPRISE_KMS_KEY_ID`
- `MEMORYOS_ENTERPRISE_LOCAL_KMS_MASTER_KEY` for local/self-hosted pilots or the equivalent cloud KMS secret wiring
- `MEMORYOS_ENTERPRISE_SEARCH_INDEX_KEY`

## Health Check

```sh
curl http://127.0.0.1:8775/health
```

The health response intentionally does not expose database URLs or secrets.
