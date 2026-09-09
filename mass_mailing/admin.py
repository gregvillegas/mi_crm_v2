from django.contrib import admin

from .models import (
    Campaign,
    CampaignRecipient,
    MediaLibraryAsset,
    Announcement,
    OptOut,
)


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'announcement_type', 'event_date', 'is_active', 'created_by', 'created_at')
    list_filter = ('announcement_type', 'is_active', 'created_at')
    search_fields = ('title', 'body', 'location')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MediaLibraryAsset)
class MediaLibraryAssetAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'uploaded_by', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title',)
    ordering = ('-created_at',)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'total_recipients', 'sent_count', 'failed_count', 'created_by', 'created_at')
    list_filter = ('status', 'template_type', 'created_at')
    search_fields = ('name', 'subject')
    ordering = ('-created_at',)


@admin.register(OptOut)
class OptOutAdmin(admin.ModelAdmin):
    list_display = ('email', 'customer', 'opted_out_at')
    search_fields = ('email',)
    ordering = ('-opted_out_at',)
