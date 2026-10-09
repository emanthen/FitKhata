import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0005_memberfeedback'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='referred_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals', to='members.member'),
        ),
    ]
