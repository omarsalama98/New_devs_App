#!/bin/bash
# Stop hook: typecheck and lint the code changed this turn, and send failures back to Claude once.
# Exit 2 = keep working, with stderr as feedback. Exit 0 = let the turn end.
# Turn it off for the rest of the session: touch .claude/skip-verify

input=$(cat)
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
[ -f .claude/skip-verify ] && exit 0

# Nudge once per stop. If Claude is already continuing because of this hook, let it end the turn,
# so a failure it can't fix (or that predates the change) never turns into a loop.
[ "$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ] && exit 0

git rev-parse --git-dir >/dev/null 2>&1 || exit 0
changed=$(git status --porcelain --untracked-files=all | sed -E 's/^.{3}//; s/.* -> //')
[ -z "$changed" ] && exit 0

failures=""
add_failure() { failures+=$'\n=== '"$1"$' ===\n'"$(printf '%s' "$2" | tail -30)"; }

# --- TypeScript / JavaScript: each folder with a package.json and installed deps -----------------
while IFS= read -r pj; do
  dir=$(dirname "$pj"); rel=${dir#./}
  if [ "$dir" = "." ]; then pat='\.(ts|tsx|js|jsx)$'; else pat="^${rel}/.*\.(ts|tsx|js|jsx)$"; fi
  printf '%s\n' "$changed" | grep -Eq "$pat" || continue
  [ -d "$dir/node_modules" ] || continue

  has_script() { (cd "$dir" && node -e "process.exit(require('./package.json').scripts?.['$1']?0:1)") 2>/dev/null; }

  if has_script typecheck; then
    out=$(cd "$dir" && npm run --silent typecheck 2>&1) || add_failure "$rel: npm run typecheck" "$out"
  elif [ -f "$dir/tsconfig.json" ] && [ -x "$dir/node_modules/.bin/tsc" ]; then
    # Vite-style configs with project references need build mode; a plain config takes --noEmit.
    if grep -q '"references"' "$dir/tsconfig.json"; then
      out=$(cd "$dir" && ./node_modules/.bin/tsc -b 2>&1) || add_failure "$rel: tsc -b" "$out"
    else
      out=$(cd "$dir" && ./node_modules/.bin/tsc --noEmit 2>&1) || add_failure "$rel: tsc --noEmit" "$out"
    fi
  fi
  if has_script lint; then
    out=$(cd "$dir" && npm run --silent lint 2>&1) || add_failure "$rel: npm run lint" "$out"
  fi
done < <(find . -maxdepth 3 -name package.json -not -path '*/node_modules/*' 2>/dev/null)

# --- Python: the changed .py files ----------------------------------------------------------------
pyfiles=()
while IFS= read -r f; do
  [ -n "$f" ] && [ -f "$f" ] && pyfiles+=("$f")
done < <(printf '%s\n' "$changed" | grep -E '\.py$' | grep -vE '(^|/)(\.?venv|node_modules)/')

if [ ${#pyfiles[@]} -gt 0 ]; then
  # Syntax check without writing __pycache__.
  out=$(python3 -c 'import ast, sys
for f in sys.argv[1:]:
    ast.parse(open(f, encoding="utf-8").read(), f)' "${pyfiles[@]}" 2>&1) || add_failure "python syntax" "$out"

  # Use the project's ruff and its rules if it configures them. Otherwise only real bugs
  # (undefined names, unused imports, syntax): style rules would pull Claude into starter churn.
  ruff=$(find . -maxdepth 4 -path '*/bin/ruff' -not -path '*/node_modules/*' 2>/dev/null | head -1)
  [ -z "$ruff" ] && ruff=$(command -v ruff)
  if [ -n "$ruff" ]; then
    rules=(--select E9,F)
    if [ -f ruff.toml ] || [ -f .ruff.toml ] || grep -qs '^\[tool\.ruff' pyproject.toml */pyproject.toml; then rules=(); fi
    out=$("$ruff" check --quiet --output-format concise "${rules[@]}" "${pyfiles[@]}" 2>&1) || add_failure "ruff check" "$out"
  fi
fi

if [ -n "$failures" ]; then
  printf '%s\n' "Checks failed on code changed in this session. Fix what the change caused." \
    "If a failure was already in the baseline in NOTES.md, say so and stop; don't fix unrelated code." \
    "$failures" >&2
  exit 2
fi
exit 0
