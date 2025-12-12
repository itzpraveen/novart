from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.staticfiles.storage import staticfiles_storage
from django.shortcuts import redirect
from django.urls import include, path


def favicon(request):
    try:
        return redirect(staticfiles_storage.url("favicon.ico"), permanent=True)
    except Exception:
        return redirect(f"{settings.STATIC_URL}favicon.ico", permanent=True)

urlpatterns = [
    path("favicon.ico", favicon),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='portal/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('portal.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
