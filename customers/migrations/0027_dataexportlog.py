from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('customers', '0026_increase_company_name_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataExportLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('export_type', models.CharField(choices=[('customers', 'Customers'), ('customers_with_contacts', 'Customers + Contacts'), ('delinquents', 'Delinquent Accounts'), ('sales_funnel', 'Sales Funnel'), ('other', 'Other')], default='customers', max_length=40)),
                ('record_count', models.PositiveIntegerField(default=0, help_text='Number of records exported')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=500)),
                ('exported_at', models.DateTimeField(auto_now_add=True)),
                ('exported_by', models.ForeignKey(help_text='The user who performed the export', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='data_exports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Data Export Log',
                'verbose_name_plural': 'Data Export Logs',
                'ordering': ['-exported_at'],
            },
        ),
        migrations.AddIndex(
            model_name='dataexportlog',
            index=models.Index(fields=['-exported_at'], name='customers_d_exporte_idx'),
        ),
        migrations.AddIndex(
            model_name='dataexportlog',
            index=models.Index(fields=['exported_by', '-exported_at'], name='customers_d_exp_by_idx'),
        ),
    ]
