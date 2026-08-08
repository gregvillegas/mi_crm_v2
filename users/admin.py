from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from datetime import timedelta
from .models import User, UserActivityLog

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_online', 'last_activity')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'groups')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('CRM Info', {'fields': ('role', 'initials', 'mobile_number', 'last_activity')}),
    )
    readonly_fields = ('last_activity',)

    def is_online(self, obj):
        if not obj.last_activity:
            return False
        # User is considered online if active in the last 5 minutes
        return timezone.now() - obj.last_activity < timedelta(minutes=5)
    is_online.boolean = True
    is_online.short_description = 'Online Status'

@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'path', 'method', 'ip_address', 'timestamp')
    list_filter = ('method', 'timestamp', 'user')
    search_fields = ('user__username', 'path', 'ip_address', 'details')
    readonly_fields = ('user', 'path', 'method', 'ip_address', 'timestamp', 'details')
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


from .models import FailedLoginAttempt

@admin.register(FailedLoginAttempt)
class FailedLoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('username', 'ip_address', 'reason', 'timestamp', 'user_agent_short')
    list_filter = ('reason', 'timestamp')
    search_fields = ('username', 'ip_address', 'user_agent')
    readonly_fields = ('username', 'ip_address', 'user_agent', 'timestamp', 'reason')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'

    def user_agent_short(self, obj):
        return obj.user_agent[:80] + '...' if len(obj.user_agent) > 80 else obj.user_agent
    user_agent_short.short_description = 'User Agent'

    def has_add_permission(self, request):
        return False  # Log entries are created by signal only

    def has_change_permission(self, request, obj=None):
        return False  # Audit logs must not be editable
