# -----------------------------------------------------------------------------
# 5. core/views.py (for handling login, logout, and home page)
# -----------------------------------------------------------------------------
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from django.urls import reverse
from sales_funnel.models import SalesFunnel
from teams.models import Team, Group, TeamMembership, asm_scoped_groups
from users.models import User
from customers.permissions import visible_customers_queryset
from sales_proposals.models import Proposal
from sales_proposals.permissions import visible_proposals_queryset
from lead_generation.models import Lead
from lead_generation.permissions import visible_leads_queryset
from gamification.models import UserMissionProgress
from gamification.utils import generate_daily_missions, generate_weekly_missions, get_current_week_start
from mass_mailing.models import Campaign, CampaignRecipient, MediaLibraryAsset, Announcement


def _visible_funnel_queryset(user):
    if not getattr(user, 'is_authenticated', False):
        return SalesFunnel.objects.none()

    EXEC_ROLES = {'admin', 'president', 'gm', 'vp', 'marketing'}
    if user.role in EXEC_ROLES:
        return SalesFunnel.objects.all()

    if user.role == 'salesperson':
        return SalesFunnel.objects.filter(salesperson=user)

    if user.role == 'supervisor':
        groups = Group.objects.filter(supervisor=user)
        member_ids = list(TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True))
        member_ids.append(user.id)
        return SalesFunnel.objects.filter(salesperson_id__in=member_ids)

    if user.role == 'teamlead':
        groups = Group.objects.filter(teamlead=user)
        member_ids = list(TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True))
        member_ids.append(user.id)
        return SalesFunnel.objects.filter(salesperson_id__in=member_ids)

    if user.role == 'asm':
        asm_groups = asm_scoped_groups(user)
        member_ids = list(TeamMembership.objects.filter(group__in=asm_groups).values_list('user_id', flat=True))
        supervisor_ids = list(Group.objects.filter(id__in=asm_groups.values_list('id', flat=True), supervisor__isnull=False).values_list('supervisor_id', flat=True))
        visible_ids = set(member_ids) | set(supervisor_ids) | {user.id}
        return SalesFunnel.objects.filter(Q(salesperson_id__in=visible_ids) | Q(salesperson=user))

    if user.role == 'sm':
        sm_groups = user.sm_groups.all()
        member_ids = list(TeamMembership.objects.filter(group__in=sm_groups).values_list('user_id', flat=True))
        supervisor_ids = list(Group.objects.filter(id__in=sm_groups.values_list('id', flat=True), supervisor__isnull=False).values_list('supervisor_id', flat=True))
        visible_ids = set(member_ids) | set(supervisor_ids) | {user.id}
        return SalesFunnel.objects.filter(Q(salesperson_id__in=visible_ids) | Q(salesperson=user))

    if user.role == 'avp':
        teams = Team.objects.filter(avp=user)
        groups = Group.objects.filter(team__in=teams)
        salespeople_ids = list(TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True))
        asm_ids = list(teams.exclude(asm__isnull=True).values_list('asm_id', flat=True))
        supervisor_ids = list(Group.objects.filter(team__in=teams, supervisor__isnull=False).values_list('supervisor_id', flat=True))
        sm_ids = list(groups.values_list('sm_managers__id', flat=True))
        visible_ids = set(salespeople_ids) | set(asm_ids) | set(supervisor_ids) | set(i for i in sm_ids if i) | {user.id}
        return SalesFunnel.objects.filter(Q(salesperson_id__in=visible_ids) | Q(salesperson=user))

    return SalesFunnel.objects.none()


def _visible_users_queryset(user):
    if not getattr(user, 'is_authenticated', False):
        return User.objects.none()

    EXEC_ROLES = {'admin', 'president', 'gm', 'vp', 'marketing'}
    if user.role in EXEC_ROLES:
        return User.objects.filter(is_active=True)

    if user.role == 'avp':
        from customers.permissions import get_user_team_ids, get_team_scoped_users
        ASSIGNABLE_ROLES = {'salesperson', 'supervisor', 'asm', 'sm', 'avp'}
        team_ids = get_user_team_ids(user)
        if not team_ids:
            return User.objects.filter(pk=user.pk)
        return get_team_scoped_users(team_ids, roles=ASSIGNABLE_ROLES) | User.objects.filter(pk=user.pk)

    if user.role in {'asm', 'sm'}:
        from customers.permissions import group_scoped_member_ids
        member_ids = group_scoped_member_ids(user)
        member_ids.add(user.id)
        if not member_ids:
            return User.objects.filter(pk=user.pk)
        return User.objects.filter(id__in=member_ids, is_active=True)

    if user.role in {'supervisor', 'teamlead'}:
        groups = Group.objects.filter(supervisor=user) if user.role == 'supervisor' else Group.objects.filter(teamlead=user)
        member_ids = set(TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True))
        member_ids.add(user.id)
        if not member_ids:
            return User.objects.filter(pk=user.pk)
        return User.objects.filter(id__in=member_ids, is_active=True)

    return User.objects.filter(pk=user.pk)


def _search_proposals(user, q, limit=20):
    qs = visible_proposals_queryset(user).filter(
        Q(proposal_number__icontains=q) |
        Q(reference_number__icontains=q) |
        Q(subject__icontains=q) |
        Q(customer__company_name__icontains=q) |
        Q(contact_name__icontains=q) |
        Q(contact_email__icontains=q) |
        Q(created_by__username__icontains=q) |
        Q(created_by__first_name__icontains=q) |
        Q(created_by__last_name__icontains=q)
    ).select_related('customer', 'created_by').order_by('-created_at')
    results = []
    for p in qs[:limit]:
        results.append({
            'obj': p,
            'title': f"{p.proposal_number}",
            'subtitle': f"{p.subject or '—'} • {p.customer.company_name if p.customer_id else '—'}",
            'meta': f"By {p.created_by.get_full_name() or p.created_by.username} • {p.date}",
            'url': reverse('proposal_detail', kwargs={'pk': p.pk}),
            'badge': p.get_status_display(),
            'badge_class': {
                'draft': 'bg-secondary',
                'sent': 'bg-primary',
                'accepted': 'bg-success',
                'declined': 'bg-danger',
                'expired': 'bg-warning text-dark',
            }.get(p.status, 'bg-secondary'),
        })
    return results


def _search_customers(user, q, limit=20):
    qs = visible_customers_queryset(user).filter(
        Q(company_name__icontains=q) |
        Q(contact_person_name__icontains=q) |
        Q(contact_person_position__icontains=q) |
        Q(email__icontains=q) |
        Q(phone_number__icontains=q) |
        Q(address__icontains=q)
    ).select_related('salesperson').order_by('-created_at')
    results = []
    for c in qs[:limit]:
        results.append({
            'obj': c,
            'title': c.company_name,
            'subtitle': f"{c.contact_person_name or '—'}{(' • ' + c.contact_person_position) if c.contact_person_position else ''}",
            'meta': f"{c.email or ''}{(' • ' + c.phone_number) if c.phone_number else ''}",
            'url': reverse('customer_detail', kwargs={'pk': c.pk}),
            'badge': c.display_status,
            'badge_class': 'bg-success' if c.is_effectively_active else 'bg-secondary',
        })
    return results


def _search_users(user, q, limit=20):
    qs = _visible_users_queryset(user).filter(
        Q(username__icontains=q) |
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q) |
        Q(email__icontains=q) |
        Q(initials__icontains=q) |
        Q(mobile_number__icontains=q)
    ).order_by('first_name', 'last_name', 'username')
    results = []
    for u in qs[:limit]:
        if user.role == 'admin':
            detail_url = reverse('edit_user', kwargs={'user_id': u.pk})
        else:
            detail_url = reverse('profile') if u.pk == user.pk else reverse('profile')
        results.append({
            'obj': u,
            'title': u.get_full_name() or u.username,
            'subtitle': f"@{u.username}",
            'meta': f"{u.get_role_display()}{(' • ' + u.get_job_title_display()) if u.job_title else ''}",
            'url': detail_url,
            'badge': u.get_role_display(),
            'badge_class': 'bg-info text-dark',
        })
    return results


def _search_leads(user, q, limit=20):
    if not hasattr(Lead, 'assigned_to'):
        return []
    qs = visible_leads_queryset(user).filter(
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q) |
        Q(company_name__icontains=q) |
        Q(email__icontains=q) |
        Q(phone_number__icontains=q)
    ).select_related('source', 'assigned_to').order_by('-created_at')
    results = []
    for l in qs[:limit]:
        full = " ".join(x for x in [l.first_name, l.last_name] if x) or l.company_name or "—"
        results.append({
            'obj': l,
            'title': full,
            'subtitle': f"{l.company_name or '—'}",
            'meta': f"{l.email or ''}{(' • ' + l.phone_number) if l.phone_number else ''}",
            'url': reverse('lead_generation:lead_detail', kwargs={'lead_id': l.pk}),
            'badge': l.get_status_display() if hasattr(l, 'get_status_display') else 'Lead',
            'badge_class': 'bg-warning text-dark',
        })
    return results


def _search_funnel(user, q, limit=20):
    qs = _visible_funnel_queryset(user).filter(
        Q(company_name__icontains=q) |
        Q(brand__icontains=q) |
        Q(requirement_description__icontains=q) |
        Q(salesperson__username__icontains=q) |
        Q(salesperson__first_name__icontains=q) |
        Q(salesperson__last_name__icontains=q)
    ).select_related('salesperson', 'customer').order_by('-date_created')
    results = []
    for f in qs[:limit]:
        results.append({
            'obj': f,
            'title': f.company_name,
            'subtitle': f"{f.brand or '—'}{(' • ' + f.requirement_description[:80]) if f.requirement_description else ''}",
            'meta': f"By {f.salesperson.get_full_name() or f.salesperson.username} • {f.date_created}",
            'url': reverse('sales_funnel:entry_detail', kwargs={'entry_id': f.pk}),
            'badge': f.get_stage_display() if hasattr(f, 'get_stage_display') else 'Funnel',
            'badge_class': {
                'quoted': 'bg-pink',
                'closable': 'bg-warning text-dark',
                'project': 'bg-success',
                'services': 'bg-primary',
            }.get(getattr(f, 'stage', ''), 'bg-secondary'),
        })
    return results


@login_required
def global_search(request):
    query = request.GET.get('q', '').strip()
    context = {
        'query': query,
        'sections': [],
        'total_count': 0,
    }

    if not query or len(query) < 1:
        return render(request, 'core/search_results.html', context)

    sections = []

    proposals = _search_proposals(request.user, query)
    if proposals:
        sections.append({
            'key': 'proposals',
            'label': 'Proposals',
            'icon': 'fas fa-file-invoice-dollar',
            'color': 'primary',
            'items': proposals,
            'count': len(proposals),
        })
        context['total_count'] += len(proposals)

    customers = _search_customers(request.user, query)
    if customers:
        sections.append({
            'key': 'customers',
            'label': 'Customers',
            'icon': 'fas fa-users',
            'color': 'success',
            'items': customers,
            'count': len(customers),
        })
        context['total_count'] += len(customers)

    users = _search_users(request.user, query)
    if users:
        sections.append({
            'key': 'users',
            'label': 'Users',
            'icon': 'fas fa-user-circle',
            'color': 'info',
            'items': users,
            'count': len(users),
        })
        context['total_count'] += len(users)

    leads = _search_leads(request.user, query)
    if leads:
        sections.append({
            'key': 'leads',
            'label': 'Leads',
            'icon': 'fas fa-user-plus',
            'color': 'warning',
            'items': leads,
            'count': len(leads),
        })
        context['total_count'] += len(leads)

    funnel = _search_funnel(request.user, query)
    if funnel:
        sections.append({
            'key': 'funnel',
            'label': 'Sales Funnel',
            'icon': 'fas fa-filter',
            'color': 'pink',
            'items': funnel,
            'count': len(funnel),
        })
        context['total_count'] += len(funnel)

    context['sections'] = sections
    return render(request, 'core/search_results.html', context)

@login_required
def home(request):
    user = request.user
    context = {'user': user}
    
    # Gamification: Get Daily Missions
    today = timezone.now().date()
    week_start = get_current_week_start(today)

    generate_daily_missions(user)
    generate_weekly_missions(user)

    my_missions = UserMissionProgress.objects.filter(
        user=user
    ).filter(
        Q(mission__mission_type='daily', date_assigned=today) |
        Q(mission__mission_type='weekly', date_assigned=week_start)
    ).select_related('mission').order_by('mission__mission_type', 'mission__title')
    
    context['my_missions'] = my_missions
    
    # Add sales funnel data for eligible users
    if user.role in ['salesperson', 'supervisor', 'teamlead', 'asm', 'avp', 'admin', 'president', 'gm', 'vp']:
        # Get funnel entries based on user role
        if user.role == 'salesperson':
            funnel_entries = SalesFunnel.objects.filter(
                salesperson=user,
                is_active=True,
                is_closed=False
            )
        elif user.role == 'supervisor':
            # Supervisor can see entries from their groups (members + self)
            groups = Group.objects.filter(supervisor=user)
            salespeople_ids = list(TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True))
            salespeople_ids.append(user.id)
            funnel_entries = SalesFunnel.objects.filter(
                salesperson_id__in=salespeople_ids,
                is_active=True,
                is_closed=False
            )
        elif user.role == 'teamlead':
            # Teamlead can see entries from their assigned group
            teamlead_groups = Group.objects.filter(teamlead=user)
            salespeople_ids = TeamMembership.objects.filter(group__in=teamlead_groups).values_list('user_id', flat=True)
            funnel_entries = SalesFunnel.objects.filter(
                salesperson_id__in=salespeople_ids,
                is_active=True,
                is_closed=False
            )
        elif user.role == 'asm':
            # ASM can see entries from their teams (salespeople + supervisors + self)
            asm_teams = user.asm_teams.all()
            groups = Group.objects.filter(team__in=asm_teams)
            salespeople_ids = list(TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True))
            supervisor_ids = list(Group.objects.filter(team__in=asm_teams, supervisor__isnull=False).values_list('supervisor_id', flat=True))
            visible_ids = salespeople_ids + supervisor_ids
            funnel_entries = SalesFunnel.objects.filter(
                Q(salesperson_id__in=visible_ids) | Q(salesperson=user),
                is_active=True,
                is_closed=False
            )
        elif user.role == 'sm':
            # SM sees entries from their assigned groups (salespeople + supervisors + self)
            groups = user.sm_groups.all()
            salespeople_ids = list(TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True))
            supervisor_ids = list(Group.objects.filter(id__in=groups.values_list('id', flat=True), supervisor__isnull=False).values_list('supervisor_id', flat=True))
            visible_ids = salespeople_ids + supervisor_ids
            funnel_entries = SalesFunnel.objects.filter(
                Q(salesperson_id__in=visible_ids) | Q(salesperson=user),
                is_active=True,
                is_closed=False
            )
        elif user.role == 'avp':
            # AVP can see entries from their teams (salespeople + supervisors + ASMs + SMs)
            teams = Team.objects.filter(avp=user)
            groups = Group.objects.filter(team__in=teams)
            salespeople_ids = list(TeamMembership.objects.filter(group__in=groups).values_list('user_id', flat=True))
            asm_ids = list(teams.exclude(asm__isnull=True).values_list('asm_id', flat=True))
            supervisor_ids = list(Group.objects.filter(team__in=teams, supervisor__isnull=False).values_list('supervisor_id', flat=True))
            sm_ids = list(groups.values_list('sm_managers__id', flat=True))
            visible_ids = salespeople_ids + asm_ids + supervisor_ids + [i for i in sm_ids if i]
            funnel_entries = SalesFunnel.objects.filter(
                Q(salesperson_id__in=visible_ids) | Q(salesperson=user),
                is_active=True,
                is_closed=False
            )
        else:
            # Executives and admins can see all entries
            funnel_entries = SalesFunnel.objects.filter(
                is_active=True,
                is_closed=False
            )
        
        # Calculate funnel statistics
        funnel_stats = {
            'quoted_count': funnel_entries.filter(stage='quoted').count(),
            'closable_count': funnel_entries.filter(stage='closable').count(),
            'project_count': funnel_entries.filter(stage='project').count(),
            'total_value': funnel_entries.aggregate(Sum('retail'))['retail__sum'] or 0,
            'total_entries': funnel_entries.count(),
        }
        
        # Get recent entries for quick view (limit to 5)
        recent_entries = funnel_entries.select_related('salesperson', 'customer').order_by('-date_created')[:5]
        
        context.update({
            'funnel_stats': funnel_stats,
            'recent_funnel_entries': recent_entries,
            'show_funnel': True,
            'can_add_funnel': user.role in ['salesperson', 'supervisor', 'asm', 'avp'],
        })
    
    # ------------------------------------------------------------------
    # Marketing Officer Dashboard
    # ------------------------------------------------------------------
    if user.role == 'marketing':
        campaigns = Campaign.objects.all()
        recipients = CampaignRecipient.objects.all()

        sent_count = recipients.filter(status='sent').count()
        failed_count = recipients.filter(status='failed').count()
        interested_count = recipients.filter(interested_at__isnull=False).count()
        campaigns_sent = campaigns.filter(status='completed').count()

        # Interest rate = interested clicks / successfully sent emails.
        interest_rate = round((interested_count / sent_count) * 100, 1) if sent_count else 0

        # Recent campaigns (annotate each with its interested-click count)
        from django.db.models import Count
        recent_campaigns = campaigns.order_by('-created_at').annotate(
            interested_clicks=Count('recipients', filter=Q(recipients__interested_at__isnull=False))
        )[:5]

        # Recently added media / EDMs in the library
        recent_media = MediaLibraryAsset.objects.order_by('-created_at')[:5]

        # Recent "Interested" clicks to follow up on
        recent_interested = (
            recipients.filter(interested_at__isnull=False)
            .select_related('campaign', 'customer')
            .order_by('-interested_at')[:6]
        )

        # Announcements & upcoming events (active only)
        active_announcements = Announcement.objects.filter(is_active=True)
        upcoming_events = active_announcements.filter(
            announcement_type='event', event_date__gte=timezone.now()
        ).order_by('event_date')[:5]
        recent_announcements = active_announcements.exclude(
            announcement_type='event', event_date__gte=timezone.now()
        ).order_by('-created_at')[:5]

        context.update({
            'show_marketing_dashboard': True,
            'mkt_stats': {
                'campaigns_sent': campaigns_sent,
                'total_campaigns': campaigns.count(),
                'sent_count': sent_count,
                'failed_count': failed_count,
                'interested_count': interested_count,
                'interest_rate': interest_rate,
            },
            'mkt_recent_campaigns': recent_campaigns,
            'mkt_recent_media': recent_media,
            'mkt_recent_interested': recent_interested,
            'mkt_upcoming_events': upcoming_events,
            'mkt_recent_announcements': recent_announcements,
            'mkt_can_manage_announcements': True,
        })

    # ------------------------------------------------------------------
    # Active Users Widget (admin-only)
    # ------------------------------------------------------------------
    if user.role == 'admin':
        threshold_minutes = getattr(settings, 'ONLINE_THRESHOLD_MINUTES', 15)
        cutoff = timezone.now() - timedelta(minutes=threshold_minutes)

        active_users = (
            User.objects
            .filter(last_activity__gte=cutoff, is_active=True)
            .exclude(pk=user.pk)           # exclude self
            .select_related()
            .order_by('-last_activity')
        )

        context.update({
            'active_users': active_users,
            'active_users_count': active_users.count(),
            'online_threshold_minutes': threshold_minutes,
        })

    # Latest from Marketing — company-wide announcements/events for the home card.
    # (Announcement is imported at module top; no local import — that would make
    # the name a function-local and break the marketing branch above.)
    context['latest_announcements'] = list(
        Announcement.objects.filter(is_active=True)
        .select_related('created_by')
        .order_by('-created_at')[:4]
    )

    return render(request, 'core/home.html', context)

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('login')
