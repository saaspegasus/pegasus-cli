<% if model_names -%>
from django.conf import settings
<%- endif %>
from django.db import models<% if not model_names %>  # noqa<% endif %>
<%- if model_names %>
from django.urls import reverse
<%- if base_model %>

from << base_model_module >> import << base_model_class >>
<%- endif %>
<%- for model_name in model_names %>


class << model_name >>(<<base_model_class if base_model else "models.Model">>):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("<< app_name >>:<< model_name | lower >>_detail", kwargs={<% if extra_view_param %>"<< extra_view_param >>": << extra_model_param_value >>, <% endif %>"pk": self.pk})
<%- endfor %>
<%- else %>

# Create your models here.
<% endif %>
