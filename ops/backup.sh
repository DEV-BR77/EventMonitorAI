#!/bin/sh
set -eu
umask 077

interval="${BACKUP_INTERVAL_SECONDS:-86400}"
retention="${BACKUP_RETENTION_DAYS:-30}"
mkdir -p /backups

while true; do
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  target="/backups/$stamp"
  temporary="/backups/.${stamp}.tmp"
  mkdir -p "$temporary"
  if PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "$temporary/database.dump"; then
    tar -C /data/clips -czf "$temporary/clips.tar.gz" .
    (cd "$temporary" && sha256sum database.dump clips.tar.gz > SHA256SUMS)
    mv "$temporary" "$target"
    echo "Backup completed: $target"
  else
    rm -rf "$temporary"
    echo "Backup failed at $stamp" >&2
  fi
  find /backups -mindepth 1 -maxdepth 1 -type d ! -name '.*.tmp' -mtime "+$retention" -exec rm -rf {} +
  sleep "$interval"
done
