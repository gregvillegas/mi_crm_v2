from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0023_alter_customer_industry_alter_customer_territory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='email',
            field=models.EmailField(max_length=254),
        ),
    ]

