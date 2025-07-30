from django.urls import path
from .views import *


urlpatterns = [
    path('apple-app-site-association', Appleapp.as_view(), name='apple-app-site-association'),
    path('assetlinks.json', Androidapp.as_view(), name='apple-app-site-association')
]