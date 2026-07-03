#!/bin/bash

set -e

PROJECT_DIR="/Users/perry/Documents/GitHub/Halifax-burn-restriction-tracker"
LOG_FILE="$PROJECT_DIR/daily_update.log"
ERROR_FILE="$PROJECT_DIR/daily_update_error.log"

cd "$PROJECT_DIR"

echo "==== Daily update started: $(date) ====" >> "$LOG_FILE"

source .venv/bin/activate

python scripts/update.py >> "$LOG_FILE" 2>> "$ERROR_FILE"

git add \
  data/latest.json \
  data/history.json \
  data/weather.json \
  data/prediction.json \
  data/predictions_archive.json \
  data/learning.json \
  data/metrics.json \
  docs/latest.json \
  docs/history.json \
  docs/weather.json \
  docs/prediction.json \
  docs/predictions_archive.json \
  docs/learning.json \
  docs/metrics.json

if git diff --cached --quiet; then
  echo "No changes to commit." >> "$LOG_FILE"
else
  git commit -m "Daily Halifax burn update" >> "$LOG_FILE" 2>> "$ERROR_FILE"
  git push origin main >> "$LOG_FILE" 2>> "$ERROR_FILE"
fi

echo "==== Daily update finished: $(date) ====" >> "$LOG_FILE"