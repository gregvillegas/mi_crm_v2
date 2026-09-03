from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales_proposals', '0033_proposalemaillog'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='use_availability_column',
            field=models.BooleanField(
                default=True,
                help_text="Show 'Availability' column in the proposal (uncheck to show 'Warranty' column instead)",
            ),
        ),
    ]
