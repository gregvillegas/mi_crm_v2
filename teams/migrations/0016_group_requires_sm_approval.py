from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0015_group_sm_managers'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='requires_sm_approval',
            field=models.BooleanField(
                default=False,
                help_text='If checked, proposals from this group require SM approval before AVP.',
            ),
        ),
    ]
