from django.core.management.base import BaseCommand
from sales_monitoring.models import ActivityType

class Command(BaseCommand):
    help = 'Populate default activity types for sales monitoring'

    def handle(self, *args, **options):
        activity_types = [
            {
                'name': 'Phone Call',
                'description': 'Cold calls, warm calls, follow-up calls, support calls, and other customer phone conversations.',
                'icon': 'fas fa-phone',
                'color': 'primary',
                'requires_customer': True,
            },
            {
                'name': 'Client Meeting',
                'description': 'Client-facing meetings such as initial meetings, demos, proposal presentations, negotiations, and closing meetings.',
                'icon': 'fas fa-handshake',
                'color': 'success',
                'requires_customer': True,
            },
            {
                'name': 'Email',
                'description': 'Email communications and follow-ups with customers.',
                'icon': 'fas fa-envelope',
                'color': 'info',
                'requires_customer': True,
            },
            {
                'name': 'Proposals',
                'description': 'Creating, revising, and sending formal sales proposals and quotations.',
                'icon': 'fas fa-file-contract',
                'color': 'warning',
                'requires_customer': True,
            },
            {
                'name': 'Product Demo',
                'description': 'Product demonstrations, technical presentations, and proof-of-concept showcases.',
                'icon': 'fas fa-desktop',
                'color': 'purple',
                'requires_customer': True,
            },
            {
                'name': 'Site Visit',
                'description': 'On-site customer visits for assessment, delivery, installation, or relationship building.',
                'icon': 'fas fa-building',
                'color': 'dark',
                'requires_customer': True,
            },
            {
                'name': 'Follow-up',
                'description': 'Follow-up activities after initial contact, proposal submission, or post-sale check-in.',
                'icon': 'fas fa-redo',
                'color': 'secondary',
                'requires_customer': True,
            },
            {
                'name': 'Negotiation',
                'description': 'Price negotiation, contract terms discussion, and deal-closing conversations.',
                'icon': 'fas fa-comments-dollar',
                'color': 'danger',
                'requires_customer': True,
            },
            {
                'name': 'Technical Consultation',
                'description': 'Technical requirement gathering, solution design, and pre-sales engineering support.',
                'icon': 'fas fa-cogs',
                'color': 'info',
                'requires_customer': True,
            },
            {
                'name': 'Lead Generation',
                'description': 'Prospecting, cold outreach, event attendance, and networking for new business.',
                'icon': 'fas fa-user-plus',
                'color': 'success',
                'requires_customer': False,
            },
            {
                'name': 'Training',
                'description': 'Product training, vendor certification sessions, or internal knowledge sharing.',
                'icon': 'fas fa-chalkboard-teacher',
                'color': 'warning',
                'requires_customer': False,
            },
            {
                'name': 'Internal Task',
                'description': 'Administrative work, report preparation, CRM updates, and team coordination.',
                'icon': 'fas fa-clipboard-check',
                'color': 'secondary',
                'requires_customer': False,
            },
        ]

        created_count = 0
        for activity_data in activity_types:
            activity_type, created = ActivityType.objects.get_or_create(
                name=activity_data['name'],
                defaults=activity_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  + Created: {activity_type.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'  ✓ Already exists: {activity_type.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nDone. Created {created_count} new activity types. Total: {ActivityType.objects.count()}')
        )
