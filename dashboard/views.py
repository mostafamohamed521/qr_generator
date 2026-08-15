import json
from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
import csv

from qrapp.models import QRCode, DynamicLink
from teams.models import Team
from accounts.models import AuditLogEntry


def _admin(view_fn):
    return staff_member_required(view_fn, login_url='accounts:login')


@_admin
def dashboard(request):
    return render(request, 'dashboard/dashboard.html')


@_admin
@require_GET
def stats(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    total_users  = User.objects.count()
    new_week     = User.objects.filter(date_joined__gte=week_ago).count()
    total_qr     = QRCode.objects.count()
    new_qr_week  = QRCode.objects.filter(created_at__gte=week_ago).count()
    total_scans  = DynamicLink.objects.aggregate(s=Sum('scan_count'))['s'] or 0
    total_teams  = Team.objects.count()
    total_dynamic= DynamicLink.objects.count()

    # User signups last 14 days
    user_growth = list(
        User.objects.filter(date_joined__gte=now - timedelta(days=14))
        .annotate(day=TruncDate('date_joined'))
        .values('day').annotate(count=Count('id')).order_by('day')
    )
    for i in user_growth:
        i['day'] = i['day'].strftime('%d %b')

    # QR codes last 14 days
    qr_growth = list(
        QRCode.objects.filter(created_at__gte=now - timedelta(days=14))
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(count=Count('id')).order_by('day')
    )
    for i in qr_growth:
        i['day'] = i['day'].strftime('%d %b')

    # QR by type
    qr_by_type = list(QRCode.objects.values('qr_type').annotate(count=Count('id')).order_by('-count'))

    # Top 5 most active users
    top_users = list(
        User.objects.order_by('-date_joined')[:5]
        .values('id','email','first_name','last_name','is_active','date_joined')
    )
    for u in top_users:
        u['qr_count'] = 0
    for u in top_users:
        u['date_joined'] = u['date_joined'].strftime('%d %b %Y') if u['date_joined'] else ''
        u['name'] = f"{u['first_name']} {u['last_name']}".strip() or u['email']

    # Recent audit activity
    recent = list(
        AuditLogEntry.objects.select_related('user','team')
        .order_by('-created_at')[:10]
        .values('action','created_at','user__email','user__first_name','user__last_name','team__name')
    )
    for e in recent:
        e['created_at'] = e['created_at'].strftime('%d %b, %H:%M')
        e['username'] = (
            f"{e['user__first_name']} {e['user__last_name']}".strip()
            or e['user__email'] or 'System'
        )

    return JsonResponse({
        'ok': True,
        'stats': {
            'total_users': total_users, 'new_week': new_week,
            'total_qr': total_qr, 'new_qr_week': new_qr_week,
            'total_scans': total_scans, 'total_teams': total_teams,
            'total_dynamic': total_dynamic,
        },
        'user_growth': user_growth,
        'qr_growth': qr_growth,
        'qr_by_type': qr_by_type,
        'top_users': top_users,
        'recent': recent,
    })


@_admin
def users_page(request):
    return render(request, 'dashboard/users.html')


@_admin
@require_GET
def users_list(request):
    q       = request.GET.get('q','').strip()
    page    = max(1, int(request.GET.get('page',1)))
    per     = 20
    qs = User.objects.order_by('-date_joined')
    if q:
        qs = qs.filter(Q(email__icontains=q)|Q(first_name__icontains=q)|Q(last_name__icontains=q))
    total = qs.count()
    pages = max(1, (total+per-1)//per)
    qs    = qs[(page-1)*per: page*per]
    return JsonResponse({'ok':True,'total':total,'pages':pages,'page':page,'users':[{
        'id': u.id, 'email': u.email,
        'name': f"{u.first_name} {u.last_name}".strip() or '—',
        'qr_count': 0,
        'is_active': u.is_active, 'is_staff': u.is_staff,
        'date_joined': u.date_joined.strftime('%d %b %Y') if u.date_joined else '',
    } for u in qs]})


@_admin
@require_POST
def toggle_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        return JsonResponse({'ok':False,'error':"Can't modify your own account"},status=400)
    try:
        p = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok':False,'error':'Invalid JSON'},status=400)

    # Granting/revoking staff access is a superuser-only action — a staff user
    # (is_staff=True) who isn't a superuser must not be able to mint other
    # admins. Likewise, only a superuser may touch another superuser's account
    # at all, otherwise any staff member could lock out the site's superusers.
    if 'is_staff' in p and not request.user.is_superuser:
        return JsonResponse({'ok':False,'error':'Only a superuser can grant or revoke staff access'},status=403)
    if user.is_superuser and not request.user.is_superuser:
        return JsonResponse({'ok':False,'error':'Only a superuser can modify a superuser account'},status=403)

    if 'is_active' in p: user.is_active = bool(p['is_active'])
    if 'is_staff'  in p: user.is_staff  = bool(p['is_staff'])
    user.save(update_fields=['is_active','is_staff'])
    AuditLogEntry.objects.create(user=request.user, team=None,
        action='admin.user_toggled', metadata={'target': user.email, **p})
    return JsonResponse({'ok':True,'is_active':user.is_active,'is_staff':user.is_staff})


@_admin
@require_POST
def delete_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        return JsonResponse({'ok':False,'error':"Can't delete yourself"},status=400)
    if user.is_superuser and not request.user.is_superuser:
        return JsonResponse({'ok':False,'error':'Only a superuser can delete a superuser account'},status=403)
    email = user.email
    user.delete()
    AuditLogEntry.objects.create(user=request.user, team=None,
        action='admin.user_deleted', metadata={'email': email})
    return JsonResponse({'ok':True})


@_admin
@require_GET
def export_users_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="users.csv"'
    response.write('\ufeff')
    w = csv.writer(response)
    w.writerow(['ID','Email','Name','QR Count','Active','Staff','Joined'])
    for u in User.objects.order_by('-date_joined'):
        w.writerow([u.id,u.email,f"{u.first_name} {u.last_name}".strip(),
                    0, u.is_active,u.is_staff,
                    u.date_joined.strftime('%Y-%m-%d') if u.date_joined else ''])
    return response
