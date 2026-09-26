from django.db.models import Q
from teams.models import Group, TeamMembership, asm_scoped_groups
from users.models import User
from .models import Proposal


EXEC_ROLES = {'admin', 'president', 'gm', 'vp', 'marketing'}


def _proposal_member_ids_from_groups(groups):
    groups = list(groups)
    if not groups:
        return set()
    group_ids = [g.id for g in groups]
    member_ids = set(TeamMembership.objects.filter(group_id__in=group_ids).values_list('user_id', flat=True))
    supervisor_ids = set(Group.objects.filter(id__in=group_ids, supervisor__isnull=False).values_list('supervisor_id', flat=True))
    return member_ids | supervisor_ids


def visible_proposals_queryset(user):
    if not getattr(user, 'is_authenticated', False):
        return Proposal.objects.none()

    if user.role in EXEC_ROLES:
        return Proposal.objects.all()

    if user.role == 'salesperson':
        return Proposal.objects.filter(created_by=user)

    if user.role == 'supervisor':
        managed_groups = user.managed_groups.all()
        visible_ids = _proposal_member_ids_from_groups(managed_groups)
        visible_ids.add(user.id)
        if not visible_ids:
            return Proposal.objects.none()
        return Proposal.objects.filter(created_by_id__in=visible_ids)

    if user.role == 'teamlead':
        led_groups = user.led_groups.all()
        visible_ids = _proposal_member_ids_from_groups(led_groups)
        visible_ids.add(user.id)
        if not visible_ids:
            return Proposal.objects.none()
        return Proposal.objects.filter(created_by_id__in=visible_ids)

    if user.role == 'asm':
        asm_groups = asm_scoped_groups(user)
        visible_ids = _proposal_member_ids_from_groups(asm_groups)
        visible_ids.add(user.id)
        if not visible_ids:
            return Proposal.objects.none()
        return Proposal.objects.filter(created_by_id__in=visible_ids)

    if user.role == 'sm':
        sm_groups = user.sm_groups.all()
        visible_ids = _proposal_member_ids_from_groups(sm_groups)
        visible_ids.add(user.id)
        if not visible_ids:
            return Proposal.objects.none()
        return Proposal.objects.filter(created_by_id__in=visible_ids)

    if user.role == 'avp':
        managed_teams = user.managed_teams.all()
        if not managed_teams.exists():
            return Proposal.objects.none()
        groups = Group.objects.filter(team__in=managed_teams)
        visible_ids = _proposal_member_ids_from_groups(groups)
        sm_ids = set(groups.values_list('sm_managers__id', flat=True))
        asm_ids = set(managed_teams.exclude(asm__isnull=True).values_list('asm_id', flat=True))
        visible_ids = visible_ids | sm_ids | asm_ids | {user.id}
        visible_ids.discard(None)
        if not visible_ids:
            return Proposal.objects.none()
        return Proposal.objects.filter(created_by_id__in=visible_ids)

    return Proposal.objects.none()
