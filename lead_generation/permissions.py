from django.db.models import Q
from teams.models import Group
from users.models import User
from .models import Lead


EXEC_ROLES = {'admin', 'president', 'gm', 'vp', 'marketing'}


def _salespeople_in_groups(groups):
    groups = list(groups)
    if not groups:
        return User.objects.none()
    group_ids = [g.id for g in groups]
    return User.objects.filter(team_membership__group_id__in=group_ids, role='salesperson', is_active=True)


def visible_leads_queryset(user):
    if not getattr(user, 'is_authenticated', False):
        return Lead.objects.none()

    if user.role in EXEC_ROLES:
        return Lead.objects.filter(is_active=True)

    if user.role == 'salesperson':
        return Lead.objects.filter(assigned_to=user, is_active=True)

    if user.role == 'supervisor':
        groups = user.managed_groups.all()
        team_members = _salespeople_in_groups(groups)
        return Lead.objects.filter(assigned_to__in=team_members, is_active=True)

    if user.role == 'asm':
        groups = Group.objects.filter(team__in=user.asm_teams.all())
        team_members = _salespeople_in_groups(groups)
        return Lead.objects.filter(assigned_to__in=team_members, is_active=True)

    if user.role == 'sm':
        groups = user.sm_groups.all()
        team_members = _salespeople_in_groups(groups)
        return Lead.objects.filter(assigned_to__in=team_members, is_active=True)

    if user.role == 'avp':
        from teams.models import Team
        groups = Group.objects.filter(team__in=Team.objects.filter(avp=user))
        team_members = _salespeople_in_groups(groups)
        return Lead.objects.filter(assigned_to__in=team_members, is_active=True)

    if user.role == 'teamlead':
        groups = user.led_groups.all()
        team_members = _salespeople_in_groups(groups)
        return Lead.objects.filter(assigned_to__in=team_members, is_active=True)

    return Lead.objects.none()
