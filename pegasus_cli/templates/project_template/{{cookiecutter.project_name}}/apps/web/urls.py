from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("app/", views.app_home, name="app_home"),
]
