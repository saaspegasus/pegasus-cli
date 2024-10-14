from django import forms

from .models import <% for model in model_names %><< model >><% if not loop.last %>, <% endif %><% endfor %>
<%- for model in model_names %>


class << model >>Form(forms.ModelForm):
    class Meta:
        model = << model >>
        fields = ["name"]
<%- endfor %>
