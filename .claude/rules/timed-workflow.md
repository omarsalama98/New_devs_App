# Working in a time box

This repo is a timed assessment: two hours, fixed. It is judged on whether the brief's requirements work, whether the code is clean and explainable, and how the decisions are written up. Time is the binding constraint, so these rules trade breadth for finished, working slices.

## Order of work

1. `/kickoff` first. It reads the brief, maps the repo, records a baseline and writes the plan to `NOTES.md`. No code before Omar agrees the plan.
2. Build the Must items one at a time with `/slice`. Each requirement works end to end (backend, frontend, a test) before the next one starts. Half-built features score worse than fewer finished ones.
3. Feature freeze at 1:35 elapsed. Then `/wrap-up`: final checks, the README, the last commit and push.

## Scope

- The brief's explicit requirements come first. Extras start only once every Must works and is committed.
- Follow the starter's existing structure and style. Don't refactor, rename or reformat code the task doesn't need touched. Reviewers diff against the starter, and churn hides the real work.
- When the brief is ambiguous, pick the most reasonable reading, write it under Assumptions in `NOTES.md` and keep going. Nobody can be asked during the test.
- Names the brief gives (routes, fields, files) are used exactly as written. They may be tested automatically.
- Add a dependency only when it saves real time. Each one is something to justify.

## Quality bar

- Omar has to explain every line in the follow-up interview. Prefer plain code to clever code. Where a library does something non-obvious, a one-line comment says what.
- Handle the failure paths a user would actually hit: not found, empty, invalid input, and an external call that fails or times out. The API returns a clear status and message, and the UI shows loading, error and empty states.
- Secrets come from environment variables, never from code. Keep `.env` out of git and keep `.env.example` up to date.
- Anything that calls an LLM or another external API sits behind one small function. Create the client lazily, set a timeout, and let tests replace it. The app must still start without the key.

## Verification

- A slice is done when its acceptance check passes and the commands in CLAUDE.md §Commands pass. Show the output; don't just say it passed. A Stop hook also runs typecheck and lint on changed code.
- If a check was already failing in the baseline (`NOTES.md`), say so and leave it. Don't fix unrelated code.
- When debugging, reproduce the problem first, find the cause, then fix the cause. Don't widen a `try/except` or loosen a type to make an error go away.

## Commits

- Commits are small and working, with conventional messages, e.g. `feat: add draft-reply endpoint`. The history is part of what gets reviewed.
- Commit only when Omar asks for it. Propose the message at the end of every slice anyway.
- Never force-push, rewrite history, or commit `.env`, `node_modules`, virtualenvs or local databases.

## Process skills

In this repo, `/kickoff`, `/slice` and `/wrap-up` replace the general brainstorming and plan-writing skills, which take longer than this time box allows.
