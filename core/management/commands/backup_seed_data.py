"""
Management command: backup_seed_data

Exports only the data needed to seed a fresh production database:
  - auth.Group              (Django permission groups)
  - users.User              (all CRM users, no activity logs)
  - teams.Team              (sales teams)
  - teams.Group             (sales groups inside teams)
  - teams.TeamMembership    (which user belongs to which group)
  - lead_generation.LeadSource  (lead source definitions)

Usage:
    python manage.py backup_seed_data
    python manage.py backup_seed_data --output /path/to/seed.json
    python manage.py backup_seed_data --exclude-lead-sources
    python manage.py backup_seed_data --indent 4
"""

import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand
from django.core.serializers import serialize
from django.contrib.auth.models import Group as AuthGroup
from users.models import User
from teams.models import Team, Group as SalesGroup, TeamMembership
from lead_generation.models import LeadSource


class Command(BaseCommand):
    help = (
        'Backup seed data only: users, teams, groups, team memberships, '
        'and lead sources. Safe to import on a fresh production database.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', '-o',
            type=str,
            default=None,
            help=(
                'Output file path. '
                'Defaults to seed_backup_YYYY-MM-DD_HHMMSS.json in the project root.'
            ),
        )
        parser.add_argument(
            '--indent',
            type=int,
            default=2,
            help='JSON indentation level (default: 2).',
        )
        parser.add_argument(
            '--exclude-lead-sources',
            action='store_true',
            default=False,
            help='Exclude lead_generation.LeadSource records from the backup.',
        )
        parser.add_argument(
            '--exclude-team-memberships',
            action='store_true',
            default=False,
            help='Exclude teams.TeamMembership records from the backup.',
        )
        parser.add_argument(
            '--stdout',
            action='store_true',
            default=False,
            help='Print JSON to stdout instead of writing to a file.',
        )

    def handle(self, *args, **options):
        indent = options['indent']
        exclude_lead_sources = options['exclude_lead_sources']
        exclude_memberships = options['exclude_team_memberships']
        to_stdout = options['stdout']

        # ----------------------------------------------------------------
        # Collect querysets in dependency order
        # (referenced models must come before referencing models)
        # ----------------------------------------------------------------
        sections = [
            ('auth.Group (Django permission groups)',    AuthGroup.objects.all()),
            ('users.User',                               User.objects.all().order_by('id')),
            ('teams.Team',                               Team.objects.all().order_by('id')),
            ('teams.Group (sales groups)',               SalesGroup.objects.all().order_by('id')),
        ]

        if not exclude_memberships:
            sections.append(
                ('teams.TeamMembership', TeamMembership.objects.all().order_by('id'))
            )

        if not exclude_lead_sources:
            sections.append(
                ('lead_generation.LeadSource', LeadSource.objects.all().order_by('id'))
            )

        # ----------------------------------------------------------------
        # Serialize each queryset and merge into one JSON array
        # ----------------------------------------------------------------
        all_objects = []
        counts = {}

        for label, qs in sections:
            serialized = json.loads(
                serialize('json', qs, use_natural_foreign_keys=True, use_natural_primary_keys=True)
            )
            counts[label] = len(serialized)
            all_objects.extend(serialized)

        output_json = json.dumps(all_objects, indent=indent, ensure_ascii=False)

        # ----------------------------------------------------------------
        # Write output
        # ----------------------------------------------------------------
        if to_stdout:
            self.stdout.write(output_json)
        else:
            if options['output']:
                output_path = options['output']
            else:
                timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
                # __file__ = core/management/commands/backup_seed_data.py
                # go up 3 levels  → core/  → project root (BASE_DIR)
                project_root = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                )
                output_path = os.path.join(project_root, f'seed_backup_{timestamp}.json')

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output_json)

            self.stdout.write(self.style.SUCCESS(f'\nSeed backup written to: {output_path}'))

        # ----------------------------------------------------------------
        # Summary
        # ----------------------------------------------------------------
        self.stdout.write('\n' + '─' * 52)
        self.stdout.write(self.style.SUCCESS('  Seed Backup Summary'))
        self.stdout.write('─' * 52)
        for label, count in counts.items():
            self.stdout.write(f'  {label:<45} {count:>4} record(s)')
        self.stdout.write('─' * 52)
        self.stdout.write(f'  {"TOTAL":<45} {sum(counts.values()):>4} record(s)')
        self.stdout.write('─' * 52 + '\n')

        self.stdout.write(
            self.style.WARNING(
                'To import on the production server run:\n'
                '  python manage.py migrate --noinput\n'
                '  python manage.py loaddata <backup_file>.json\n'
            )
        )
