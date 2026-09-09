from django.db.models import Q

from teams.models import Group, TeamMembership
from users.models import User

from .models import Customer, CustomerCreateRequest


EXEC_ROLES = {'admin', 'president', 'gm', 'vp', 'marketing'}
ASSIGNABLE_ROLES = {'salesperson', 'supervisor', 'asm', 'sm', 'avp'}

# --- Customer create-request review model ---------------------------------
# There are three tiers of "seeing" a pending customer create-request:
#
#   GLOBAL_REVIEWER_ROLES  — see ALL pending requests, and may approve/reject.
#   APPROVER_ROLES         — may approve/reject requests within their scope
#                            (global for execs; own team for AVP).
#   WATCHER_ROLES          — may SEE requests within their scope for awareness,
#                            but may NOT approve/reject (decision stays with the
#                            AVP/executive).
#
# To let a watcher role approve later, simply move it into APPROVER_ROLES.
GLOBAL_REVIEWER_ROLES = {'admin', 'gm', 'vp', 'marketing'}
APPROVER_ROLES = GLOBAL_REVIEWER_ROLES | {'avp'}
WATCHER_ROLES = {'supervisor', 'sm', 'asm'}
# Anyone who can see the pending queue at all (approvers + watchers).
REQUEST_REVIEWER_ROLES = APPROVER_ROLES | WATCHER_ROLES


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

    if user.role == 'sm':
        # SM is scoped to their explicitly assigned groups only — derive team IDs from those
        team_ids.update(
            user.sm_groups.values_list('team_id', flat=True)
        )

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

    if user.role == 'avp':
        team_ids = get_user_team_ids(user)
        if not team_ids:
            return Customer.objects.none()
        scoped_users = get_team_scoped_users(team_ids, roles=ASSIGNABLE_ROLES)
        return Customer.objects.filter(salesperson_id__in=scoped_users.values_list('id', flat=True))

    if user.role == 'asm':
        team_ids = get_user_team_ids(user)
        if not team_ids:
            return Customer.objects.none()
        scoped_users = get_team_scoped_users(team_ids, roles=ASSIGNABLE_ROLES)
        return Customer.objects.filter(salesperson_id__in=scoped_users.values_list('id', flat=True))

    if user.role == 'sm':
        # SM sees only customers assigned to salespeople in their specifically assigned groups
        sm_groups = user.sm_groups.all()
        if not sm_groups.exists():
            return Customer.objects.none()
        member_ids = TeamMembership.objects.filter(group__in=sm_groups).values_list('user_id', flat=True)
        # Also include supervisors of those groups and the SM themselves if they hold customers
        supervisor_ids = Group.objects.filter(
            id__in=sm_groups.values_list('id', flat=True),
            supervisor__isnull=False
        ).values_list('supervisor_id', flat=True)
        visible_ids = set(member_ids) | set(supervisor_ids) | {user.id}
        return Customer.objects.filter(salesperson_id__in=visible_ids)

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


def _managed_requester_ids(user):
    """
    Set of user IDs whose customer create-requests this manager is scoped to see.
    Mirrors each role's customer visibility so the notification scope matches the
    data scope.

    - avp / asm: salespeople (and other assignable users) within their team(s).
    - supervisor / teamlead: members of the groups they manage/lead.
    - sm: members of their explicitly assigned groups (+ those groups' supervisors).
    Returns an empty set if the manager has no resolvable scope.
    """
    role = getattr(user, 'role', None)

    if role in {'avp', 'asm'}:
        team_ids = get_user_team_ids(user)
        if not team_ids:
            return set()
        return set(get_team_scoped_users(team_ids).values_list('id', flat=True))

    if role == 'supervisor':
        groups = Group.objects.filter(supervisor=user)
        member_ids = TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True)
        return set(member_ids) | {user.id}

    if role == 'teamlead':
        groups = Group.objects.filter(teamlead=user)
        member_ids = TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True)
        return set(member_ids) | {user.id}

    if role == 'sm':
        sm_groups = user.sm_groups.all()
        if not sm_groups.exists():
            return set()
        member_ids = TeamMembership.objects.filter(group__in=sm_groups).values_list('user_id', flat=True)
        supervisor_ids = Group.objects.filter(
            id__in=sm_groups.values_list('id', flat=True),
            supervisor__isnull=False,
        ).values_list('supervisor_id', flat=True)
        return set(member_ids) | set(supervisor_ids) | {user.id}

    return set()


def can_review_customer_requests(user):
    """
    True if this user may SEE the pending customer create-request queue
    (approvers AND watchers). Watchers can view but not approve/reject.
    """
    return getattr(user, 'is_authenticated', False) and user.role in REQUEST_REVIEWER_ROLES


def can_approve_customer_requests(user):
    """True if this user may APPROVE/REJECT customer create-requests."""
    return getattr(user, 'is_authenticated', False) and user.role in APPROVER_ROLES


def pending_requests_for_reviewer(user):
    """
    Return the pending CustomerCreateRequest queryset this user is allowed to SEE.

    - admin/gm/vp/marketing: ALL pending requests (global).
    - avp/asm/supervisor/teamlead/sm: only requests raised by users within their
      own team/group scope. A manager with no resolvable scope sees nothing.
    - anyone else: nothing.
    """
    if not can_review_customer_requests(user):
        return CustomerCreateRequest.objects.none()

    base = CustomerCreateRequest.objects.filter(status='pending')

    if user.role in GLOBAL_REVIEWER_ROLES:
        return base

    requester_ids = _managed_requester_ids(user)
    if not requester_ids:
        return CustomerCreateRequest.objects.none()
    return base.filter(requested_by_id__in=requester_ids)


def can_review_request(user, req):
    """True if this user may SEE a specific create-request (approver or watcher)."""
    if not can_review_customer_requests(user):
        return False
    if user.role in GLOBAL_REVIEWER_ROLES:
        return True
    if not req.requested_by_id:
        return False
    return req.requested_by_id in _managed_requester_ids(user)


def can_approve_request(user, req):
    """True if this user may APPROVE/REJECT a specific create-request."""
    if not can_approve_customer_requests(user):
        return False
    if user.role in GLOBAL_REVIEWER_ROLES:
        return True
    # AVP — only within their team scope.
    if not req.requested_by_id:
        return False
    return req.requested_by_id in _managed_requester_ids(user)

