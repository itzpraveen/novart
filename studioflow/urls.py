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

from portal.public_site import public_work, site_root


def _public_canonical_url(path: str = '/') -> str:
    base_url = getattr(settings, 'PUBLIC_SITE_CANONICAL_URL', 'https://novartarchitects.com').rstrip('/')
    return f"{base_url}{path}"


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


@require_GET
def robots_txt(request):
    response = HttpResponse(
        "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                f"Sitemap: {_public_canonical_url('/sitemap.xml')}",
                "",
            ]
        ),
        content_type="text/plain",
    )
    response["Cache-Control"] = "max-age=3600"
    return response


@require_GET
def sitemap_xml(request):
    response = HttpResponse(
        "\n".join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
                "  <url>",
                f"    <loc>{_public_canonical_url()}</loc>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>1.0</priority>",
                "  </url>",
                "  <url>",
                f"    <loc>{_public_canonical_url('/work/')}</loc>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>0.8</priority>",
                "  </url>",
                "</urlset>",
                "",
            ]
        ),
        content_type="application/xml",
    )
    response["Cache-Control"] = "max-age=3600"
    return response

urlpatterns = [
    path("favicon.ico", favicon),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),
    path("manifest.json", manifest, name="manifest"),
    path("service-worker.js", service_worker, name="service_worker"),
    path("work/", public_work, name="public_work"),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='portal/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('api/v1/', include('portal.api.urls')),
    path('', site_root, name='dashboard'),
    path('', include('portal.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
