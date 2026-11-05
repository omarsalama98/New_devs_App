---
name: wrap-up
description: Finish a timed assessment. Feature freeze, final checks, the brief audit, the README and the last commit and push. Run at about 1:35 elapsed, or earlier if time is short.
disable-model-invocation: true
---

# Wrap-up

From here on, no new features. Only fixes for a broken Must.

## Steps

1. **Check everything once.**
   - Run every command in CLAUDE.md §Commands.
   - Run the acceptance check for each requirement in `NOTES.md`.
   - Update its Status and Proof columns with what actually happened.

2. **Run the `brief-auditor` agent.** Tell it how many minutes are left. Fix only the blocking items that fit in the time.

3. **Write the README.** Keep the starter's own content, and add these sections:
   - **What's done:** each requirement R1..Rn with an honest status (done, partial, not done) and one line on how to see it working.
   - **How to run and test:** exact commands and the env vars, pointing to `.env.example`. Say whether it runs without an API key, and how.
   - **Approach and key decisions:** 3–6 bullets, each with the reason and the trade-off.
   - **Assumptions:** from NOTES.md.
   - **What I'd do next:** ranked and concrete, e.g. "stream the draft", not "improve performance".
   - **How I used AI tools:** two or three plain lines: what Claude Code did, and what Omar checked himself. Leave this out if the brief says otherwise.

   Write it as Omar: first person, plain words, short sentences. No em dashes, no marketing words ("robust", "seamless", "leverage").

4. **Clean up:**
   - No secrets in the repo: `git grep -nI -E "sk-[A-Za-z0-9_-]{20,}|(api_key|secret|token)\s*=\s*['\"][^'\"]+['\"]"`.
   - `.env` is ignored and `.env.example` is current.
   - No debug prints, commented-out code or unused imports in changed files.
   - No `node_modules`, virtualenvs, build output or local databases tracked, unless the starter tracked them.

5. **Commit and push.** Propose the final commit message. After Omar commits and pushes, confirm the push landed:
   - `git status -sb` shows nothing ahead of the remote;
   - `git log -1 origin/<branch>` matches `git log -1`.
