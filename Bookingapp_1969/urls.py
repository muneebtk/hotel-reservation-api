"""
URL configuration for Bookingapp_1969 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',include('privatepolicy.urls')),
    path('.well-known/', include('privatepolicy.deeplink-urls')),
    path('api/',include('api.urls')),
    path('vendor/',include('vendor.urls')),
    path('chalets/',include('chalets.urls')),
    path('super_user/',include('superuserapp.urls')),
    path('common/',include('common.urls')),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('allauth.socialaccount.urls')),
    
    path('', lambda request: redirect('vendor/login/', permanent=True)),
]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if not settings.DEBUG:
    handler404="vendor.views.error_404_view"
    handler500="vendor.views.error_500_view"
    handler403="vendor.views.error_403_view"
    handler400="vendor.views.error_400_view"

# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # urlpatterns+= static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)