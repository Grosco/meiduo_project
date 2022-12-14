"""meiduo_mall URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
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
from django.urls import path, re_path, include
from django.views.generic import RedirectView

from meiduo_mall.utils import views as contents_views

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='static/favicon.ico')),
    path('admin/', admin.site.urls),
    path('admincenter/', include('admincenter.urls', namespace='admincenter')),
    path('search/', include('haystack.urls')),
    path('', include('users.urls', namespace='users')),
    path('', include('contents.urls', namespace='contents')),
    path('', include('goods.urls', namespace='goods')),
    path('', include('verifications.urls', namespace='verifications')),
    path('', include('oauth.urls', namespace='oauth')),
    path('', include('areas.urls', namespace='areas')),
    path('', include('carts.urls', namespace='carts')),
    path('', include('orders.urls', namespace='orders')),
    re_path(r'(?P<fastdfs>^group\d+?/.*?$)', contents_views.FastDFSView.as_view()),
]
