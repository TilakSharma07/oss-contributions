#!/usr/bin/env bash
# Push this repository to GitHub.
#
# The sandbox that built these commits cannot reach github.com or api.github.com
# (both resolve into a private address range there), so the push has to run from
# your machine. Everything up to the push is already done: 2 commits, tests green
# from a fresh clone.
#
# Usage:  bash push.sh [repo-name]
set -euo pipefail

REPO="${1:-oss-contributions}"
cd "$(dirname "$0")"

echo "== state =="
git log --oneline | sed 's/^/  /'
echo "  files: $(git ls-files | wc -l)"

if gh auth status >/dev/null 2>&1; then
  echo "== creating $REPO via gh and pushing =="
  gh repo create "$REPO" --public --source=. --remote=origin --push \
    --description "Upstream contributions to nf-core/tools and Galaxy training-material"
else
  echo "== gh not authenticated =="
  echo "Either run:  gh auth login"
  echo "or create the repo in the browser and then:"
  echo "  git remote add origin https://github.com/TilakSharma07/$REPO.git"
  echo "  git push -u origin main"
  exit 1
fi

echo "== done =="
gh repo view "$REPO" --json url --jq .url
