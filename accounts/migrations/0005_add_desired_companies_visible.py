from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_profile_bio_visible_profile_company_visible_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='desired_companies_visible',
            field=models.BooleanField(default=True),
        ),
    ]
