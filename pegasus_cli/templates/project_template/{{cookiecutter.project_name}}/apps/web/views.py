from django.template.response import TemplateResponse


def home(request):
    return TemplateResponse(request, 'web/landing_page.html')

