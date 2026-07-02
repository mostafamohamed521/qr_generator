import json
import secrets

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from .models import Team, TeamMember, TeamInvite
from accounts.models import Profile, AuditLogEntry


def _is_admin(team, user):
    return TeamMember.objects.filter(team=team, user=user, role__in=['owner', 'admin']).exists()


def _log(user, team, action, meta=None):
    AuditLogEntry.objects.create(user=user, team=team, action=action, metadata=meta or {})


# ── Pages ─────────────────────────────────────────────────────────────────────
@login_required
def teams_page(request):
    return render(request, 'teams/teams.html')


@login_required
def team_detail(request, slug):
    team = get_object_or_404(Team, slug=slug)
    if not TeamMember.objects.filter(team=team, user=request.user).exists():
        from django.http import Http404
        raise Http404
    return render(request, 'teams/team_detail.html', {'team': team})


# ── API: my teams ─────────────────────────────────────────────────────────────
@login_required
@require_GET
def my_teams(request):
    memberships = TeamMember.objects.filter(user=request.user).select_related('team')
    active_id   = getattr(request.user.profile, 'active_team_id', None)
    teams = [{
        'id':       m.team.id,
        'name':     m.team.name,
        'slug':     m.team.slug,
        'role':     m.role,
        'members':  m.team.members.count(),
        'active':   m.team.id == active_id,
    } for m in memberships]
    return JsonResponse({'ok': True, 'teams': teams})


# ── API: create team ──────────────────────────────────────────────────────────
@login_required
@require_POST
def create_team(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    name = payload.get('name', '').strip()[:120]
    if not name:
        return JsonResponse({'ok': False, 'error': 'Team name is required'}, status=400)

    # generate unique slug
    base_slug = slugify(name)[:100] or 'team'
    slug = base_slug
    counter = 1
    while Team.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{counter}'; counter += 1

    team = Team.objects.create(name=name, slug=slug, owner=request.user)
    TeamMember.objects.create(team=team, user=request.user, role='owner')

    # set as active team
    Profile.objects.filter(user=request.user).update(active_team=team)
    _log(request.user, team, 'team.created', {'name': name})

    return JsonResponse({'ok': True, 'team': {
        'id': team.id, 'name': team.name, 'slug': team.slug, 'role': 'owner',
    }})


# ── API: switch active team ───────────────────────────────────────────────────
@login_required
@require_POST
def switch_team(request, pk):
    membership = TeamMember.objects.filter(team_id=pk, user=request.user).first()
    if not membership:
        return JsonResponse({'ok': False, 'error': 'Not a member'}, status=403)
    Profile.objects.filter(user=request.user).update(active_team_id=pk)
    return JsonResponse({'ok': True, 'team_id': pk, 'team_name': membership.team.name})


# ── API: leave / delete team ─────────────────────────────────────────────────
@login_required
@require_POST
def leave_team(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if team.owner == request.user:
        return JsonResponse({'ok': False, 'error': 'Owner cannot leave — transfer ownership or delete the team'}, status=400)
    TeamMember.objects.filter(team=team, user=request.user).delete()
    _log(request.user, team, 'team.left')
    return JsonResponse({'ok': True})


@login_required
@require_POST
def delete_team(request, pk):
    team = get_object_or_404(Team, pk=pk, owner=request.user)
    _log(request.user, team, 'team.deleted', {'name': team.name})
    team.delete()
    return JsonResponse({'ok': True})


# ── API: members ──────────────────────────────────────────────────────────────
@login_required
@require_GET
def team_members(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if not TeamMember.objects.filter(team=team, user=request.user).exists():
        return JsonResponse({'ok': False, 'error': 'Not a member'}, status=403)

    members = [{
        'id':       m.user.id,
        'username': m.user.get_full_name() or m.user.email,
        'email':    m.user.email,
        'role':     m.role,
        'joined':   m.joined_at.strftime('%d %b %Y'),
        'is_me':    m.user == request.user,
    } for m in team.members.select_related('user').order_by('joined_at')]

    pending = [{
        'email': i.email,
        'role':  i.role,
        'token': i.token[:8] + '…',
        'date':  i.created_at.strftime('%d %b %Y'),
    } for i in TeamInvite.objects.filter(team=team, accepted=False)]

    return JsonResponse({'ok': True, 'members': members, 'pending': pending,
                         'is_admin': _is_admin(team, request.user)})


# ── API: invite ───────────────────────────────────────────────────────────────
@login_required
@require_POST
def invite_member(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if not _is_admin(team, request.user):
        return JsonResponse({'ok': False, 'error': 'Admin only'}, status=403)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    email = payload.get('email', '').strip().lower()
    role  = payload.get('role', 'member')
    if not email:
        return JsonResponse({'ok': False, 'error': 'Email is required'}, status=400)
    if role not in ['admin', 'member']:
        role = 'member'

    # If user already exists and is a member, skip
    try:
        existing_user = User.objects.get(email__iexact=email)
        if TeamMember.objects.filter(team=team, user=existing_user).exists():
            return JsonResponse({'ok': False, 'error': 'User is already a member'}, status=400)
        # Auto-add if they have an account
        TeamMember.objects.create(team=team, user=existing_user, role=role)
        _log(request.user, team, 'member.added', {'email': email, 'role': role})
        return JsonResponse({'ok': True, 'auto_added': True, 'email': email})
    except User.DoesNotExist:
        pass

    # create invite token
    token  = secrets.token_urlsafe(32)
    invite, created = TeamInvite.objects.update_or_create(
        team=team, email=email,
        defaults={'role': role, 'token': token, 'invited_by': request.user, 'accepted': False},
    )
    invite_url = request.build_absolute_uri(f'/teams/accept/{token}/')
    _log(request.user, team, 'member.invited', {'email': email, 'role': role})

    # In production this would send an email. For now return the link.
    return JsonResponse({'ok': True, 'invite_url': invite_url, 'email': email})


# ── API: accept invite ────────────────────────────────────────────────────────
@login_required
def accept_invite(request, token):
    invite = get_object_or_404(TeamInvite, token=token, accepted=False)
    # If email matches the current user's email, add them
    if request.user.email.lower() != invite.email.lower():
        return render(request, 'teams/invite_mismatch.html', {'invite': invite})

    member, created = TeamMember.objects.get_or_create(
        team=invite.team, user=request.user,
        defaults={'role': invite.role},
    )
    if not created:
        member.role = invite.role; member.save()

    invite.accepted = True; invite.save()
    Profile.objects.filter(user=request.user).update(active_team=invite.team)
    _log(request.user, invite.team, 'invite.accepted', {'role': invite.role})

    return render(request, 'teams/invite_accepted.html', {'team': invite.team})


# ── API: change role ──────────────────────────────────────────────────────────
@login_required
@require_POST
def change_role(request, pk, user_id):
    team = get_object_or_404(Team, pk=pk)
    if not _is_admin(team, request.user):
        return JsonResponse({'ok': False, 'error': 'Admin only'}, status=403)
    if team.owner_id == user_id:
        return JsonResponse({'ok': False, 'error': 'Cannot change owner role'}, status=400)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    role = payload.get('role', 'member')
    if role not in ['admin', 'member']:
        return JsonResponse({'ok': False, 'error': 'Invalid role'}, status=400)

    TeamMember.objects.filter(team=team, user_id=user_id).update(role=role)
    _log(request.user, team, 'role.changed', {'user_id': user_id, 'new_role': role})
    return JsonResponse({'ok': True})


# ── API: remove member ────────────────────────────────────────────────────────
@login_required
@require_POST
def remove_member(request, pk, user_id):
    team = get_object_or_404(Team, pk=pk)
    if not _is_admin(team, request.user):
        return JsonResponse({'ok': False, 'error': 'Admin only'}, status=403)
    if team.owner_id == user_id:
        return JsonResponse({'ok': False, 'error': 'Cannot remove team owner'}, status=400)
    TeamMember.objects.filter(team=team, user_id=user_id).delete()
    _log(request.user, team, 'member.removed', {'user_id': user_id})
    return JsonResponse({'ok': True})


# ── API: audit log ────────────────────────────────────────────────────────────
@login_required
@require_GET
def audit_log(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if not TeamMember.objects.filter(team=team, user=request.user).exists():
        return JsonResponse({'ok': False, 'error': 'Not a member'}, status=403)

    entries = AuditLogEntry.objects.filter(team=team).select_related('user')[:50]
    return JsonResponse({'ok': True, 'entries': [{
        'action':    e.action,
        'user':      e.user.get_full_name() or e.user.email if e.user else 'System',
        'meta':      e.metadata,
        'timestamp': e.created_at.strftime('%d %b %Y, %H:%M'),
    } for e in entries]})
