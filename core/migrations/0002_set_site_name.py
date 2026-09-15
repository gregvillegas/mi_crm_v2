from django.conf import settings
from django.db import migrations


# Set the django.contrib.sites Site to the real system identity so allauth stops
# using the default "example.com" in password-reset email subjects/bodies/links.
#   name   -> drives the "[MI CRM] ..." subject prefix and "from MI CRM" wording
#   domain -> used for links in emails
SITE_NAME = 'MI CRM'
SITE_DOMAIN = 'micrm.microimageph.com'


def set_site(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    site_id = getattr(settings, 'SITE_ID', 1)
    site, _ = Site.objects.get_or_create(id=site_id)
    site.name = SITE_NAME
    site.domain = SITE_DOMAIN
    site.save()


def revert_site(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    site_id = getattr(settings, 'SITE_ID', 1)
    Site.objects.filter(id=site_id).update(name='example.com', domain='example.com')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(set_site, revert_site),
    ]
