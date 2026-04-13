#!/bin/zsh
set -euo pipefail

export TZ="${DIGEST_TIMEZONE:-Europe/Moscow}"
cd "$(dirname "$0")/.."
export PYTHONPATH="src"
python3 -m digest_bot.main weekly-openclaw
