from django.db import migrations, models


class Migration(migrations.Migration):
    """
    - Updates BDO PHP default values to match actual bank details.
    - Adds php_bank_address, php_swift_code, php_branch_code fields (BDO PHP).
    - Adds BPI PHP bank fields: php_bpi_account_name, php_bpi_account_number,
      php_bpi_account_type, php_bpi_branch, php_bpi_bank_address, php_bpi_swift_code.
    - Adds usd_bank_name, usd_branch_code fields and updates USD defaults.
    - Existing proposals keep their stored values; only new proposals get updated defaults.
    """

    dependencies = [
        ('sales_proposals', '0035_proposal_show_vat'),
    ]

    operations = [
        # ----- BDO PHP: new supplementary fields -----
        migrations.AddField(
            model_name='proposal',
            name='php_bank_address',
            field=models.CharField(
                max_length=300,
                default='Golden Rock Bldg, 168 Salcedo, Legaspi Village, Makati, 1229 Metro Manila',
            ),
        ),
        migrations.AddField(
            model_name='proposal',
            name='php_swift_code',
            field=models.CharField(max_length=50, default='BNORPHMM'),
        ),
        migrations.AddField(
            model_name='proposal',
            name='php_branch_code',
            field=models.CharField(max_length=20, default='00204'),
        ),
        # ----- BPI PHP: all new fields -----
        migrations.AddField(
            model_name='proposal',
            name='php_bpi_account_name',
            field=models.CharField(
                max_length=200, default='MICRO IMAGE INTERNATIONAL CORPORATION',
            ),
        ),
        migrations.AddField(
            model_name='proposal',
            name='php_bpi_account_number',
            field=models.CharField(max_length=100, default='0075-336527 (CURRENT)'),
        ),
        migrations.AddField(
            model_name='proposal',
            name='php_bpi_account_type',
            field=models.CharField(max_length=200, default='Current Account'),
        ),
        migrations.AddField(
            model_name='proposal',
            name='php_bpi_branch',
            field=models.CharField(max_length=200, default='LEGASPI-SALCEDO'),
        ),
        migrations.AddField(
            model_name='proposal',
            name='php_bpi_bank_address',
            field=models.CharField(
                max_length=300,
                default='Golden Rock Bldg, 168 Salcedo, Legaspi Village, Makati, 1229 Metro Manila',
            ),
        ),
        migrations.AddField(
            model_name='proposal',
            name='php_bpi_swift_code',
            field=models.CharField(max_length=50, default='BOPIPHMMXXX'),
        ),
        # ----- USD BDO: new supplementary fields -----
        migrations.AddField(
            model_name='proposal',
            name='usd_bank_name',
            field=models.CharField(max_length=200, default='Banco De Oro'),
        ),
        migrations.AddField(
            model_name='proposal',
            name='usd_branch_code',
            field=models.CharField(max_length=20, default='10204'),
        ),
        # ----- Update defaults on existing fields (alter_field) -----
        migrations.AlterField(
            model_name='proposal',
            name='php_bank_name',
            field=models.CharField(max_length=200, default='Banco De Oro'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='php_account_name',
            field=models.CharField(max_length=200, default='MICRO IMAGE INTERNATIONAL CORPORATION'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='php_account_number',
            field=models.CharField(max_length=100, default='00204-0042969 (SAVINGS)'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='php_account_type',
            field=models.CharField(max_length=200, default='Savings Account'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='php_branch',
            field=models.CharField(max_length=200, default='SALCEDO-DELA ROSA'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='usd_beneficiary_name',
            field=models.CharField(max_length=200, default='MICRO IMAGE INTERNATIONAL CORPORATION'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='usd_beneficiary_address',
            field=models.CharField(
                max_length=300,
                default='Unit 53 & 101 Legaspi Suites Building, 178 Salcedo St., Legaspi Village, Makati City 1229',
            ),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='usd_account_number',
            field=models.CharField(max_length=100, default='10204-0146004'),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='usd_bank_address',
            field=models.CharField(
                max_length=300,
                default='Golden Rock Bldg, 168 Salcedo, Legaspi Village, Makati, 1229 Metro Manila',
            ),
        ),
        migrations.AlterField(
            model_name='proposal',
            name='usd_swift_code',
            field=models.CharField(max_length=50, default='BNORPHMMXXX'),
        ),
    ]
