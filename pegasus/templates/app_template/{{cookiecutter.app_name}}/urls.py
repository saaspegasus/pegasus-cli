from django.urls import path

from . import views

app_name = "<< app_name >>"

urlpatterns = [
    path("", views.home, name="<< app_name >>_home"),
<%- for model_name in model_names %>
    path("<< model_name | lower >>/", views.<< model_name | lower >>_list, name="<< model_name | lower >>_list"),
    path("<< model_name | lower >>/<int:pk>/", views.<< model_name | lower >>_detail, name="<< model_name | lower >>_detail"),
    path("<< model_name | lower >>/create/", views.<< model_name | lower >>_create, name="<< model_name | lower >>_create"),
    path("<< model_name | lower >>/<int:pk>/update/", views.<< model_name | lower >>_update, name="<< model_name | lower >>_update"),
    path("<< model_name | lower >>/<int:pk>/delete/", views.<< model_name | lower >>_delete, name="<< model_name | lower >>_delete"),
<%- endfor %>
]
