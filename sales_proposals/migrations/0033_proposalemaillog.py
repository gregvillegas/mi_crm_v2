from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sales_proposals', '0032_multi_option_proposal'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProposalEmailLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipients', models.TextField(help_text='Comma-separated To addresses')),
                ('cc', models.TextField(blank=True, help_text='Comma-separated CC addresses')),
                ('status', models.CharField(choices=[('sent', 'Sent'), ('failed', 'Failed')], max_length=10)),
                ('error_message', models.TextField(blank=True, help_text='Error details if send failed')),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('proposal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_logs', to='sales_proposals.proposal')),
                ('sent_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='proposal_emails_sent', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Proposal Email Log',
                'verbose_name_plural': 'Proposal Email Logs',
                'ordering': ['-sent_at'],
            },
        ),
    ]
