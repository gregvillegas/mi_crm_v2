from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales_proposals', '0034_proposal_use_availability_column'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='show_vat',
            field=models.BooleanField(
                default=False,
                help_text='Show VAT 12% line in the proposal (most proposals exclude VAT)',
            ),
        ),
    ]
