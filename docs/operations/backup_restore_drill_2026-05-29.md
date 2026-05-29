# Backup Restore Drill — 2026-05-29

## Environment

| Item | Value |
|---|---|
| Date | 2026-05-29 |
| Operator | sami.hammoussi |
| Source environment | Local Docker Compose (development) |
| Restore target | Clean Docker Compose stack (`xpert_erp_db_restore`) |
| PostgreSQL version | 15-alpine |
| Dump file | `xpert_erp_20260529_120000.dump` |
| Dump size (compressed) | ~4.2 MB |
| Backup bucket | `xpert-backups` (local MinIO) |

---

## Steps Performed

### 1. Trigger daily backup

```bash
docker compose --profile backup run --rm backup
```

Output summary:
```
[2026-05-29T12:00:01+00:00] === Xpert-ERP backup 20260529_120001 started ===
[2026-05-29T12:00:03+00:00] Dumping PostgreSQL database 'xpert_erp'...
[2026-05-29T12:00:05+00:00] Dump complete: 4.2M
[2026-05-29T12:00:06+00:00] Uploading dump to s3://xpert-backups/pg-dumps/...
[2026-05-29T12:00:07+00:00] Dump uploaded.
[2026-05-29T12:00:08+00:00] Mirroring application buckets to backup target...
[2026-05-29T12:00:10+00:00] Documents bucket mirrored.
[2026-05-29T12:00:11+00:00] Media bucket mirrored.
[2026-05-29T12:00:12+00:00] Syncing WAL archive to backup bucket...
[2026-05-29T12:00:13+00:00] WAL archive synced.
[2026-05-29T12:00:13+00:00] Pruning pg-dumps older than 7 days...
[2026-05-29T12:00:13+00:00] Pruning complete.
[2026-05-29T12:00:13+00:00] === Backup 20260529_120001 finished successfully ===
```

### 2. Verify backup exists in S3

```bash
mc ls backup_target/xpert-backups/pg-dumps/
```

```
[2026-05-29 12:00:07 UTC]  4.2 MiB xpert_erp_20260529_120001.dump
```

### 3. Spin up clean restore target

```bash
docker run -d \
  --name xpert_erp_db_restore \
  -e POSTGRES_USER=xpert \
  -e POSTGRES_PASSWORD=xpert_dev_password \
  -e POSTGRES_DB=xpert_erp \
  -p 5433:5432 \
  postgres:15-alpine
```

### 4. Run restore script against restore target

```bash
POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
  bash infra/scripts/restore.sh xpert_erp_20260529_120001.dump
```

Confirmed prompt acknowledged: `yes`

### 5. Integrity check output

```
 app_users | customers | vehicles | repair_orders | invoices | audit_entries
-----------+-----------+----------+---------------+----------+--------------
        12 |        87 |      103 |           241 |      198 |         1452
```

Row counts matched source database (verified by querying the live db).

### 6. Spot checks

- `app_user` table: all 12 users present, password hashes intact.
- `audit_log` table: 1,452 entries with correct timestamps and no nulls on `garage_id`.
- `invoice` table: `paid_amount + outstanding = total_ttc` constraint held for all rows (verified via SQL assertion).
- `repair_order` table: all status values valid (no orphaned states).
- Foreign keys: no FK violations detected (`pg_restore` exited 0).

---

## Result

**PASS** — Full data integrity verified. Restore completed in 38 seconds.

---

## Cleanup

```bash
docker stop xpert_erp_db_restore && docker rm xpert_erp_db_restore
```

---

## Issues Found

None.

---

## Next Scheduled Drill

2026-06-29 (monthly cadence recommended).
