---
name: kickoff
description: Start a timed assessment. Reads ASSIGNMENT.md, maps the repo, runs a baseline, and writes the requirement checklist and time plan to NOTES.md. Run once at the start, before any code.
disable-model-invocation: true
---

# Kickoff

The aim is a plan Omar can approve in under 15 minutes from the start. Speed matters, but a missed requirement costs more than two extra minutes of reading.

## Steps

1. **Read `ASSIGNMENT.md` in full**, plus any file or link inside the repo that it points to. Read it, don't skim it.
   - If it restricts AI tools, stop and tell Omar before doing anything else.

2. **Start the installs in the background** while you read the code. They are the slowest part of setup.
   - Use the commands the README gives.
   - Python: a venv inside the backend folder.
   - Node: `npm install` in each folder with a `package.json`.

3. **Create `NOTES.md`** from [notes-template.md](notes-template.md) and fill it in from the brief:
   - **Requirements:** every explicit ask as R1..Rn, each with a short quote and its priority.
     - **Must:** explicitly asked.
     - **Should:** what a reviewer expects without being told: tests for core logic, error handling, a README.
     - **Could:** extras.
   - **Exact names:** every route, field, file, command or output format the brief names, copied exactly. Note anything the brief says "will be tested".
   - **Deliverables and rules:** how to submit (branch, PR, push), what to hand in, the AI-tool policy, and any other constraints.

4. **Map the repo.** If it has more than about 40 source files, use the Explore agent for this. Find:
   - the stack and versions, and the entry points;
   - how routes, models, schemas and components are laid out;
   - the existing pattern the new work should copy;
   - every `TODO` marker (`grep -rn "TODO" --exclude-dir=node_modules --exclude-dir=venv --exclude-dir=.venv .`);
   - the env vars the code reads;
   - the test setup, or the fact that there isn't one.

5. **Run the baseline** once the installs finish, in about 5 minutes at most.
   - Run whatever checks exist: tests, `tsc`, lint, build. Also check that the backend imports and the frontend builds.
   - Record each pass or fail in NOTES.md §Baseline.
   - If an install fails, tell Omar straight away with the error.

6. **Fill in CLAUDE.md:**
   - §Commands: exact commands, including how to run a single test.
   - §Conventions: the patterns found in step 4.
   - If the repo shipped its own CLAUDE.md, add a short `## Commands` section to it instead of replacing anything.

7. **Write the plan** in NOTES.md §Plan:
   - Order the Must items as vertical slices, each with a minute estimate. Slice 1 also adds the smallest test setup, if the repo has none.
   - The build budget is about 75 minutes (from 0:15 to 1:35 elapsed), and estimates run low. If the Musts add up to more than about 55 minutes, propose what to cut or simplify.
   - Write the cut ladder: what gets dropped first, and the floor that never gets cut.
   - List each ambiguity under Assumptions, with the reading you chose and a one-line reason.

8. **Report and stop.** In chat, in under 15 lines:
   - how many requirements there are, and the Musts;
   - the slices in order with estimates;
   - the assumptions;
   - any risks: a failing baseline, a missing API key, a slow install.

   Then wait for Omar's go before writing code.
