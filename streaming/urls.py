from django.conf.urls import include, url
from django.contrib import admin

from download import views

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url('^download_csv_streaming$', views.download_csv_streaming, name='download_csv_streaming'),
    url('^download_csv$', views.download_csv, name='download_csv')
]
