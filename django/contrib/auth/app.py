from django import apps
from django.utils.translation import ugettext_lazy as _

class AuthApp(apps.App):

    label = 'auth'
    models_path = 'django.contrib.auth.models'
