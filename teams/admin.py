from django.contrib import admin
from .models import Team, TeamMember, TeamInvite


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 0
    autocomplete_fields = ('user',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display  = ('name', 'slug', 'owner', 'member_count', 'created_at')
    search_fields = ('name', 'slug', 'owner__username', 'owner__email')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('owner',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TeamMemberInline]

    def member_count(self, obj):
        return obj.members.count()


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display  = ('team', 'user', 'role', 'joined_at')
    list_filter   = ('role', 'joined_at')
    search_fields = ('team__name', 'user__username', 'user__email')
    autocomplete_fields = ('team', 'user')


@admin.register(TeamInvite)
class TeamInviteAdmin(admin.ModelAdmin):
    # The token is a bearer credential for joining a team — never shown.
    list_display    = ('team', 'email', 'role', 'accepted', 'invited_by', 'created_at')
    list_filter     = ('accepted', 'role', 'created_at')
    search_fields   = ('team__name', 'email')
    readonly_fields = ('team', 'email', 'role', 'invited_by', 'accepted', 'created_at')
    exclude         = ('token',)

    def has_add_permission(self, request):
        return False
