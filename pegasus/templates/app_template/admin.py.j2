from django.contrib import admin<% if not model_names %>  # noqa<% endif %>
<%- if model_names %>

from .models import <% for model in model_names %><< model >><% if not loop.last %>, <% endif %><% endfor %>
<%- for model_name in model_names %>


@admin.register(<< model_name >>)
class << model_name >>Admin(admin.ModelAdmin):
    list_display = ["name", <% if use_teams %>"team", <% endif %>"user", "created_at", "updated_at"]
    search_fields = ["name", <% if use_teams %>"team__slug", <% endif %>"user__email"]

<%- endfor %>
<%- else %>

# Register your models here.
<%- endif %>
