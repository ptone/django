from django import apps
from django.utils.translation import ugettext_lazy as _

class AuthApp(apps.App):

    auth_user_model = 'auth.User'
    class Meta:
        verbose_name = _('auth')

    def get_user_model(self):
        model_name = self.auth_user_model.split('.')[-1].lower()
        return self._meta.models[model_name]
