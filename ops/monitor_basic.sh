#!/usr/bin/env bash
set -euo pipefail

# Basic droplet health snapshot for cron/email/Sentry check-ins.

HOST="$(hostname)"
NOW="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

LOAD="$(uptime | awk -F'load average:' '{print $2}' | xargs)"
MEM="$(free -h | awk '/Mem:/ {print $3 "/" $2}')"
DISK_ROOT="$(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 " used)"}')"

echo "NovartERP health · ${HOST} · ${NOW}"
echo "Load: ${LOAD}"
echo "Memory: ${MEM}"
echo "Disk(/): ${DISK_ROOT}"
