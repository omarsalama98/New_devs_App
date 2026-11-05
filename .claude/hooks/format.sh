#!/bin/bash
# PostToolUse(Edit|Write): format the edited file, but only with a formatter the project already
# configures. Formatting a starter file the project never formatted rewrites lines the task didn't
# touch, which buries the real change in the reviewer's diff. Never blocks: always exits 0.

f=$(jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -n "$f" ] && [ -f "$f" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Walk up from the file to the nearest folder that has a marker file.
nearest() {
  local d; d=$(dirname "$f")
  while [ "$d" != "/" ] && [ "${#d}" -ge "${#CLAUDE_PROJECT_DIR}" ]; do
    for m in "$@"; do [ -e "$d/$m" ] && { echo "$d"; return; }; done
    d=$(dirname "$d")
  done
}

case "$f" in
  *.ts|*.tsx|*.js|*.jsx|*.css|*.json|*.md)
    d=$(nearest .prettierrc .prettierrc.json .prettierrc.js .prettierrc.cjs .prettierrc.yaml prettier.config.js prettier.config.mjs)
    [ -n "$d" ] && [ -x "$d/node_modules/.bin/prettier" ] && "$d/node_modules/.bin/prettier" --write "$f" >/dev/null 2>&1
    ;;
  *.py)
    d=$(nearest ruff.toml .ruff.toml pyproject.toml)
    [ -n "$d" ] || exit 0
    if [ -f "$d/ruff.toml" ] || [ -f "$d/.ruff.toml" ] || grep -q '^\[tool\.ruff' "$d/pyproject.toml" 2>/dev/null; then
      ruff=$(command -v ruff) && "$ruff" format --quiet "$f" >/dev/null 2>&1
    fi
    ;;
esac
exit 0
