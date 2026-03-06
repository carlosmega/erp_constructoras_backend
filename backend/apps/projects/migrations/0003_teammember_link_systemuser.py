"""
Migration: Link ProjectTeamMember to SystemUser.

1. Delete all existing team member records (test data only)
2. Remove old text fields (name, phone, email)
3. Add systemuserid FK to SystemUser
4. Add unique constraint (projectid, systemuserid)
5. Update ordering
"""

from django.db import migrations, models
import django.db.models.deletion


def delete_existing_team_members(apps, schema_editor):
    """Delete all existing team member records (test data)."""
    ProjectTeamMember = apps.get_model('projects', 'ProjectTeamMember')
    ProjectTeamMember.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_make_dates_nullable'),
        ('users', '0001_initial'),
    ]

    operations = [
        # Step 1: Delete existing test data
        migrations.RunPython(
            delete_existing_team_members,
            migrations.RunPython.noop,
        ),
        # Step 2: Remove old text fields
        migrations.RemoveField(
            model_name='projectteammember',
            name='name',
        ),
        migrations.RemoveField(
            model_name='projectteammember',
            name='phone',
        ),
        migrations.RemoveField(
            model_name='projectteammember',
            name='email',
        ),
        # Step 3: Add systemuserid FK
        migrations.AddField(
            model_name='projectteammember',
            name='systemuserid',
            field=models.ForeignKey(
                db_column='systemuserid',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='team_memberships',
                to='users.systemuser',
            ),
            preserve_default=False,
        ),
        # Step 4: Add unique constraint
        migrations.AddConstraint(
            model_name='projectteammember',
            constraint=models.UniqueConstraint(
                fields=['projectid', 'systemuserid'],
                name='unique_team_member_per_project',
            ),
        ),
        # Step 5: Update ordering
        migrations.AlterModelOptions(
            name='projectteammember',
            options={
                'ordering': ['systemuserid__fullname'],
                'verbose_name': 'Project Team Member',
                'verbose_name_plural': 'Project Team Members',
            },
        ),
    ]
