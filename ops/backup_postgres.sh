#!/usr/bin/env bash
set -euo pipefail

# Nightly Postgres backup helper.
# Usage (cron/systemd):
#   DATABASE_URL="postgres://..." BACKUP_DIR="/var/backups/studioflow" OFFSITE_REMOTE="s3:bucket/path" ./backup_postgres.sh

: "${DATABASE_URL:?DATABASE_URL not set}"

BACKUP_DIR="${BACKUP_DIR:-/var/backups/studioflow}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
OFFSITE_REMOTE="${OFFSITE_REMOTE:-}"  # Optional: rclone remote or s3:// URL

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
FILENAME="studioflow-${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[backup] dumping database to ${BACKUP_DIR}/${FILENAME}"
pg_dump "$DATABASE_URL" | gzip > "${BACKUP_DIR}/${FILENAME}"

echo "[backup] pruning backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -type f -name "studioflow-*.sql.gz" -mtime +"$RETENTION_DAYS" -delete || true

if [[ -n "$OFFSITE_REMOTE" ]]; then
  echo "[backup] uploading offsite to ${OFFSITE_REMOTE}"
  if command -v rclone >/dev/null 2>&1; then
    rclone copy "${BACKUP_DIR}/${FILENAME}" "$OFFSITE_REMOTE"
  elif command -v aws >/dev/null 2>&1; then
    aws s3 cp "${BACKUP_DIR}/${FILENAME}" "$OFFSITE_REMOTE"
  else
    echo "[backup] OFFSITE_REMOTE set but no rclone/aws cli found" >&2
  fi
fi

echo "[backup] done"

