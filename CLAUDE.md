# CLAUDE.md

The brief is `ASSIGNMENT.md`. It is the spec: every explicit requirement in it gets built and shown working before anything extra. The requirement checklist, the plan, assumptions and decisions live in `NOTES.md`.

This is a fixed two-hour task. Reviewers read the code, the commit history and the README. The process rules are in `.claude/rules/timed-workflow.md`.

## This task

It's a **debugging exercise**, not a build: three reported symptoms to reproduce, root-cause and fix. The brief says not to rebuild the system and to keep the existing structure and patterns, so fixes stay minimal and local.
- In `/kickoff`, the requirement list is the reported symptoms (S1 March totals don't match for Sunset Properties; S2 another client's revenue shows up on refresh for Ocean Rentals; S3 totals a few cents off), plus any other bug found on the way. The time zone, caching and multi-tenant notes in the brief are hints.
- Use `/slice` per bug, in debug order: reproduce (a failing test or a request as a given client), find the root cause, make the smallest fix, then show it passing.
- The deliverable is a 5–10 minute **Loom video**, not a README. `/wrap-up` writes `FINDINGS.md`: for each bug, how it was found, the root cause (file:line), the fix and the proof. That file doubles as the Loom script.

## Commands

Run from the repo root unless a `cd` is shown. Client logins are in `ASSIGNMENT.md`.

- Start everything: `docker compose up --build -d`. Frontend `:3000`, API `:8000/docs`, Postgres on host port `5433`, Redis on host port `6380`.
- Apply changes: backend code reloads through the bind mount. A `requirements.txt` change needs `docker compose up --build -d backend`. A frontend change needs `docker compose up --build -d frontend`, because nginx serves the built bundle.
- Clear the revenue cache: `docker compose exec -T redis redis-cli FLUSHALL`
- Query the database: `docker compose exec -T db psql -U postgres -d propertyflow -c "..."`
- Backend logs: `docker compose logs backend --no-log-prefix`
- Python env for tests (3.12): `cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest`
- Backend tests (slice 1 adds them, and they need the stack running): `cd backend && .venv/bin/python -m pytest -q`
- A single test: `cd backend && .venv/bin/python -m pytest tests/test_file.py::test_name -q`
- Typecheck: `cd frontend && ./node_modules/.bin/tsc --noEmit -p tsconfig.app.json` (baseline 256 errors, so compare the count)
- Lint: `cd frontend && ./node_modules/.bin/eslint src/components/Dashboard.tsx src/components/RevenueSummary.tsx` (all of `src` has 579 baseline errors)
- Build check: `cd frontend && ./node_modules/.bin/vite build --outDir <scratch folder> --emptyOutDir`

## Conventions

- Backend: FastAPI routers in `backend/app/api/v1/*.py`, registered with the `/api/v1` prefix in `main.py`. Routers call plain async functions in `backend/app/services/`.
- Auth: routes take `Depends(authenticate_request)`, and the tenant comes from `current_user.tenant_id`, never from the client.
- Database: raw SQL through SQLAlchemy `text()` with named parameters, on an async session. Every query filters on `tenant_id`.
- Frontend: components call methods on the `SecureAPI` singleton in `frontend/src/lib/secureApi.ts`, which wrap `request`. Local `useState` and `useEffect`, Tailwind classes.
- Money: `NUMERIC(10,3)` in the database, `Decimal` in Python.

## Gotchas

<!-- Add anything surprising as it comes up: pre-existing failures, missing env vars, quirks in the starter. -->
- `frontend/node_modules` and `frontend/dist` are committed and there's no `.gitignore`. Don't run `npm install` or `npm run build`: they would dirty tracked files. Use the commands in §Commands.
- `frontend/.env` is excluded from the Docker build by `.dockerignore`, so the bundle falls back to `http://localhost:8000`.
- With the stack running, the backend logs `Database error for ...` when it falls back to mock data. Check for that line before trusting a figure.
- Docker Desktop on this Mac is old (2022, Docker 20.10.17) and `docker info` crashed before Desktop was started. If `docker compose up --build` won't run within a few minutes, run it locally instead: Homebrew Postgres is installed (`psql`, `pg_ctl`); create the `propertyflow` DB and load `database/schema.sql` then `database/seed.sql`. Install Redis with `brew install redis`, then `redis-server --daemonize yes`. Start the backend from `backend/` with `DATABASE_URL`, `REDIS_URL` and `SECRET_KEY` as in `docker-compose.yml`, but pointing at localhost. Run the frontend with `npm run dev`.
