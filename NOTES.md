# Revenue Debugging Notes

Started 17:50 · Feature freeze 19:25 (+1:35) · Hard stop 19:50 (+2:00)

## Summary

**Status:** all fixes are committed on `fix/revenue-dashboard` and 40 tests pass. The code review found nothing blocking. The write-up is in `FINDINGS.md`, and the Loom is the remaining deliverable.

**Main finding:** the dashboard has never read Postgres. Several faults on the database path each end in a catch-all `except` that returns hardcoded numbers to any tenant. So nothing the clients see comes from their data, and the three reported symptoms sit on top of that.

| Symptom | What the client sees now | Correct | Root cause |
|---|---|---|---|
| S1 March totals | Beach House Alpha: USD 1,000.00, 3 bookings | USD 2,250.00, 4 bookings | The mock data leaves out `res-tz-1` (1,250.00). Behind it, the unused monthly function uses UTC bounds, which would put that booking in February: Sunset's March is 12,076.00 in UTC and 13,326.00 in property time |
| S2 another client's revenue | Ocean's dropdown lists Sunset's three properties, and picking one shows Sunset's revenue | Ocean sees its own three properties and figures only | Three separate leaks: the cache key has no tenant, the mock data ignores the tenant, and the property list is hardcoded |
| S3 cents off | Not visible on seeded totals. A total of `2250.555` shows as `2,250.55` | `2,250.56` | `float()` on the server, then `Math.round` in the browser. About 6.6% of totals ending in `.xx5` lose a cent |

**Decided with Omar:**

1. **The "12%" trend gets calculated, not removed.** It compares the selected month with the month before, in the property's time zone. If the earlier month has no revenue, the badge says "No prior data".
2. **The dashboard opens on the all-time total.** A month picker shows a month's total and trend. The all-time view has no badge, because it has no earlier period to compare with.
3. **The seed data stays as it is.** All seeded revenue is in March 2024, so the demo shows "No prior data" for March and -100% for April. Tests prove rising trends with temporary rows.
4. **Commits:** the Claude Code setup first, then one commit per fix group after that group is verified, with `NOTES.md` last.

**Also changed after re-checking:**

- Browser rounding stays. Once the server rounds to cents, it never changes a value (8 million values tested), so the cents fix is server-only and the "Precision Mismatch" block isn't touched.
- A database failure returns 503 and catches both `OSError` and `SQLAlchemyError`, because a closed port and a bad password raise different types.
- Unknown and other-tenant properties both return the same 404, so the response doesn't reveal whether a property exists.

The database connection, queries and rounding were checked in a scratch script against the real data. The cache, route and frontend changes are still untested.

## Issues and fixes

Paths are under `backend/app/` or `frontend/src/components/`, except `backend/requirements.txt`.

### Fix 1: read real data (10 min)

| # | Issue | Where | Fix |
|---|---|---|---|
| B1 | `sqlalchemy>=2.0.0` resolves to 2.1.8, which doesn't install `greenlet`, so the async import fails | `backend/requirements.txt:21` | Use `sqlalchemy[asyncio]>=2.0.0` and rebuild the backend image |
| B2 | The pool reads `settings.supabase_db_*`, which don't exist, and ignores `database_url` | `core/database_pool.py:18` | Build the URL from `settings.database_url`, changing `postgresql://` to `postgresql+asyncpg://` |
| B3 | `QueuePool` is rejected by the async engine | `core/database_pool.py:22` | Remove it and its import, so SQLAlchemy picks the async pool |
| B4 | `get_session` is `async def` but is used with `async with` | `core/database_pool.py:48` | Make it a plain `def` |
| B5 | A new pool is created on every call | `services/reservations.py:40-44` | Use the shared `db_pool` and initialise it once |
| B6 | The catch-all returns mock figures for any tenant, and the result is cached for 5 minutes. With an empty cache, Ocean's `prop-002` still returned Sunset's 4,975.50 | `services/reservations.py:88-109` | Delete the fallback. `api/v1/dashboard.py` returns 503 with a clear message on database errors, and nothing is cached |
| B7 | The error state is never cleared, so one failure sticks until reload. This becomes reachable once B6 is gone | `RevenueSummary.tsx:24-36` | Clear it when a fetch starts |

### Fix 2: isolate tenants (15 min)

| # | Issue | Where | Fix |
|---|---|---|---|
| B8 | The cache key has no tenant. Whichever client asks first fills the entry for both, for 5 minutes | `services/cache.py:13` | `revenue:{tenant_id}:{property_id}` |
| B9 | The hardcoded list shows all five names to everyone, and labels Ocean's `prop-001` (Mountain Lodge Beta) as Sunset's Beach House Alpha | `Dashboard.tsx:4-10` | Add `GET /api/v1/properties`, scoped to the caller's tenant. `Dashboard.tsx` loads it through the existing `SecureAPI.getProperties`, with loading, error and empty states |
| B10 | Unknown users fall through to `tenant-a`. A validly signed token for `nobody@example.com` got Sunset's figures | `core/tenant_resolver.py:92` | Return `None` for unknown users |
| B11 | A user with no tenant carries on under a made-up `default_tenant` | `api/v1/dashboard.py:14` | Return 403 |

The two client logins aren't affected by B10 or B11. Other callers of the resolver only see a change for users with no tenant mapping, and none exist today.

### Fix 3: March in property time (10 min)

| # | Issue | Where | Fix |
|---|---|---|---|
| B12 | `calculate_monthly_revenue` uses UTC bounds, has no tenant argument and always returns 0. Nothing calls it, so the dashboard has no way to show a month | `services/reservations.py:5-32` | Real query filtered by tenant, comparing `check_in_date AT TIME ZONE properties.timezone` with the month bounds |
| B13 | The summary route takes no period | `api/v1/dashboard.py:8-12`, `services/cache.py:13` | Optional `month` (1-12) and `year`, which must be sent together. The period goes in the cache key. Without them the route returns the all-time total, as it does now |

### Fix 4: cents (5 min)

| # | Issue | Where | Fix |
|---|---|---|---|
| B14 | Money goes through `float`, then the browser rounds it a second time | `api/v1/dashboard.py:18`, `RevenueSummary.tsx:64` | Round on the server with `Decimal.quantize(Decimal("0.01"), ROUND_HALF_UP)`. No frontend change: the browser's rounding has no effect on a value already in cents |

### Fix 5: real trend (10 min)

| # | Issue | Where | Fix |
|---|---|---|---|
| B15 | A made-up "12%" trend sits next to a financial figure | `RevenueSummary.tsx:83-89` | Calculate it month over month on the server and show it for month views |
| B16 | A slow response for the previous property can overwrite the current one | `RevenueSummary.tsx:24-44` | Ignore stale responses in the effect cleanup |

## Detailed plan

Each commit follows the same order: write the regression test and see it fail, make the fix, see the test pass, verify, then commit. Paths are relative to `backend/app/` or `frontend/src/` unless shown in full.

**Verification for every commit:** the full `pytest` suite passes, the two dashboard files stay lint-clean, typecheck stays at 256 errors, and the frontend builds to a scratch folder. The acceptance check is then run against the live stack.

### Commit 1: read real data

**Message:** `fix: read revenue from Postgres instead of silent mock data`

**Acceptance:** Sunset's `prop-001` returns 2,250.00 with 4 bookings. With the `db` container stopped, it returns 503 with no figures.

- `backend/requirements.txt:21`: `sqlalchemy[asyncio]>=2.0.0`, then rebuild the backend image.
- `core/database_pool.py`: build the URL with `settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)`. Remove `poolclass=QueuePool` and its import. Make `get_session` a plain `def`.
- `services/reservations.py`:
  - Add `class RevenueDataUnavailable(Exception)`.
  - Add a private `_fetch_rows(query, params)` that initialises the shared `db_pool` once, runs the `text()` query in a session, and turns `SQLAlchemyError` and `OSError` into `RevenueDataUnavailable`.
  - `calculate_total_revenue` uses it, and the whole mock `except` block goes.
- `api/v1/dashboard.py`: catch `RevenueDataUnavailable` and return 503 with a clear message.
- `components/RevenueSummary.tsx`: `setError('')` when a fetch starts.
- **Test setup:** `backend/tests/conftest.py` with `requests` calls against the live stack, a fixture for each client's login, and a fixture that clears `revenue:*` keys before each test.
- **Tests:** real totals for all of each client's properties, and 503 with `TestClient` and the dependency overridden.

### Commit 2: isolate tenants

**Message:** `fix: isolate revenue cache and property list by tenant`

**Acceptance:** in either call order, Sunset's `prop-001` is 2,250.00 and Ocean's is 0.00. Each dropdown lists only that client's three properties.

- `services/cache.py:13`: `revenue:{tenant_id}:{property_id}`.
- `services/reservations.py`:
  - Add `class PropertyNotFound(Exception)`.
  - Rewrite the total query as `properties LEFT JOIN reservations`, with `COALESCE(SUM(...), 0)` and `COUNT(r.id)`. No row means `PropertyNotFound`, and an owned property with no bookings gives 0.
  - Add `list_properties(tenant_id)`, returning `id` and `name` ordered by name.
- `api/v1/dashboard.py`:
  - Add a small helper that returns 403 when the user has no tenant, replacing line 14.
  - Map `PropertyNotFound` to 404.
  - Add `GET /properties`, returning `{"items": [...], "total": n}`, the shape `SecureAPI.getProperties` already expects.
- `core/tenant_resolver.py:92`: return `None`, and change the return type to `Optional[str]`.
- `components/Dashboard.tsx`: remove `PROPERTIES`. Load the list with `SecureAPI.getProperties()`, select the first one, and show loading, error and empty states.
- **Tests:** both call orders, tenant in the Redis key, each client's property list, 404 for other-tenant and unknown properties with identical bodies, `X-Simulated-Tenant` ignored, 403 for a signed token with an unknown email, 401 with no token.

### Commit 3: March in property time, with a month picker

**Message:** `fix: calculate monthly revenue in each property's time zone`

**Acceptance:** Sunset's `prop-001` is 2,250.00 for March 2024 and 0.00 for February 2024. Picking March on the dashboard shows the same.

- `services/reservations.py`: replace the stub with `calculate_monthly_revenue(property_id, tenant_id, month, year)`, returning the same dict as the total. It uses the same join, with the bounds on the join condition: `(r.check_in_date AT TIME ZONE p.timezone) >= :start` and `< :end`, with naive datetimes.
- `services/cache.py`: add optional `month` and `year`. The key gains `:{year}-{month:02d}` for month views.
- `api/v1/dashboard.py`: `month: Optional[int] = Query(None, ge=1, le=12)` and `year: Optional[int] = Query(None, ge=2000, le=2100)`. One without the other returns 400.
- `lib/secureApi.ts`: `getDashboardSummary` sends `month` and `year` when given.
- `components/Dashboard.tsx`: an `<input type="month">` with an "All time" button that clears it.
- `components/RevenueSummary.tsx`: optional `month` and `year` props, passed to the API and the effect dependencies, and a label showing the period.
- **Tests:** March and February for `prop-001`, Sunset's March total of 13,326.00 across properties, a temporary row at 03:00 UTC on 1 April in `prop-004` that counts as March in New York, invalid month 422, month without year 400, and month and all-time cache entries staying separate.

### Commit 4: cents

**Message:** `fix: round revenue to cents on the server with Decimal`

**Acceptance:** a temporary row bringing a total to `2250.555` returns `2250.56`, and `1.005` returns `1.01`.

- `api/v1/dashboard.py:18`: `float(Decimal(revenue_data["total"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))`, with a comment saying why rounding happens here.
- No frontend change.
- **Tests:** both temporary-row cases, with cleanup in a fixture.

### Commit 5: real trend

**Message:** `fix: replace hardcoded trend with month-over-month calculation`

**Acceptance:** March 2024 shows "No prior data" and April 2024 shows -100.0%. All time shows no badge.

- `services/reservations.py`: `calculate_trend_percent(current, previous)` returns `None` when `previous` is 0. Otherwise it returns the percentage change as a Decimal rounded half-up to one place.
- `services/cache.py`: month views also calculate the previous month (January rolls back to December of the year before), and the cached result gains `trend_percent`.
- `api/v1/dashboard.py`: the response gains `trend_percent`, a number or `null`. It's `null` for all time. Existing fields don't change.
- `components/RevenueSummary.tsx`: replace the fake block at lines 83-89. A month view shows a green up arrow or a red down arrow with the percentage, or a muted "No prior data". All time shows nothing.
- `components/RevenueSummary.tsx`: a `cancelled` flag in the effect cleanup, so stale responses are ignored (B16).
- **Tests:** March null, April -100.0, all time null, a temporary February row giving +100.0, a temporary December and January pair across the year boundary, and a repeat call returning the same value from the cache.

### Review cycle

After commit 5, `code-reviewer` reviews the full branch diff against `main`, and `brief-auditor` checks it against `ASSIGNMENT.md`. Blocking findings get fixed, re-verified and committed.

## Expected results after the fixes

| Login | Request | Total | Bookings |
|---|---|---|---|
| Sunset | `prop-001` Beach House Alpha | 2,250.00 | 4 |
| Sunset | `prop-001`, February 2024 | 0.00 | 0 |
| Sunset | `prop-001`, March 2024, "No prior data" | 2,250.00 | 4 |
| Sunset | `prop-001`, April 2024, -100.0% | 0.00 | 0 |
| Sunset | `prop-002` City Apartment Downtown | 4,975.50 | 4 |
| Sunset | `prop-003` Country Villa Estate | 6,100.50 | 2 |
| Ocean | `prop-001` Mountain Lodge Beta | 0.00 | 0 |
| Ocean | `prop-004` Lakeside Cottage | 1,776.50 | 4 |
| Ocean | `prop-005` Urban Loft Modern | 3,256.00 | 3 |

Each client's dropdown lists only its own three properties. Ocean asking for `prop-002`, which is Sunset's, gets 404. A signed token for an unknown user gets 403, and a database outage gets 503.

The scratch script confirmed the database figures for `prop-001`, `prop-002` as Sunset and as Ocean, and both months. It also confirmed both property lists, and half-up rounding of `2250.555` to `2250.56` and `1.005` to `1.01`.

The regression tests will be black-box HTTP calls against the running stack, using the real client logins. These bugs are in the wiring, and mocks are what hid them here.

## Checked and ruled out

- **`supabase_url is required` in the log.** It comes from a different pool, `supabase_pool`, which logs it once at startup and carries on. `DatabasePool` never reads that setting. Worth a sentence in the Loom.
- **Authentication.** No token, a garbage token and a wrong-secret token all return 401. A wrong password and an unknown email also return 401.
- **`X-Simulated-Tenant`.** The frontend sends it, but the backend ignores it. Ocean sending `tenant-a` was still calculated as `tenant-b`. Fix 2 adds a test for this.
- **`/api/v1/auth/me`.** It returns the right tenant for each client.
- **`/api/v1/company-settings`.** Its cache key includes the tenant.
- **Browser and proxy caches.** The `SecureAPI` cache key includes tenant and session, and is bypassed for these logins. nginx only serves static files. Nothing writes to the IndexedDB query cache, because nothing uses `useQuery`.

## Flag in FINDINGS, don't fix

- **Currency** is hardcoded to USD (`services/reservations.py:73`, `:82`) although `reservations.currency` exists. All 17 seeded rows are USD, and mixed currencies would need a conversion rule the brief doesn't give.
- **Row-level security** is enabled with zero policies, and the app connects as a superuser, so it protects nothing. Tenant isolation rests entirely on the query filters.
- **The signing secret** has a default in `config.py:14` and in `docker-compose.yml`. Anyone with it can sign a token, which is how B10 was tested.
- **Secrets reach the logs:** token previews at `core/auth.py:101` and `:104`, and a preview of `SECRET_KEY` at `config.py:44-45`.
- **Operations routes** have no authentication in `main.py`. The status routes returned 200 without a token. The reset and clear routes weren't called.
- **`/api/v1/cities`** returns 500 for both clients. It queries a `city` column the schema doesn't have, with no tenant filter. The dashboard doesn't call it.
- **A Redis outage** would likely surface as a 500, because `services/cache.py` has no error handling. This is from reading the code and wasn't tested.
- **Repo hygiene:** `frontend/.env`, `frontend/node_modules` and `frontend/dist` are committed, and there's no `.gitignore`. `frontend/.env` wasn't read, because the permission rules blocked it.

## Requirements

| ID | Requirement (from ASSIGNMENT.md) | Priority | Status | Proof |
|---|---|---|---|---|
| R1 | S1, Sunset Properties: "We're showing different totals for March" | Must | done | Commits `c1e9d8b47`, `02f8b18e6`, tests, browser |
| R2 | S2, Ocean Rentals: "when we refresh the page, we see revenue numbers that look like they belong to another company" | Must | done | Commits `c1e9d8b47`, `9ac60963d`, tests, browser |
| R3 | S3, finance: "revenue totals that seem 'slightly off' by a few cents" | Must | done | Commit `71826c475`, tests with temporary rows |
| R4 | "Investigate the reported issues by logging in as each client" and "Test your fixes with the provided client credentials" | Must | done | Tests use the real client logins |
| R5 | "Identify any bugs in the system" and "Fix the problems you find" | Must | done | `FINDINGS.md`, including what's known and not fixed |
| R6 | Loom, 5-10 min: bugs and how found, root cause, fix, quick demo | Must | Omar recording | |
| R7 | "Do NOT rebuild the system"; "Use the existing codebase structure and patterns" | Must | done | Fixes follow the existing routers and services |
| R8 | Regression test for each fixed bug (the repo has no tests) | Should | done | 40 passing. The session, stale-response and error-state fixes have browser proof only |
| R9 | `FINDINGS.md`: bug, how found, root cause (file:line), fix, proof. Doubles as the Loom script | Should | done | `FINDINGS.md` |

## Exact names from the brief

Nothing in the brief is marked as automatically tested. These must keep working unchanged.

- Start command: `docker-compose up --build`
- Frontend: `http://localhost:3000` · Backend API: `http://localhost:8000/docs`
- Logins: the two client accounts listed in `ASSIGNMENT.md`
- Client names: Sunset Properties (`tenant-a`), Ocean Rentals (`tenant-b`)
- Existing routes: `POST /api/v1/auth/login`, `GET /api/v1/dashboard/summary?property_id=`
- Existing response fields: `property_id`, `total_revenue`, `currency`, `reservations_count`

## Deliverables and rules

- How to submit: the brief doesn't name a branch or PR flow. It only requires the Loom video.
- What to hand in: a Loom of 5-10 minutes. Reviewers can also read the code and commit history.
- AI tools policy: the brief doesn't mention AI tools, so there's no restriction to apply.
- Other constraints: debugging only, no rebuild. Keep the existing structure and patterns.

## Baseline (before any change)

| Check | Command | Result |
|---|---|---|
| Stack starts | `docker compose up --build -d` | Pass: all 4 containers running, frontend returns 200 |
| Backend imports | `python -c "import app.main"` | Pass: 30 routes |
| Backend tests | `pytest` | None exist ("no tests collected") |
| Frontend typecheck | `tsc --noEmit -p tsconfig.app.json` | **Fail, pre-existing:** 256 errors, 12 in `secureApi.ts`, 0 in `Dashboard.tsx` and `RevenueSummary.tsx` |
| Frontend lint | `eslint src` | **Fail, pre-existing:** 579 errors, 31 warnings. The two dashboard files are clean |
| Frontend build | `vite build --outDir <scratch>` | Pass |
| Login as each client | `POST /api/v1/auth/login`, and the UI as Ocean | Pass: both logins work |
| Summary as each client | `GET /api/v1/dashboard/summary` | **Bug:** identical mock figures for both clients on all five properties |

### Live figures before any fix

| Property | API as Sunset | API as Ocean | Database: Sunset | Database: Ocean |
|---|---|---|---|---|
| `prop-001` | 1,000.00 (3) | 1,000.00 (3) | 2,250.000 (4) | none |
| `prop-002` | 4,975.50 (4) | 4,975.50 (4) | 4,975.500 (4) | not theirs |
| `prop-003` | 6,100.50 (2) | 6,100.50 (2) | 6,100.500 (2) | not theirs |
| `prop-004` | 1,776.50 (4) | 1,776.50 (4) | not theirs | 1,776.500 (4) |
| `prop-005` | 3,256.00 (3) | 3,256.00 (3) | not theirs | 3,256.000 (3) |

In the first baseline run, the backend log showed every calculation running for `tenant-a`. Ocean's calls never reached the calculation: they were served from Sunset's entries under `revenue:prop-00x`.

March 2024 from the database: Sunset is 12,076.00 with UTC bounds and 13,326.00 in property time. The 1,250.00 difference is `res-tz-1`, which checks in at 23:30 UTC on 29 Feb, or 00:30 on 1 March in Paris. Ocean is 5,032.50 either way.

## Plan

| # | Slice | Covers | Est. (min) |
|---|---|---|---|
| 1 | Read real data (B1-B7), plus test setup | R1 R4 R5 R8 | 7 |
| 2 | Isolate tenants (B8-B11) | R2 R5 R8 | 7 |
| 3 | March in property time, month picker (B12-B13) | R1 R8 | 7 |
| 4 | Cents (B14) | R3 R8 | 3 |
| 5 | Real trend, stale responses (B15-B16) | R5 R8 | 6 |

Then the review cycle, then `/wrap-up`: `FINDINGS.md`, which doubles as the Loom script (R6, R9).

Time left at 18:54: 31 min to freeze, 56 to the hard stop. The five commits are estimated at 30 min, so the review cycle will likely run past the freeze and into the buffer before the hard stop.

**Cut ladder** (drop from the top first):
1. B16 stale responses. List it in FINDINGS as known and unfixed.
2. B10 and B11. List them in FINDINGS.
3. Any test beyond one regression test per fix.

**Never cut:** the real database path · tenant in the cache key · tenant-scoped property list · time zone fix · cents fix · real trend · one regression test per fix · `FINDINGS.md` with honest status.

## Assumptions

- A booking's revenue belongs to the month of its check-in, in the property's local time, with no splitting across months. The existing queries filter on `check_in_date`, and `res-tz-1` sits on exactly this boundary.
- Sunset's internal records aren't in the repo, so "correct" means what the seed data gives: Beach House Alpha 2,250.00, Sunset's March 13,326.00.
- `total_revenue` stays a JSON number, rounded to cents on the server. This keeps the existing field and type, and full precision stays in the database.
- No seeded total shows S3, so its proof uses a temporary test row. FINDINGS will say so.
- A trend percentage is rounded to one decimal place, half-up. When the current month is 0 and the previous month isn't, that's a true -100.0%.

## Decisions

- Omar asked Claude to finish the investigation and to confirm the issues and fixes before anything changes.
- `GET /api/v1/properties` instead of a new dashboard route, because `SecureAPI.getProperties` already calls that path and nothing else uses it.
- Docker instead of the local fallback, because the daemon is up and it's the brief's own command.
- `npm install` skipped, which departs from the kickoff steps. `frontend/node_modules` is committed and already has darwin-arm64 binaries, and an install could dirty thousands of tracked files.
- Builds go to a scratch folder, because `npm run build` would overwrite the committed `frontend/dist`.
- `backend/.venv`, Python caches, `.playwright-mcp/` and `NOTES.html` are listed in `.git/info/exclude`, which is local only. No `.gitignore` was added, to keep the diff against the starter clean.
- `greenlet` is installed by hand in the local venv for probing. Fix 1 makes it a real dependency.
- `.claude/` and `CLAUDE.md` are committed first, to show how AI was used. `NOTES.md` is committed last, once it reads as a finished record. `FINDINGS.md` carries the write-up.
- Fix agents run one at a time, not in parallel or in separate worktrees. The fixes touch the same files, and the running stack is bind-mounted to this folder.

## Log

- 17:50 kickoff
- 17:58 live baseline as both clients: mock data confirmed
- 18:02 first plan written. Omar then took over the investigation
- 18:36 Omar handed the investigation back. Auth boundary, other endpoints and fix recipes checked
- 18:37 issues and fixes written up, waiting for confirmation
- 18:47 findings re-verified, three decisions corrected
- 18:54 decisions made with Omar, detailed plan written, fix agents starting
- 19:05 commit 1 verified: real data
- 19:12 commit 2 verified: tenant isolation
- 19:21 commit 3 verified: March and month picker
- 19:23 commit 4 verified: cents
- 19:24 extra bug found and fixed: session lost on the second reload after login
- 19:28 commit 5 verified: real trend. Review cycle started
- 19:30 code review finished, nothing blocking
- 19:35 write-up in `FINDINGS.md`, Omar recording the Loom
