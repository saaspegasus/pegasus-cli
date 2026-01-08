<% if model_names -%>
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
<%- endif %>
from django.template.response import TemplateResponse
<%- if model_names %>
from django.urls import reverse
from django.views.decorators.http import require_POST
<%- endif %>

from << view_decorator_module >> import << view_decorator_function >>
<%- if model_names %>

from .forms import <% for model in model_names %><< model >>Form<% if not loop.last %>, <% endif %><% endfor %>
from .models import <% for model in model_names %><< model >><% if not loop.last %>, <% endif %><% endfor %>

# A reasonable value for pagination would be 10 or 20 entries per page.
# Here we use 4 (a very low value), so we can show off the pagination using fewer items
PAGINATE_BY = 4
# For pagination, we use get_elided_page_range() to give a list of pages that always has some
# pages at the beginning and end, and some on either side of current, with ellipsis where needed.
<%- endif %>


@<< view_decorator_function >>
def home(request<< extra_view_args >>):
    template = "<< app_name >>/<< app_name >>_home.html#page-content" if request.htmx else "<< app_name >>/<< app_name >>_home.html"

    return TemplateResponse(request, template, {"active_tab": "<< app_name >>"})
<%- for model_name in model_names %>


@<< view_decorator_function >>
def << model_name | lower >>_list(request<< extra_view_args >>):
    """Display a list of << model_name >>s."""
    context = {}
<%- if use_teams %>
    << model_name | lower >>_list = << model_name >>.objects.filter(team=request.team).order_by("-created_at")
<%- else %>
    << model_name | lower >>_list = << model_name >>.objects.filter(user=request.user).order_by("-created_at")
<% endif %>

    paginator = Paginator(<< model_name | lower >>_list, PAGINATE_BY)
    page = request.GET.get("page", 1)
    try:
        page = paginator.page(page)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    if request.htmx:
        if request.htmx.target == "page-content":
            template = "<< app_name >>/<< model_name | lower >>_list.html#page-content"
        else:
            template = "<< app_name >>/<< model_name | lower >>_list.html#object-table"
    else:
        template = "<< app_name >>/<< model_name | lower >>_list.html"

    context["active_tab"] = "<< app_name >>"
    context["page_obj"] = page
    context["object_list"] = page.object_list
    context["is_paginated"] = page.has_other_pages
    context["elided_page_range"] = list(paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1))
    return render(request, template, context)


@<< view_decorator_function >>
def << model_name | lower >>_detail(request<< extra_view_args >>, pk):
    """Display << model_name >> details."""
    context = {}
    context["active_tab"] = "<< app_name >>"
<%- if use_teams %>
    context["object"] = get_object_or_404(<< model_name >>, id=pk, team=request.team)
<%- else %>
    context["object"] = get_object_or_404(<< model_name >>, id=pk, user=request.user)
<%- endif %>

    template = "<< app_name >>/<< model_name | lower >>_detail.html#page-content" if request.htmx else "<< app_name >>/<< model_name | lower >>_detail.html"

    return render(request, template, context)


@<< view_decorator_function >>
def << model_name | lower >>_create(request<< extra_view_args >>):
    """Create a new << model_name >>."""
    context = {}
    form = << model_name >>Form(request.POST or None)
    if form.is_valid():
        instance = form.save(commit=False)
        instance.user = request.user
<%- if use_teams %>
        instance.team = request.team
<%- endif %>
        instance.save()
        return HttpResponseRedirect(reverse("<< app_name >>:<< model_name | lower >>_list"<% if extra_view_param %>, kwargs={"<< extra_view_param >>": << extra_view_param_value >>}<% endif %>))

    template = "<< app_name >>/<< model_name | lower >>_form.html#page-content" if request.htmx else "<< app_name >>/<< model_name | lower >>_form.html"

    context["active_tab"] = "<< app_name >>"
    context["form"] = form
    return render(request, template, context)


@<< view_decorator_function >>
def << model_name | lower >>_update(request<< extra_view_args >>, pk):
    """Edit / update a << model_name >>."""
    context = {}
<%- if use_teams %>
    obj = get_object_or_404(<< model_name >>, id=pk, team=request.team)
<%- else %>
    obj = get_object_or_404(<< model_name >>, id=pk, user=request.user)
<%- endif %>
    form = << model_name >>Form(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        return HttpResponseRedirect(reverse("<< app_name>>:<< model_name | lower >>_detail", kwargs={<% if extra_view_param %>"<< extra_view_param >>": << extra_view_param_value >>, <% endif %>"pk": pk}))

    template = "<< app_name >>/<< model_name | lower >>_form.html#page-content" if request.htmx else "<< app_name >>/<< model_name | lower >>_form.html"
    context["active_tab"] = "<< app_name >>"
    context["form"] = form
    context["object"] = obj
    return render(request, template, context)


@<< view_decorator_function >>
@require_POST
def << model_name | lower >>_delete(request<< extra_view_args >>, pk):
    """Delete a << model_name >>."""
<%- if use_teams %>
    obj = get_object_or_404(<< model_name >>, id=pk, team=request.team)
<%- else %>
    obj = get_object_or_404(<< model_name >>, id=pk, user=request.user)
<%- endif %>
    obj.delete()
    return HttpResponseRedirect(reverse("<< app_name >>:<< model_name | lower >>_list"<% if extra_view_param %>, kwargs={"<< extra_view_param >>": << extra_view_param_value >>}<% endif %>))
<%- endfor  %>
