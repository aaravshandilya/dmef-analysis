#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v gh >/dev/null || { echo 'Install GitHub CLI first: brew install gh'; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login
if [ ! -d .git ]; then git init -b main; fi
git add .
if ! git diff --cached --quiet; then git commit -m 'Add DMEF pilot analysis and grouped model training'; fi
if git remote get-url origin >/dev/null 2>&1; then
  echo 'An origin already exists; refusing to publish without checking its identity and privacy.'
  exit 1
fi
gh repo create dmef-analysis --private --source=. --remote=origin
test "$(gh repo view --json isPrivate --jq .isPrivate)" = true
git push -u origin main
gh repo view --json url,isPrivate
