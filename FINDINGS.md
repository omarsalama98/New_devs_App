# Revenue Dashboard Findings

## Summary

**Main finding:** the dashboard never read Postgres. Several faults on the connection path fell into a catch-all that returned hardcoded numbers to any tenant, and the reported symptoms sat on top of that.

| Symptom | Root cause | Fix | Proof |
|---|---|---|---|
| Sunset's March totals don't match | Mock data left out `res-tz-1` (1,250.00). Month bounds also used UTC, so that booking fell in February | Real database path, month bounds in the property's time zone | Beach House Alpha is 2,250.00 with 4 bookings. Sunset's March is 13,326.00, not 12,076.00 |
| Ocean sees another company's revenue | Cache key had no tenant, mock data ignored the tenant, property list was hardcoded | Tenant in the cache key, tenant-scoped `GET /api/v1/properties`, the same 404 for other tenants' properties | Correct figures in both call orders. Each client lists only its own three properties |
| Totals a few cents off | `float()` on the server, then `Math.round` in the browser | Round half-up with `Decimal` on the server | `2250.555` now returns `2250.56`, using a temporary test row. No seeded total shows this bug |

All 40 backend regression tests pass against the running stack. Some of them insert temporary rows, which are removed afterwards.

**Branch:** `fix/revenue-dashboard`, one commit per fix group.

## How the bugs were found

1. Logged in as both clients and compared the dashboard, the API and direct database queries. Both clients saw identical figures, and `prop-001` was 1,250.00 short.
2. Read the backend logs, which showed `Database error` on every uncached request and only one tenant being calculated per cache key.
3. Followed one request through `dashboard.py`, `cache.py`, `reservations.py` and `database_pool.py`.
4. Tested the cache by clearing it and calling in both orders. Only the first caller's tenant was ever calculated.
5. Compared March in UTC and in property time with SQL, which isolated `res-tz-1`.

Root-cause line numbers below refer to the starter commit, `d1835ec5d`.

## Bugs and fixes

### Real data: commit `c1e9d8b47`

| Root cause | Where | Fix |
|---|---|---|
| `sqlalchemy>=2.0.0` resolves to 2.1.8, which doesn't install `greenlet` | `backend/requirements.txt:21` | `sqlalchemy[asyncio]>=2.0.0` |
| The pool read `settings.supabase_db_*`, which don't exist | `backend/app/core/database_pool.py:18` | Use `settings.database_url` with the asyncpg driver |
| `QueuePool` is rejected by the async engine | `backend/app/core/database_pool.py:22` | Removed |
| `get_session` was `async def` but used with `async with` | `backend/app/core/database_pool.py:48` | Plain `def` |
| A new pool was created on every call | `backend/app/services/reservations.py:43` | Shared `db_pool` |
| A catch-all returned mock figures, which were then cached | `backend/app/services/reservations.py:88` | Removed. A database failure returns 503 and nothing is cached |
| The UI error state was never cleared | `frontend/src/components/RevenueSummary.tsx:36` | Cleared when a fetch starts |

**Proof:** real totals for every property of both clients. With the `db` container stopped, the API returned 503 with no figures, and it recovered once `db` was back. The error-state fix was checked by hand in the browser, and only after the fix.

### Tenant isolation: commit `9ac60963d`

| Root cause | Where | Fix |
|---|---|---|
| The cache key had no tenant | `backend/app/services/cache.py:13` | `revenue:{tenant_id}:{property_id}` |
| The hardcoded list showed all five properties to everyone and mislabelled Ocean's `prop-001` | `frontend/src/components/Dashboard.tsx:4` | Loaded from `GET /api/v1/properties` |
| Unknown users fell through to `tenant-a` | `backend/app/core/tenant_resolver.py:92` | Returns `None` |
| A user with no tenant carried on as `default_tenant` | `backend/app/api/v1/dashboard.py:14` | Returns 403 |

**Proof:** tests cover both call orders, the tenant in the Redis key, each client's list, identical 404 bodies, `X-Simulated-Tenant` being ignored, and 403 for a signed token with an unknown email. Browser check as Ocean.

### March in property time: commit `02f8b18e6`

| Root cause | Where | Fix |
|---|---|---|
| The monthly function used UTC bounds, had no tenant argument, always returned 0 and had no callers | `backend/app/services/reservations.py:5` | Real query using `AT TIME ZONE` on each property's time zone |
| The summary route took no period | `backend/app/api/v1/dashboard.py:8` | Optional `month` and `year`, with the period in the cache key, plus a month picker |

**Proof:** `prop-001` is 2,250.00 for March and 0.00 for February. A temporary row at 03:00 UTC on 1 April in a New York property counts as March. Browser check as Sunset.

### Cents: commit `71826c475`

| Root cause | Where | Fix |
|---|---|---|
| Money went through `float`, then the browser rounded the binary value | `backend/app/api/v1/dashboard.py:18`, `frontend/src/components/RevenueSummary.tsx:64` | `Decimal.quantize` half-up on the server. No frontend change, because the browser's rounding never changes a value already in cents (8 million values tested) |

**Proof:** temporary rows turn `2250.555` into `2250.56` and `1.005` into `1.01`.

### Session lost on reload: commit `1f03868f5`

| Root cause | Where | Fix |
|---|---|---|
| A storage migration's allowlist only kept Supabase keys, so it deleted `base360-auth-token`. The second reload after login logged the user out | `frontend/src/utils/localStorageManager.ts:242` | Keep that key |

**Proof:** reproduced in the browser before the fix, and three reloads stayed logged in after it. There's no automated test, because the frontend has no test setup.

### Fake trend and stale responses: commit `23816e216`

| Root cause | Where | Fix |
|---|---|---|
| A hardcoded "12%" sat beside the total | `frontend/src/components/RevenueSummary.tsx:83` | Month-over-month calculation on the server. "No prior data" when the earlier month has no revenue, and no badge for all time |
| A slow response could overwrite the current property | `frontend/src/components/RevenueSummary.tsx:24` | Stale responses are ignored |

**Proof:** tests cover null, -100.0, +100.0, -25.0, 0.0 and the December to January boundary. In the browser, March shows "No prior data" and April shows a red -100.0%. The green and neutral badges weren't seen in a browser, only their API values. The stale-response fix was checked by hand with a delayed response, and has no automated test.

## Checked and ruled out

- **`supabase_url is required` in the log:** it comes from a different pool, logged once at startup, and doesn't affect revenue.
- **Authentication:** no token, a garbage token and a wrong-secret token all return 401.
- **`X-Simulated-Tenant`:** the frontend sends it and the backend ignores it.
- **Other caches:** the `SecureAPI` cache key includes tenant and session, nginx only serves static files, and nothing writes to the IndexedDB query cache.
- **Console errors at login:** `SessionRecovery ... 'split'` and `Login error ... 'session'` appeared before any change. Login still works, and they weren't investigated further.

## Known and not fixed

- **Currency** is hardcoded to USD although `reservations.currency` exists. All seeded rows are USD, and mixed currencies would need a conversion rule the brief doesn't give.
- **Row-level security** is enabled with no policies, and the app connects as a superuser, so isolation rests on the query filters.
- **The signing secret** has a default in `config.py` and `docker-compose.yml`, and anyone with it can sign a token.
- **Secrets reach the logs:** token previews in `core/auth.py` and a preview of `SECRET_KEY` in `config.py`.
- **Operations routes** in `main.py` have no authentication.
- **`/api/v1/cities`** returns 500, because it queries a column the schema doesn't have. The dashboard doesn't call it.
- **`/api/v1/departments`** skips its tenant filter when a user has no tenant. It isn't reachable today: unknown users get 403 at the permission check, and the table isn't in the schema. It should return 403 too.
- **A Redis outage** would likely return 500. This is from reading the code and wasn't tested.
- **Repo hygiene:** `frontend/.env`, `frontend/node_modules` and `frontend/dist` are committed, and there's no `.gitignore`.

## Assumptions

- A booking's revenue belongs to the month of its check-in, in the property's local time, with no splitting across months.
- Sunset's internal records aren't in the repo, so "correct" means what the seed data gives.
- `total_revenue` stays a JSON number, rounded to cents by the server.
