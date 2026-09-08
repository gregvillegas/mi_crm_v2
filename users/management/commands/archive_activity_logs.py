"""
Archive old UserActivityLog rows to compressed JSON files, then remove only the
archived rows from the live table.

WHY: UserActivityLog is written on almost every request, so it grows quickly.
This keeps the live admin table small and fast while preserving every record on
disk. Archives are written with Django's serializer, so they can be restored at
any time with `manage.py loaddata <file>` (gzip is supported natively).

USAGE:
    # Archive logs older than 90 days (default) into backup/activity_logs/
    python manage.py archive_activity_logs

    # Custom retention window
    python manage.py archive_activity_logs --days 60

    # Preview only — writes nothing, deletes nothing
    python manage.py archive_activity_logs --days 90 --dry-run

    # Custom output directory
    python manage.py archive_activity_logs --output-dir /path/to/archives

RESTORE (when you need the data back):
    python manage.py loaddata backup/activity_logs/user_activity_YYYYMMDD_HHMMSS.json.gz
"""
import gzip
import os
from datetime import timedelta

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from users.models import UserActivityLog


class Command(BaseCommand):
    help = "Archive UserActivityLog rows older than N days to compressed JSON, then delete only those archived rows."

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Archive logs OLDER than this many days (default: 90).',
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default=None,
            help='Directory to write archives to (default: <BASE_DIR>/backup/activity_logs).',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=5000,
            help='Number of rows to delete per batch after archiving (default: 5000).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be archived/deleted without writing or deleting anything.',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        if days < 0:
            self.stderr.write(self.style.ERROR('--days must be >= 0.'))
            return

        cutoff = timezone.now() - timedelta(days=days)

        qs = UserActivityLog.objects.filter(timestamp__lt=cutoff).order_by('timestamp')
        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                f'No user activity logs older than {days} day(s) (before {cutoff:%Y-%m-%d %H:%M}). Nothing to archive.'
            ))
            return

        self.stdout.write(
            f'Found {total} user activity log(s) older than {days} day(s) '
            f'(before {cutoff:%Y-%m-%d %H:%M}).'
        )

        if dry_run:
            oldest = qs.first()
            newest = qs.last()
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] Would archive {total} row(s) '
                f'(from {oldest.timestamp:%Y-%m-%d} to {newest.timestamp:%Y-%m-%d}) and then delete them. '
                f'No files written, no rows deleted.'
            ))
            return

        # Resolve output directory
        output_dir = options['output_dir'] or os.path.join(settings.BASE_DIR, 'backup', 'activity_logs')
        os.makedirs(output_dir, exist_ok=True)

        timestamp_tag = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'user_activity_{timestamp_tag}.json.gz'
        filepath = os.path.join(output_dir, filename)

        # Capture the exact IDs we are archiving so we only delete what we saved.
        archived_ids = list(qs.values_list('id', flat=True))

        # Write the archive first. Only touch the DB after the file is safely on disk.
        try:
            with gzip.open(filepath, 'wt', encoding='utf-8') as fh:
                serializers.serialize(
                    'json',
                    UserActivityLog.objects.filter(id__in=archived_ids).order_by('timestamp'),
                    stream=fh,
                    indent=2,
                )
        except Exception as exc:
            # If anything fails while writing, remove the partial file and abort — no deletion happens.
            if os.path.exists(filepath):
                os.remove(filepath)
            self.stderr.write(self.style.ERROR(f'Failed to write archive; aborting without deleting. Error: {exc}'))
            return

        file_size = os.path.getsize(filepath)
        self.stdout.write(self.style.SUCCESS(
            f'Archived {len(archived_ids)} row(s) to {filepath} ({file_size / 1024:.1f} KB).'
        ))

        # Delete only the archived rows, in batches, inside a transaction.
        deleted_total = 0
        with transaction.atomic():
            for start in range(0, len(archived_ids), batch_size):
                chunk = archived_ids[start:start + batch_size]
                deleted_count, _ = UserActivityLog.objects.filter(id__in=chunk).delete()
                deleted_total += deleted_count

        self.stdout.write(self.style.SUCCESS(
            f'Deleted {deleted_total} archived row(s) from the live table. '
            f'Restore anytime with:\n'
            f'    python manage.py loaddata {filepath}'
        ))
