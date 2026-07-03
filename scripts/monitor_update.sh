#!/bin/bash

set -e

PROJECT_DIR="/Users/perry/Documents/GitHub/Halifax-burn-restriction-tracker"
LOG_FILE="$PROJECT_DIR/monitor_update.log"
ERROR_FILE="$PROJECT_DIR/monitor_update_error.log"

START_TIME="14:00"
END_TIME="14:30"
INTERVAL_SECONDS=300

cd "$PROJECT_DIR"

echo "==== Monitor started: $(date) ====" >> "$LOG_FILE"

while true; do
  NOW_HM=$(date +"%H:%M")

  if [[ "$NOW_HM" > "$END_TIME" ]]; then
    echo "Reached end time $END_TIME without confirmed update." >> "$LOG_FILE"
    exit 1
  fi

  echo "Attempting update at $(date)" >> "$LOG_FILE"

  if ./scripts/run_daily_update.sh >> "$LOG_FILE" 2>> "$ERROR_FILE"; then
    echo "Update command succeeded at $(date)" >> "$LOG_FILE"
    echo "==== Monitor finished: $(date) ====" >> "$LOG_FILE"
    exit 0
  else
    echo "Update command failed at $(date). Retrying in $INTERVAL_SECONDS seconds." >> "$LOG_FILE"
    sleep "$INTERVAL_SECONDS"
  fi
done