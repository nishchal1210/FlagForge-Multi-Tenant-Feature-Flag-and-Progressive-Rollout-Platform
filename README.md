<div align="center">

# FlagForge

### Multi-Tenant Feature Flag & Progressive Rollout Platform

**Control releases centrally. Evaluate flags locally. Keep running offline.**

<p>
  <img alt="Python 3.12 tested" src="https://img.shields.io/badge/Python-3.12_tested-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white">
  <img alt="Redis" src="https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white">
  <img alt="Docker Compose" src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white">
  <img alt="Local SDK evaluation" src="https://img.shields.io/badge/SDK-local_evaluation-7C3AED?style=flat-square">
</p>

[Architecture](#architecture) · [Quick start](#quick-start) · [SDK](#python-sdk) · [Benchmarks](#benchmarks) · [Reliability](#reliability) · [Roadmap](#roadmap)

</div>

---

FlagForge separates **deploying code** from **releasing a feature**. An administrator can enable a new checkout for 15% of Indian users, increase the rollout to 30%, and propagate the change to running applications without restarting them.

**Run it locally:** Docker Compose starts the API, PostgreSQL and Redis, applies migrations, and optionally runs an SDK demonstration with a persistent cache.

The FastAPI backend manages configuration. A separate Python SDK downloads published snapshots and makes runtime decisions **inside the application's process**. Redis and SSE notify SDKs about changes; individual flag evaluations require no network access.

| Local evaluation benchmark | Measured result |
| --- | ---: |
| Mixed-workload p50, 1,000 flags | **2.6 µs** |
| Mixed-workload p99, 1,000 flags | **4.9 µs** |
| Sequential local evaluations per second | **360,495** |

Measured on an Intel Core i7-1260P with Python 3.12.4 on Windows 11. These are local SDK measurements from one recorded run, not HTTP throughput or production capacity claims. [Methodology and results ↓](#benchmarks)

## Why FlagForge?

A release should not depend on an HTTP request succeeding every time a user opens a page.

FlagForge keeps the runtime decision local while allowing configuration to change independently of application deployments:

- **Target precisely.** Combine user attributes with ordered rules and fixed or percentage outcomes.
- **Roll out consistently.** Stable hashing keeps users in the same bucket across evaluations and process restarts.
- **Publish deliberately.** Draft edits become active only when an environment is explicitly published.
- **Update live.** Redis Pub/Sub and SSE trigger configuration refreshes in running SDKs.
- **Stay available.** Last-known-good memory and disk caches preserve evaluation during outages.
- **Explain decisions.** Evaluation details include the reason, matched rule priority and rollout bucket where applicable.

## Architecture

```mermaid
flowchart TD
    Admin["Administrator / Swagger"] --> API["FastAPI backend"]
    API -->|"Commit published snapshot"| DB[("PostgreSQL")]
    API -->|"Notify after commit"| Redis[("Redis Pub/Sub")]
    Redis --> Live["Per-process subscriber + SSE"]
    Live -->|"Environment, version, checksum"| SDK["Python SDK: in-memory snapshot"]
    SDK -->|"Authenticated configuration refresh"| API
    App["Customer application"] -->|"Local flag evaluation"| SDK
    SDK <-->|"Validated last-known-good snapshot"| Disk["Disk cache"]
```

### Control plane

The backend manages the ownership hierarchy:

**Tenant → Project → Environment → Feature Flag → Targeting Rule → Condition**

PostgreSQL holds mutable drafts, published configuration versions and environment-scoped SDK credentials. Administrative queries check the ownership chain so unrelated tenant, project and environment IDs cannot be combined.

### Data plane

The application calls the Python SDK. The SDK selects a flag from its in-memory snapshot, evaluates its rules and returns a Boolean result with optional decision details.

**PostgreSQL, Redis and FastAPI are outside the per-evaluation path.**

### Configuration propagation

1. An administrator publishes an environment.
2. PostgreSQL commits a complete versioned snapshot.
3. FastAPI publishes a small notification to Redis.
4. Each FastAPI process forwards the event to its local SSE connections for that environment.
5. SDKs fetch the latest snapshot, validate it and replace their active configuration.

Each process owns its own queues. Redis distributes notifications across those process boundaries. Events carry metadata, not the full configuration; the authenticated configuration endpoint remains the download path.

## Core engineering decisions

| Concern | Implementation |
| --- | --- |
| Environment separation | Independent flags, published versions and SDK keys per environment |
| Rule ordering | Ascending priority; first matching rule wins |
| Condition composition | All conditions within a rule must match |
| Supported operators | `equals`, `not_equals`, `in`, `not_in` |
| Percentage allocation | SHA-256 bucketing over the flag ID and user key |
| Snapshot publication | Explicit publish boundary between mutable drafts and immutable API snapshots |
| Publication concurrency | Environment row lock plus a unique environment/version constraint |
| Integrity checks | SHA-256 of deterministically serialized configuration JSON |
| Conditional downloads | Checksum-based `ETag`, `If-None-Match` and `304 Not Modified` |
| SDK credentials | High-entropy environment keys; only hashes stored in PostgreSQL |
| SDK refresh concurrency | A dedicated lock serializes complete refresh operations |
| Active state access | A separate lock protects the in-memory snapshot reference and metadata |
| Cache persistence | Write a temporary file, then replace the cache before activating the new state |
| Missed notifications | Refresh on reconnect and periodic fallback polling |

### Deterministic rollout

The evaluator hashes `flag_id:user_key`, interprets the first eight SHA-256 bytes as a big-endian integer, and takes the result modulo 10,000.

```python
bucket = int.from_bytes(digest[:8], byteorder="big") % 10000
enabled = bucket < true_basis_points
```

`1500` basis points means 15%; `3000` means 30%. Increasing the threshold preserves previously enabled users when the flag ID, user key and targeting conditions remain unchanged. A percentage rule returns `False` outside its allocation; it does not continue to later rules.

### Evaluation semantics

- A disabled flag returns its **configured flag default**.
- An enabled flag checks its ordered rules and returns the first matching rule's outcome.
- No matching rule returns the configured flag default.
- Missing user attributes do not match, including for negative operators.
- An empty condition list matches every user.
- A percentage rule requires a non-empty string `user.key`.
- A missing flag returns the **caller's fallback**.

Enabling a flag makes its rules active; it does not automatically make its result `True`.

## Quick start

**The complete local stack runs with Docker Compose.** Start the backend, publish a configuration, then launch the SDK consumer to watch live updates and offline recovery.

### 1. Configure the local stack

Install and start Docker Desktop with Linux containers. From the repository root, using PowerShell:

```powershell
docker version
docker compose version
Copy-Item .env.docker.example .env.docker
```

The example environment contains local development database settings and an initially empty SDK key:

```dotenv
POSTGRES_DB=flagforge
POSTGRES_USER=flagforge
POSTGRES_PASSWORD=flagforge_local_dev
FLAGFORGE_SDK_KEY=
```

Keep `.env.docker` private. The SDK key is generated after the backend starts; it is not needed to build or start the API.

### 2. Build and start

```powershell
docker compose --env-file .env.docker up --build -d
docker compose --env-file .env.docker ps -a
```

Open **[Swagger UI on localhost:8001](http://localhost:8001/docs)**.

| Service | Role | Expected state |
| --- | --- | --- |
| `postgres` | PostgreSQL 16 with a persistent data volume | Healthy |
| `redis` | Redis 7 for update notifications | Healthy |
| `migrate` | One-shot `alembic upgrade head` | Exited with code `0` |
| `api` | FastAPI on container port `8000` | Healthy |
| `demo` | Optional SDK consumer | Starts after key configuration |

The API waits for healthy dependencies and successful migrations. Only the API is exposed to Windows, at `127.0.0.1:8001`; PostgreSQL and Redis stay on the Compose network.

**A fresh Docker volume starts with an empty database.** Migrations create the schema; they do not import records from an existing Windows PostgreSQL installation. Local and container databases remain separate.

### 3. Publish a demonstration flag

In Swagger, create these resources in order and retain their returned IDs:

| Resource | Request body |
| --- | --- |
| Tenant | `{"name": "Acme"}` |
| Project under that tenant | `{"name": "Storefront", "key": "storefront"}` |
| Environment under that project | `{"name": "Production", "key": "production"}` |
| Flag in that environment | `{"key": "reliability_test", "name": "Reliability Test", "enabled": true, "default_value": false}` |

Leave this flag without targeting rules for the initial demo. Publish its environment, then create an SDK key with `{"name": "docker-demo"}` using the environment's `/sdk-keys` endpoint.

Copy the full returned `key` into `.env.docker`. The plaintext key is displayed only when created. Use the key for the same environment you just published.

### 4. Start the SDK consumer

```powershell
docker compose --env-file .env.docker --profile demo up -d demo
docker compose --env-file .env.docker logs -f demo
```

Expected output includes:

```text
flag=reliability_test value=False reason=DEFAULT_VALUE priority=None bucket=None
```

The consumer evaluates every two seconds and polls for configuration every five seconds alongside its SSE connection. Pressing Ctrl+C exits log-following without stopping the container.

### 5. Change a release without restarting

In Swagger, patch `reliability_test`:

```json
{"default_value": true}
```

Before publication, the SDK continues reporting `False`. Publish the environment again: the running SDK adopts the snapshot and starts reporting `True`.

**That is the core demonstration: draft edit → explicit publication → live SDK update.**

## Docker operations

| Setting | Windows / host | Inside Compose |
| --- | --- | --- |
| API URL | `http://localhost:8001` | `http://api:8000` |
| Database host | Not published | `postgres:5432` |
| Redis host | Not published | `redis:6379` |
| Database storage | Named volume `flagforge_postgres_data` | `/var/lib/postgresql/data` |
| SDK cache storage | Named volume `flagforge_sdk_cache` | `/data/flagforge-production.json` |

The container demo uses `http://api:8000`. A Python SDK process running directly on Windows uses `http://localhost:8001` for the Docker-backed API. Changing the host port does not change internal container addresses.

View backend logs:

```powershell
docker compose --env-file .env.docker logs --tail 100 migrate api
```

After changing application source, rebuild:

```powershell
docker compose --env-file .env.docker --profile demo up --build -d
```

Stop the stack and remove containers while preserving database and cache volumes:

```powershell
docker compose --env-file .env.docker --profile demo down
```

Restart it with the same environment file:

```powershell
docker compose --env-file .env.docker --profile demo up -d
```

**Do not add `-v` unless you intend to delete the database and SDK-cache volumes.** PostgreSQL initialization credentials are applied when its data volume is first created; changing `.env.docker` later does not automatically change existing database users or passwords.

The API container's health check verifies that HTTP serving is available. It is not a continuous dependency-readiness check. Images contain code and dependencies; persistent application data belongs to the named volumes.

<details>
<summary><strong>Run without Docker: Python + local PostgreSQL + Redis</strong></summary>

### Install dependencies

From the repository root, using Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python -m pip install -e .\sdk
python -m pip install pytest
```

Python 3.12.4 was used for the recorded tests and benchmarks.

### Configure local services

Start PostgreSQL and create a database named `flagforge`. Create a local `.env` in the repository root:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/flagforge
REDIS_URL=redis://localhost:6379/0
```

Replace the sample database credentials with your local values. Keep `.env` and SDK secrets out of version control.

**Windows: Redis through Ubuntu / WSL**

If Ubuntu is not installed, run the following in an Administrator PowerShell terminal and complete the installation prompts. Restart Windows if requested.

```powershell
wsl --install -d Ubuntu
```

In the Ubuntu terminal:

```bash
sudo apt update
sudo apt install redis-server
sudo service redis-server start
redis-cli ping
```

The expected response is `PONG`. From Windows, verify access with the project's virtual environment active:

```powershell
python -c "from redis import Redis; print(Redis.from_url('redis://localhost:6379/0').ping())"
```

The expected response is `True`.


### Apply migrations and start FastAPI

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

Open **[Swagger UI](http://127.0.0.1:8000/docs)** to create resources and publish configurations.


This workflow uses `http://localhost:8000`, while the Docker workflow uses host port `8001`. For a Python consumer targeting the local API, set:

```powershell
$env:FLAGFORGE_BASE_URL = "http://127.0.0.1:8000"
```

</details>

## Targeted rollout example

Within your existing environment, create another Boolean flag:

```json
{
  "key": "new_checkout",
  "name": "New checkout",
  "enabled": true,
  "default_value": false
}
```

Add this rule through the flag's `/rules` endpoint:

```json
{
  "priority": 1,
  "conditions": [
    {
      "attribute": "country",
      "operator": "equals",
      "value": "IN"
    }
  ],
  "serve": {
    "type": "percentage",
    "true_basis_points": 1500
  }
}
```

Publish the environment. The SDK example below evaluates this flag for an Indian user; the result depends on that user's deterministic bucket. The container demo continues watching `reliability_test`.

## Python SDK

The SDK is an independent installable package under `sdk/`. Docker installs it in the application image. To run this example directly on Windows, install it with `python -m pip install -e .\sdk`. The example defaults to the Docker-backed API on host port `8001` and uses an environment variable for the secret:

```powershell
$env:FLAGFORGE_SDK_KEY = Read-Host "Paste the environment SDK key"
```

```python
import os

from flagforge_sdk import FlagForgeClient


client = FlagForgeClient(
    sdk_key=os.environ["FLAGFORGE_SDK_KEY"],
    base_url=os.environ.get(
        "FLAGFORGE_BASE_URL",
        "http://127.0.0.1:8001",
    ),
    cache_path="./cache/flagforge-production.json",
)

try:
    client.initialize()
    client.start_realtime(poll_interval_seconds=5.0)

    details = client.boolean_value_details(
        "new_checkout",
        user={"key": "user-123", "country": "IN"},
        default=False,
    )

    print(details.value)
    print(details.reason)
    print(details.matched_rule_priority)
    print(details.bucket)

finally:
    client.close()
```

This example evaluates once and closes. For the continuously running demonstration, configure `examples/sdk_demo.py` with your key, flag and the appropriate base URL (`8001` for the Docker API; `8000` for the local API), then run:

```powershell
python .\examples\sdk_demo.py
```

The five-second polling interval is useful for local demonstrations. The SDK's default interval is 60 seconds.

| Public method | Purpose |
| --- | --- |
| `initialize()` | Load a valid cache and attempt to fetch current configuration |
| `refresh()` | Fetch and validate a snapshot; return whether a new version was activated |
| `boolean_value()` | Return a Boolean using local configuration |
| `boolean_value_details()` | Return the value and decision metadata |
| `start_realtime()` | Start the SSE and polling threads |
| `stop_realtime()` | Signal background threads to stop and wait up to their join timeouts |
| `close()` | Stop realtime processing and close the HTTP client |

Decision reasons include `RULE_MATCH`, `PERCENTAGE_ROLLOUT`, `DEFAULT_VALUE`, `FLAG_DISABLED`, `MISSING_USER_KEY`, `FLAG_NOT_FOUND` and `CLIENT_NOT_INITIALIZED`.

## Reliability

Configuration freshness can degrade during an outage while local evaluation remains available.

| Scenario | Behavior verified during the reliability checks |
| --- | --- |
| Flag edited but not published | SDK continues using the published snapshot |
| New version published | Running SDK adopts it without restarting |
| Redis unavailable | Publication commits; polling discovers the new snapshot |
| FastAPI unavailable | Initialized SDK continues evaluating from memory |
| SDK restarted while FastAPI is down | Valid disk cache restores local evaluation |
| Invalid disk cache and no server | Initialization fails instead of accepting invalid configuration |
| SDK key revoked | Subsequent configuration downloads return `401` |

Further safeguards include checksum rejection, rejection of older versions and changed contents under an existing version, and `304` handling without replacing the active configuration. HTTP downloads occur without holding the active-state lock, allowing evaluations to use the existing snapshot during refresh.

Redis Pub/Sub is best-effort. PostgreSQL remains authoritative; polling recovers from lost notifications or a failure between database commit and event publication. Revoking a key blocks future downloads but does not erase configuration already held by an SDK.

### Reproduce the container outage checks

Start with the running demo reporting `True` from a published snapshot and follow its logs in another terminal.

| Experiment | Action | Expected result |
| --- | --- | --- |
| Missed notifications | Stop Redis, change the flag and publish | SDK adopts the change through polling |
| Server outage | Stop the API | SDK keeps evaluating from memory |
| Restart during outage | Restart the existing demo container while API remains stopped | SDK initializes from its valid persistent cache |
| Container recreation | Bring the stack down and back up without deleting volumes | Configuration, SDK keys and cached data survive |

```powershell
# Redis outage: publish a changed flag while Redis is stopped.
docker compose --env-file .env.docker stop redis
# After verifying polling recovery:
docker compose --env-file .env.docker start redis

# API outage: the initialized consumer continues evaluating.
docker compose --env-file .env.docker stop api
# Restart only the existing consumer, keeping the API offline.
docker compose --env-file .env.docker restart demo
# Restore the API after verifying disk-cache recovery.
docker compose --env-file .env.docker start api
```

These manual Docker checks have been completed alongside the earlier cache-corruption and key-revocation checks. They complement the targeted automated suite below.

### Run the automated reliability suite

```powershell
New-Item -ItemType Directory -Path ".pytest_tmp" -Force | Out-Null
python -m pytest tests/sdk tests/realtime -q --basetemp=".pytest_tmp/milestone6"
```

For local test execution, activate a virtual environment and install the project dependencies, editable SDK and `pytest` as described in the non-Docker setup.

The targeted suite has **9 passing tests** covering local evaluation without HTTP requests, conditional refresh, preservation after invalid or failed updates, disk-cache recovery, older-version rejection, missing-flag fallback, environment-specific broadcasts and disconnected queues.

`--basetemp` is dedicated test storage that pytest clears between runs. These tests use mocked HTTP responses and the in-process queue manager; they do not require running PostgreSQL, Redis or FastAPI and do not constitute a full Redis-to-SSE integration test.

## Benchmarks

### Mixed user-and-flag workload

The following run uses 1,000 synthetic users and selects different flag keys within each configuration size. It includes percentage rules, first-, third- and tenth-rule matches, default results and approximately 10% missing-flag lookups.

| Flags in snapshot | p50 | p95 | p99 | Sequential evaluations/sec |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 2.5 µs | 4.2 µs | 4.5 µs | 361,133 |
| 10 | 3.3 µs | 5.4 µs | 9.6 µs | 315,106 |
| 100 | 2.6 µs | 3.9 µs | 5.5 µs | 355,528 |
| 1,000 | **2.6 µs** | **4.1 µs** | **4.9 µs** | **360,495** |

Source: [`mixed_20261107_143320_763335/summary.csv`](benchmarks/results/mixed_20261107_143320_763335/summary.csv).

### Individual evaluation paths

The separate path benchmark repeatedly evaluates a fixed user and selected flag to characterize particular execution paths. At 1,000 flags:

| Scenario | p50 | p99 | Sequential evaluations/sec |
| --- | ---: | ---: | ---: |
| Fixed rule | 1.2 µs | 1.5 µs | 888,806 |
| Percentage rollout | 2.2 µs | 3.0 µs | 458,839 |
| Last of ten rules matches | 3.7 µs | 5.4 µs | 268,796 |

Source: [`evaluation_20261107_143305_675975/evaluation.csv`](benchmarks/results/evaluation_20261107_143305_675975/evaluation.csv).

### Methodology and scope

- **Hardware:** Intel Core i7-1260P.
- **Runtime:** Python 3.12.4, Windows 11.
- **Execution:** One process, sequential calls, no realtime threads.
- **Sampling:** 20,000 queries per repeat, three repeats and 2,000 warmup evaluations per configuration/case. Latency percentiles use 60,000 samples; throughput is the median of three separately timed batches.
- **Mixed inputs:** 1,000 generated user contexts, fixed seed `42`, and queries prepared before timing. Each repeat reuses the prepared query sequence.
- **Timed operation:** The public `FlagForgeClient.boolean_value()` call. Initialization, mock configuration download and disk persistence are excluded. Throughput includes the surrounding batch-loop overhead.
- **Instrumentation:** `perf_counter_ns()` for elapsed time. Individual-call measurements include timing overhead; throughput uses batch timing.
- **Provenance:** Commit `f00699598aa0b077263bdb712b140e262e8a01c7`, recorded on 7 November 2026. The path run recorded a clean working tree. The mixed run recorded a dirty tree; the follow-up status showed changes only to generated benchmark artifacts.
- **Limits:** These results characterize the supplied synthetic workloads. They do not measure concurrent application traffic, live-refresh contention, propagation latency or HTTP server capacity. p99 is a percentile, not a worst-case bound.

The mixed run retains per-path query counts, raw latency samples in `.csv.gz` files and environment metadata. Earlier runs are kept alongside it to show measurement variation.

### Rollout distribution and consistency

Across 100,000 synthetic Indian users and a fixed flag ID:

| Configured rollout | Observed enabled | Enabled users |
| ---: | ---: | ---: |
| 0% | 0.000% | 0 |
| 15% | 14.843% | 14,843 |
| 30% | 29.940% | 29,940 |
| 50% | 49.920% | 49,920 |
| 100% | 100.000% | 100,000 |

The checks verify boundary behavior, stable repeated evaluations, exclusion of non-targeted US users and preservation of enabled users as thresholds increase. Approximate distribution is expected; hashing does not promise an exact population quota.

Source: [`rollout_distribution.csv`](benchmarks/results/rollout_distribution.csv).

### Reproduce the measurements

No running backend services or real SDK key are needed. HTTPX `MockTransport` supplies the initial snapshot while the benchmark calls the actual SDK evaluator.

```powershell
$env:BENCHMARK_CPU = (Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)

python .\benchmarks\evaluation_benchmark.py
python .\benchmarks\mixed_workload_benchmark.py
python .\benchmarks\rollout_distribution.py
```

The evaluation and mixed scripts create timestamped result directories. The rollout script writes `benchmarks/results/rollout_distribution.csv`.

## API map

Administrative environment routes share this prefix:

```text
/api/v1/tenants/{tenant_id}/projects/{project_id}/environments/{environment_id}
```

| Method | Route suffix | Purpose |
| --- | --- | --- |
| `POST` | `/flags` | Create a Boolean flag |
| `PATCH` | `/flags/{flag_key}` | Edit a flag's draft state |
| `POST` | `/flags/{flag_key}/rules` | Add a targeting rule |
| `POST` | `/config/publish` | Publish a new environment snapshot |
| `GET` | `/config/latest` | Retrieve the latest published snapshot |
| `GET` | `/config/versions` | List publication history |
| `GET` | `/config/versions/{version}` | Retrieve a historical snapshot |
| `POST` | `/sdk-keys` | Generate an environment SDK key |
| `DELETE` | `/sdk-keys/{key_id}` | Revoke a key |

SDK routes use a separate namespace and resolve the environment from the Bearer key:

| Method | Full route | Purpose |
| --- | --- | --- |
| `GET` | `/api/sdk/v1/config` | Download the latest snapshot or receive `304` |
| `GET` | `/api/sdk/v1/config/stream` | Subscribe to SSE update notifications |

See Swagger for complete request schemas and resource-management routes. SDK keys authorize configuration access, not administrative operations.

## Project layout

| Path | Responsibility |
| --- | --- |
| `app/api/` | Administrative and SDK routes, request dependencies |
| `app/models/` | SQLAlchemy models and ownership relationships |
| `app/schemas/` | Pydantic request and response models |
| `app/services/` | Preview evaluation, snapshot compilation and update publication |
| `app/security/` | SDK-key generation and verification |
| `app/realtime/` | Environment queues and Redis subscriber |
| `app/core/`, `app/db/` | Settings, Redis clients and database sessions |
| `sdk/flagforge_sdk/` | Installable SDK client and local evaluator |
| `migrations/` | Alembic database migrations |
| `examples/sdk_demo.py` | Continuously running local SDK consumer |
| `examples/docker_demo.py` | Environment-configured container consumer with persistent cache |
| `Dockerfile`, `.dockerignore` | Application image build and build-context exclusions |
| `compose.yaml` | API, PostgreSQL, Redis, migration job and optional demo |
| `.env.docker.example` | Committable example Docker configuration |
| `tests/sdk/`, `tests/realtime/` | SDK reliability and queue-manager tests |
| `benchmarks/` | Path, mixed-workload and rollout experiments |

## Security and current boundaries

- **Administrative authentication is pending.** Ownership-chain checks validate resource relationships; they do not establish the caller's identity or tenant permissions. Keep the development administration API private.
- SDK keys are environment-scoped secrets. Plaintext keys are shown once, hashes are stored server-side, and revoked keys cannot download new configuration.
- Snapshots contain targeting data. This SDK is intended for trusted server-side applications, not distribution of secret keys to browsers.
- Snapshot checksums detect content mismatches; they are not cryptographic signatures. Use HTTPS for deployments beyond localhost.
- Snapshot immutability is enforced by the publication/API design, not a database-level write prohibition.
- Current refresh validation checks the response envelope, version and checksum. Exhaustive validation of every nested flag, rule and condition remains planned.
- Use a separate cache file for each environment. Revocation does not invalidate previously downloaded copies.

## Roadmap

- [x] Tenant, project, environment and Boolean flag management
- [x] Ordered conditions and deterministic percentage rollouts
- [x] Versioned snapshots and explicit publication
- [x] Environment-scoped SDK keys and local Python evaluation
- [x] Redis/SSE updates, polling and last-known-good recovery
- [x] Targeted reliability suite and manual outage checks
- [x] Path and mixed-workload benchmarks with recorded results
- [x] Docker Compose packaging, automatic migrations and persistent volumes
- [x] Containerized SDK demo, live updates and outage/restart checks
- [ ] CI automation and broader API/integration/concurrency coverage
- [ ] Authenticated administrative tenant authorization
- [ ] Shared, exhaustive snapshot validation for download and cache loading
- [ ] Propagation-latency and refresh-contention experiments

The scope stays focused on feature flags and progressive releases. Statistical A/B experiment analysis, automatic rollback, billing and multiple language SDKs are outside the current implementation.
