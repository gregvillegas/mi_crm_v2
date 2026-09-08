# User Activity Log Archiving

The `UserActivityLog` table records almost every authenticated request (via
`users/middleware.py`), so it grows continuously — it can reach tens of
thousands of rows in a matter of weeks. Left unmanaged, this slows the Django
admin's *User Activity Logs* page and bloats the database.

This feature lets you **archive old logs to compressed files and remove them
from the live table — without permanently deleting them.** Archived logs can be
restored at any time.

---

## How it works

The `archive_activity_logs` management command:

1. Selects `UserActivityLog` rows older than a chosen number of days.
2. Writes them to a compressed JSON file: `backup/activity_logs/user_activity_YYYYMMDD_HHMMSS.json.gz`.
3. Deletes **only** the rows it successfully archived, in batches, inside a transaction.

The archive is written using Django's own serializer, so it is fully compatible
with `manage.py loaddata` for restoring later. These files compress extremely
well (roughly 10–20× smaller than the raw rows).

**Safety guarantees:**

- The archive file is written **first**. The database is only touched **after**
  the file is confirmed on disk. If writing fails, the partial file is removed
  and **nothing is deleted**.
- Only the exact rows captured at the start of the run are deleted (by ID), so
  new logs created while the command runs are never lost.
- `--dry-run` reports what would happen without writing or deleting anything.

---

## Usage

Run from the project root, using the project's virtualenv Python.

```bash
# Archive logs older than 90 days (default) into backup/activity_logs/
python manage.py archive_activity_logs

# Use a different retention window (e.g. keep 60 days live)
python manage.py archive_activity_logs --days 60

# Preview only — writes nothing, deletes nothing
python manage.py archive_activity_logs --days 90 --dry-run

# Write archives to a custom directory
python manage.py archive_activity_logs --output-dir /path/to/archives
```

### Options

| Option          | Default                          | Description                                                        |
|-----------------|----------------------------------|--------------------------------------------------------------------|
| `--days N`      | `90`                             | Archive logs **older than** N days. `0` archives everything.       |
| `--output-dir`  | `<BASE_DIR>/backup/activity_logs`| Directory to write the `.json.gz` archive to.                      |
| `--batch-size`  | `5000`                           | Number of rows deleted per batch after archiving.                  |
| `--dry-run`     | off                              | Show the row count and date range only; make no changes.           |

### Example output

```text
Found 13987 user activity log(s) older than 0 day(s) (before 2026-09-07 13:59).
Archived 13987 row(s) to /private/var/www/mi_crm/backup/activity_logs/user_activity_20260907_140210.json.gz (612.4 KB).
Deleted 13987 archived row(s) from the live table. Restore anytime with:
    python manage.py loaddata /private/var/www/mi_crm/backup/activity_logs/user_activity_20260907_140210.json.gz
```

---

## Restoring archived logs

To bring archived logs back into the live table, load the archive file. Django's
`loaddata` reads `.gz` files natively:

```bash
python manage.py loaddata backup/activity_logs/user_activity_YYYYMMDD_HHMMSS.json.gz
```

After loading, the rows reappear in the admin's *User Activity Logs* page with
their original IDs, timestamps, and details. You can load a single archive, or
several, as needed.

> Tip: If you only need to *read* archived data occasionally (not put it back in
> the DB), you can inspect the file directly:
> `gzip -dc backup/activity_logs/user_activity_YYYYMMDD_HHMMSS.json.gz | less`

---

## Recommended production setup (cron)

To keep the table self-maintaining, schedule the command on the production
server. This example archives logs older than 90 days at 2 AM on the 1st of
every month.

### 1. Edit the crontab
Log in as the user that runs the Django app (e.g. `www-data`, `ubuntu`, or your
deploy user):

```bash
crontab -e
```

### 2. Add the cron entry
Adjust the paths to match your deployment.

```text
# Archive user activity logs older than 90 days — 2 AM on the 1st of each month
0 2 1 * * cd /private/var/www/mi_crm && /private/var/www/mi_crm/venv/bin/python manage.py archive_activity_logs --days 90 >> /private/var/www/mi_crm/logs/activity_archive.log 2>&1
```

Ensure the log directory exists (`mkdir -p /private/var/www/mi_crm/logs`) and
that the `backup/activity_logs/` directory is included in your off-server backup
routine so archives are preserved.

---

## Backup / retention notes

- Archives live in `backup/activity_logs/` by default. Include this directory in
  your regular server backups so the archived history is preserved off-machine.
- Each run produces a separate timestamped file; nothing overwrites previous
  archives.
- The command never deletes archive files — only live database rows that have
  been safely archived.

---

## Files involved

| File                                                        | Role                                                        |
|-------------------------------------------------------------|-------------------------------------------------------------|
| `users/management/commands/archive_activity_logs.py`        | The archive command.                                        |
| `users/models.py` → `UserActivityLog`                       | The model being archived.                                   |
| `users/middleware.py` → `UserActivityMiddleware`            | Writes the logs on each authenticated request.              |
| `backup/activity_logs/`                                     | Default destination for `.json.gz` archives.                |
