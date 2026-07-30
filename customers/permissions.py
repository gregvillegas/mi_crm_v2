from django.db.models import Q

from teams.models import Group, TeamMembership
from users.models import User

from .models import Customer


EXEC_ROLES = {'admin', 'president', 'gm', 'vp', 'marketing'}
ASSIGNABLE_ROLES = {'salesperson', 'supervisor', 'asm', 'sm', 'avp'}


def _safe_team_id_from_membership(user):
    try:
        return user.team_membership.group.team_id
    except Exception:
        return None


def get_user_team_ids(user):
    if not getattr(user, 'is_authenticated', False):
        return set()

    team_ids = set()

    membership_team_id = _safe_team_id_from_membership(user)
    if membership_team_id:
        team_ids.add(membership_team_id)

    if user.role == 'avp':
        team_ids.update(user.managed_teams.values_list('id', flat=True))

    if user.role == 'asm':
        team_ids.update(user.asm_teams.values_list('id', flat=True))

    if user.role == 'supervisor':
        team_ids.update(Group.objects.filter(supervisor=user).values_list('team_id', flat=True))

    if user.role == 'teamlead':
        team_ids.update(Group.objects.filter(teamlead=user).values_list('team_id', flat=True))

    return {int(tid) for tid in team_ids if tid}


def get_user_group_ids(user):
    if not getattr(user, 'is_authenticated', False):
        return set()

    group_ids = set()

    try:
        group_ids.add(user.team_membership.group_id)
    except Exception:
        pass

    if user.role == 'supervisor':
        group_ids.update(user.managed_groups.values_list('id', flat=True))

    return {int(gid) for gid in group_ids if gid}


def get_team_scoped_users(team_ids, roles=None):
    if not team_ids:
        return User.objects.none()

    q = (
        Q(team_membership__group__team_id__in=team_ids)
        | Q(managed_groups__team_id__in=team_ids)
        | Q(asm_teams__id__in=team_ids)
        | Q(managed_teams__id__in=team_ids)
    )
    qs = User.objects.filter(is_active=True).filter(q).distinct()
    if roles:
        qs = qs.filter(role__in=list(roles))
    return qs


def can_manage_role(actor_role, target_role):
    if actor_role in EXEC_ROLES:
        return True
    if actor_role == target_role:
        return False
    if actor_role == 'avp':
        return target_role in {'asm', 'sm', 'supervisor', 'salesperson'}
    if actor_role == 'sm':
        return target_role in {'asm', 'supervisor', 'salesperson'}
    if actor_role == 'asm':
        return target_role in {'supervisor', 'salesperson'}
    if actor_role == 'supervisor':
        return target_role == 'salesperson'
    return False


def visible_customers_queryset(user):
    if not getattr(user, 'is_authenticated', False):
        return Customer.objects.none()

    if user.role in EXEC_ROLES:
        return Customer.objects.all()

    if user.role == 'salesperson':
        return Customer.objects.filter(salesperson=user)

    if user.role == 'supervisor':
        groups = Group.objects.filter(supervisor=user)
        member_ids = TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True)
        return Customer.objects.filter(Q(salesperson_id__in=member_ids) | Q(salesperson=user))

    if user.role == 'teamlead':
        groups = Group.objects.filter(teamlead=user)
        member_ids = TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True)
        return Customer.objects.filter(Q(salesperson_id__in=member_ids) | Q(salesperson=user))

    if user.role in {'avp', 'asm', 'sm'}:
        team_ids = get_user_team_ids(user)
        if not team_ids:
            return Customer.objects.none()

        scoped_users = get_team_scoped_users(team_ids, roles=ASSIGNABLE_ROLES)
        return Customer.objects.filter(salesperson_id__in=scoped_users.values_list('id', flat=True))

    return Customer.objects.none()


def can_view_customer(user, customer):
    if user.role in EXEC_ROLES:
        return True
    return visible_customers_queryset(user).filter(pk=customer.pk).exists()


def can_edit_customer(user, customer):
    if user.role in EXEC_ROLES:
        return True

    assigned = customer.salesperson
    if not assigned:
        return False

    if assigned_id := getattr(assigned, 'id', None):
        if assigned_id == user.id:
            return True

    if user.role == 'salesperson':
        return False

    if user.role == 'supervisor':
        groups = Group.objects.filter(supervisor=user)
        member_ids = TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True)
        return assigned.id in set(member_ids) and can_manage_role('supervisor', assigned.role)

    if user.role == 'teamlead':
        groups = Group.objects.filter(teamlead=user)
        member_ids = TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True)
        return assigned.id in set(member_ids) and can_manage_role('supervisor', assigned.role)

    if user.role in {'avp', 'asm', 'sm'}:
        team_ids = get_user_team_ids(user)
        if not team_ids:
            return False
        if not get_team_scoped_users(team_ids).filter(id=assigned.id).exists():
            return False
        return can_manage_role(user.role, assigned.role)

    return False


def assignment_targets_queryset(user):
    if user.role in EXEC_ROLES:
        return User.objects.filter(is_active=True, role__in=list(ASSIGNABLE_ROLES)).order_by('first_name', 'last_name', 'username')

    if user.role == 'salesperson':
        return User.objects.filter(id=user.id)

    if user.role == 'supervisor':
        groups = Group.objects.filter(supervisor=user)
        member_ids = TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True)
        return User.objects.filter(is_active=True).filter(Q(id=user.id) | Q(id__in=member_ids)).order_by('first_name', 'last_name', 'username')

    if user.role == 'teamlead':
        groups = Group.objects.filter(teamlead=user)
        member_ids = TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True)
        return User.objects.filter(is_active=True).filter(Q(id=user.id) | Q(id__in=member_ids)).order_by('first_name', 'last_name', 'username')

    if user.role in {'avp', 'asm', 'sm'}:
        team_ids = get_user_team_ids(user)
        qs = get_team_scoped_users(team_ids, roles=ASSIGNABLE_ROLES)
        return qs.order_by('first_name', 'last_name', 'username')

    return User.objects.none()

