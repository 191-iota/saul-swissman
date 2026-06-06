#!/usr/bin/env bash
# Saul Swissman — there is no engine to run; Claude Code is the engine. This prepares the
# register, optionally fetches the full law corpus, opens the webview, and points you at SAUL.md.
set -euo pipefail
cd "$(dirname "$0")"

LAWS_REPO="https://github.com/legalize-dev/legalize-ch.git"

# register/ is versioned: git diff over it is how Saul tracks corpus drift. Initialise once.
if [ ! -d .git ]; then
  git init -q
  git add -A
  git commit -q -m "saul: seed register + seed corpus (BV, OR, StGB-AT, DSG)" || true
  echo "Initialised git (register/ is under version control; the corpus is git-ignored)."
fi

# The seed corpus (4 complete codes) ships in corpus/ch/ — Saul answers everyday questions offline
# without this step. Cloning legalize-ch widens coverage to all ~5800 federal norms.
if [ ! -e corpus/ch/cc-2010-262.md ]; then     # a non-seed file → corpus not yet fully cloned
  printf "Fetch the full Swiss federal law corpus (~114 MB) from legalize-ch? [y/N] "
  read -r ans || ans=""
  if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
    tmp="$(mktemp -d)"
    echo "Cloning ${LAWS_REPO} (shallow)…"
    git clone --depth 1 "$LAWS_REPO" "$tmp/legalize-ch"
    # copy the laws into corpus/ch (keeps the vendored seed; adds the rest). corpus/ is git-ignored.
    cp -n "$tmp/legalize-ch/ch/"*.md corpus/ch/ 2>/dev/null || true
    rm -rf "$tmp"
    echo "Corpus filled. Now run REGISTER so Saul re-maps it:  ./launch.sh web  →  press ↻ Register"
    echo "  (or in a Claude Code session here:  claude -p \"register\")"
  fi
fi

# `./launch.sh web` opens the white webview (a local viewer + remote control for headless Claude
# Code). It is optional — everything works from a plain Claude Code session in this folder too.
if [ "${1:-}" = "web" ]; then
  exec python3 web/serve.py
fi

cat <<'EOF'

Saul Swissman is ready. Two ways in:

  • The webview (simplest):   ./launch.sh web    → open http://127.0.0.1:8788
      ask a legal question; every claim is a clickable citation that opens the verbatim statute.

  • A Claude Code session in this folder (the raw engine):
      Just ask a Swiss-law question — Saul reads SAUL.md and answers as counsel, with citations.
      After cloning more of the corpus, say "register" so Saul re-maps it.

Read SAUL.md once. It is the whole program.
Try:  "Darf mein Vermieter den Mietzins erhöhen?"
EOF
