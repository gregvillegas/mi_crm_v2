"""
Fix customer records where the Spanish ñ was corrupted into a dash during a
past non-UTF-8 CSV import (e.g. "PARA—AQUE" should be "PARAÑAQUE").

The corruption signature is unambiguous: an em-dash (—) or en-dash (–) sitting
BETWEEN two letters is always a mangled ñ. Company/contact/address fields are
checked. Stored data is only changed when you pass --apply; by default the
command runs as a preview (dry run).

Safety:
  - Dry run by default. Nothing is written unless you pass --apply.
  - Each affected customer is backed up (create_backup) before editing.
  - Every change is recorded in CustomerHistory (action='field_updated').
  - All writes happen inside a single transaction.

Usage:
    # Preview every proposed change (no writes):
    python manage.py fix_corrupted_names

    # Apply the fixes:
    python manage.py fix_corrupted_names --apply

    # Also fix the lowercase form (letter–letter -> letter n letter is NOT done;
    # we always restore ñ). Limit to specific fields if needed:
    python manage.py fix_corrupted_names --fields address --apply
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from customers.models import Customer, CustomerHistory


# An em-dash or en-dash between two ASCII letters == a corrupted ñ.
# Capture the surrounding letters so we can choose Ñ vs ñ based on their case.
_DASH_BETWEEN_LETTERS = re.compile(r'([A-Za-z])[—–]([A-Za-z])')

FIELDS = ['company_name', 'contact_person_name', 'address']


def _replace_dash(match):
    """
    Restore the ñ using case-aware logic:
      - If both neighboring letters are uppercase -> 'Ñ'  (e.g. PARA—AQUE -> PARAÑAQUE)
      - Otherwise -> 'ñ'                                    (e.g. Para—aque -> Parañaque)
    """
    left, right = match.group(1), match.group(2)
    enye = 'Ñ' if (left.isupper() and right.isupper()) else 'ñ'
    return f'{left}{enye}{right}'


def _fix_value(value):
    """Return (fixed_value, changed) for a single field value."""
    if not value:
        return value, False
    fixed = _DASH_BETWEEN_LETTERS.sub(_replace_dash, value)
    return fixed, (fixed != value)


class Command(BaseCommand):
    help = "Restore ñ in customer names/addresses corrupted into dashes by a past bad import."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually write the corrections. Without this flag the command only previews (dry run).',
        )
        parser.add_argument(
            '--fields',
            nargs='+',
            choices=FIELDS,
            default=FIELDS,
            help=f'Which fields to check/fix (default: all of {", ".join(FIELDS)}).',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        fields = options['fields']

        # Build the list of affected customers and their proposed changes.
        affected = []  # list of dicts: {customer, changes: [(field, old, new)]}
        for c in Customer.objects.all().only('id', *FIELDS):
            changes = []
            for f in fields:
                old = getattr(c, f, '') or ''
                new, changed = _fix_value(old)
                if changed:
                    changes.append((f, old, new))
            if changes:
                affected.append({'customer': c, 'changes': changes})

        if not affected:
            self.stdout.write(self.style.SUCCESS('No corrupted names found. Nothing to fix.'))
            return

        total_fields = sum(len(a['changes']) for a in affected)
        self.stdout.write(
            f'Found {len(affected)} customer(s) with {total_fields} corrupted field value(s):\n'
        )
        for entry in affected:
            c = entry['customer']
            self.stdout.write(self.style.WARNING(f'  Customer #{c.id}:'))
            for f, old, new in entry['changes']:
                self.stdout.write(f'      [{f}]')
                self.stdout.write(f'        - {old!r}')
                self.stdout.write(f'        + {new!r}')

        if not apply_changes:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE(
                '[DRY RUN] No changes were written. Re-run with --apply to save these corrections.'
            ))
            return

        # Apply — back up, edit, log, all in one transaction.
        updated_customers = 0
        updated_fields = 0
        with transaction.atomic():
            for entry in affected:
                c = entry['customer']
                # Snapshot before editing so the change is reversible.
                c.create_backup(changed_by=None, reason='Pre-fix backup (corrupted ñ restore)')
                for f, old, new in entry['changes']:
                    setattr(c, f, new)
                    CustomerHistory.log_customer_change(
                        customer=c,
                        action='field_updated',
                        description=f"Restored corrupted ñ in '{f}' (bad import cleanup).",
                        changed_by=None,
                        old_value={f: old},
                        new_value={f: new},
                    )
                    updated_fields += 1
                c.save(update_fields=fields)
                updated_customers += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done. Fixed {updated_fields} field value(s) across {updated_customers} customer(s). '
            f'Backups and history entries were created for each.'
        ))
