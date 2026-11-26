#!/bin/sh
# Point this checkout's git hooks at scripts/hooks (local repo config only).
set -eu
cd "$(dirname "$0")/.."
chmod +x scripts/hooks/*
git config core.hooksPath scripts/hooks
echo "git hooks: $(git config core.hooksPath)"
