from django.db import migrations


# Data migration: assign the two ASMs (whose job title is "Sales Manager") to the
# specific groups they handle, so the new sm_groups-scoped visibility restricts
# them to only those groups.
#
#   csenador (ASM, TEAM A) -> CSG-C, CSG-D
#   scereno  (ASM, TEAM B) -> CSG-G, CSG-H
#
# Matching is by username + group name and is idempotent (add() is a no-op if the
# link already exists). Missing users/groups are skipped safely so this migration
# never fails on an environment where the data differs.

ASSIGNMENTS = {
    'csenador': ['CSG-C', 'CSG-D'],
    'scereno': ['CSG-G', 'CSG-H'],
}


def assign_asm_groups(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Group = apps.get_model('teams', 'Group')

    for username, group_names in ASSIGNMENTS.items():
        user = User.objects.filter(username=username).first()
        if not user:
            continue
        for group_name in group_names:
            group = Group.objects.filter(name=group_name).first()
            if not group:
                continue
            group.sm_managers.add(user)


def unassign_asm_groups(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Group = apps.get_model('teams', 'Group')

    for username, group_names in ASSIGNMENTS.items():
        user = User.objects.filter(username=username).first()
        if not user:
            continue
        for group_name in group_names:
            group = Group.objects.filter(name=group_name).first()
            if not group:
                continue
            group.sm_managers.remove(user)


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0017_alter_group_sm_managers'),
    ]

    operations = [
        migrations.RunPython(assign_asm_groups, unassign_asm_groups),
    ]
