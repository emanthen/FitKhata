import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gyms', '0002_organization_vat_inclusive_pricing'),
        ('members', '0004_member_language_email_notifications_opt_out'),
    ]

    operations = [
        migrations.CreateModel(
            name='MemberFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('message', models.TextField(max_length=1000)),
                ('gym', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='gyms.gym')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedback', to='members.member')),
                ('org', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='gyms.organization')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
