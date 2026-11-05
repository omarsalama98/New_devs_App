---
name: slice
description: Build the next requirement from NOTES.md as one working vertical slice (contract, backend, frontend, test), verify it, and propose a commit. Use for each feature or fix during the assessment.
argument-hint: "[requirement id, e.g. R2]"
---

# Slice

One requirement, working end to end, verified, then stop. Target: $ARGUMENTS (if empty, the next open Must in `NOTES.md`).

## Steps

1. **State the acceptance check in one line:** the observable thing that proves the requirement works. For example, a request and its expected response, a test, or a UI action and what appears.

2. **Find the closest existing pattern** in the starter: a route, a schema, an API helper, a component. Copy its shape, so the new code reads like the old code.

3. **Contract first.** Write the request and response models, field names and status codes, then the frontend API function and its types. Names the brief gives are used exactly.

4. **Build backend, then API test, then frontend.** Write the failure paths alongside the happy path:
   - not found → 404;
   - invalid input → 422 or 400 with a message;
   - an external call that fails or times out → a clear error status. Never a 200 that holds an error string.
   - The UI shows loading, error and empty states.
   - LLM or HTTP calls go through one small function with a timeout and a lazily created client, so a test can replace it and the app still starts without a key.

5. **Test.** At least one test that would catch a regression in this slice's core logic.
   - Mock external calls at that function's boundary. Never call a real LLM in a test.
   - If the repo has no test setup, add the smallest one that works, e.g. `pytest` with FastAPI's `TestClient` and a dependency override for the database.

6. **Verify.** Run the commands in CLAUDE.md §Commands plus the acceptance check, and show the output. If the slice touched more than about three files or added an external call, run the `code-reviewer` agent on the diff and fix what it marks blocking.

7. **Update NOTES.md:** the requirement's status and proof, and any decision or assumption you made, in one line each.

8. **Hand over** in under 8 lines:
   - what changed, by file;
   - anything non-obvious Omar should read, so he can explain it later;
   - the proposed commit message.

   Commit only if Omar has asked for commits in this session.
