from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import include, path
from django.views.decorators.http import require_GET


def favicon(request):
    try:
        return redirect(staticfiles_storage.url("favicon.ico"), permanent=True)
    except Exception:
        return redirect(f"{settings.STATIC_URL}favicon.ico", permanent=True)


@require_GET
def manifest(request):
    response = HttpResponse(
        render_to_string("manifest.json", request=request),
        content_type="application/manifest+json",
    )
    response["Cache-Control"] = "no-cache"
    return response


@require_GET
def service_worker(request):
    response = HttpResponse(
        render_to_string("service-worker.js", request=request),
        content_type="application/javascript",
    )
    response["Cache-Control"] = "no-cache"
    return response

urlpatterns = [
    path("favicon.ico", favicon),
    path("manifest.json", manifest, name="manifest"),
    path("service-worker.js", service_worker, name="service_worker"),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='portal/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('api/v1/', include('portal.api.urls')),
    path('', include('portal.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
