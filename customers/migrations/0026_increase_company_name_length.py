from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0025_alter_customer_industry_alter_customer_territory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='company_name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='customer',
            name='phone_number',
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AlterField(
            model_name='customercreaterequest',
            name='company_name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='customercreaterequest',
            name='phone_number',
            field=models.CharField(max_length=100, blank=True),
        ),
    ]
