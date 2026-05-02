#!/bin/bash

# Configuration
RCLONE_BIN="/usr/bin/rclone"
RCLONE_BACKBLAZE="backblaze:"
RCLONE_CONFIG="/home/arosu/.config/rclone/rclone.conf"
LOG_BASE_DIR="/home/arosu/logs/backblaze-rclone-sync"

# Define Source:Destination pairs (Format: "Local_Path:Remote_Bucket")
PAIRS=(
  "/mnt/ssd/photo-library/library/admin:alex-photo-backups"
  "/mnt/ssd/files/arosu:alex-file-backups"
  "/mnt/ssd/photo-library/library/iclotea:ioana-photo-backups"
  "/mnt/ssd/files/iclotea:ioana-file-backups"
)

# Get current timestamp
current_datetime=$(date +"%Y%m%dT%H%M%S")

# Handle Logfile Prefix Argument
# If $1 is provided, it adds the prefix and a dash. Otherwise, it's just the timestamp.
PREFIX=$1
if [ -n "$PREFIX" ]; then
  LOG_FILENAME="${PREFIX}-${current_datetime}.log"
else
  LOG_FILENAME="${current_datetime}.log"
fi

LOGFILE="${LOG_BASE_DIR}/${LOG_FILENAME}"

# Print the log location to the terminal BEFORE redirection starts
echo "Log file: $LOGFILE"

# Redirect all stdout and stderr to the logfile
exec >>"$LOGFILE" 2>&1

# Start global timer
start_total=$(date +%s)

{
  echo "############################################################"
  echo "RUN START: $current_datetime"
  echo "############################################################"
} >>"$LOGFILE"

# Array to store results for summary
RESULTS=()

for entry in "${PAIRS[@]}"; do
  LIBRARY="${entry%%:*}"
  BUCKET="${entry#*:}"

  start_sync=$(date +%s)
  echo "[$(date +"%H:%M:%S")] STARTING SYNC: $LIBRARY -> $BUCKET" >>"$LOGFILE"

  # Validation check
  if [ ! -d "$LIBRARY" ]; then
    msg="ERROR: Directory $LIBRARY does not exist. Skipping."
    echo "[$msg]" >>"$LOGFILE"
    RESULTS+=("FAIL | $BUCKET | $msg")
    continue
  fi

  # Execute Sync
  $RCLONE_BIN \
    --config "$RCLONE_CONFIG" \
    sync \
    "$LIBRARY" \
    "$RCLONE_BACKBLAZE$BUCKET" \
    --verbose \
    --fast-list \
    --log-file "$LOGFILE"

  rc=$?
  end_sync=$(date +%s)
  duration=$((end_sync - start_sync))

  if [ $rc -eq 0 ]; then
    status="SUCCESS"
  else
    status="FAILED (Exit Code: $rc)"
  fi

  echo "[$(date +"%H:%M:%S")] FINISHED: $BUCKET | Status: $status | Duration: ${duration}s" >>"$LOGFILE"
  RESULTS+=("$status | $BUCKET | ${duration}s")
done

# End global timer and write Summary
end_total=$(date +%s)
total_duration=$((end_total - start_total))

{
  echo ""
  echo "--- RUN SUMMARY ---"
  echo "Total Duration: ${total_duration}s"
  for res in "${RESULTS[@]}"; do
    echo " - $res"
  done
  echo "############################################################"
  echo ""
} >>"$LOGFILE"
