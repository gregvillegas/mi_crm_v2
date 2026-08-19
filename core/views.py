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
from sales_funnel.models import SalesFunnel
from teams.models import Team, Group, TeamMembership
from users.models import User
from gamification.models import UserMissionProgress
from gamification.utils import generate_daily_missions, generate_weekly_missions, get_current_week_start

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

    return render(request, 'core/home.html', context)

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('login')
