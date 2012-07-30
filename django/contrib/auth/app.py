from django import apps
from django.utils.importlib import import_module
from django.utils.translation import ugettext_lazy as _

class AuthApp(apps.App):

    user_model = 'django.contrib.auth.models.User'
    class Meta:
        verbose_name = _('auth')

    def get_user_model(self):
        model_name = self.user_model.split('.')[-1].lower()
        if model_name not in self._meta.models:
            self.register_models()
        return self._meta.models[model_name]

    def register_models(self):
        super(AuthApp, self).register_models()
        import_module(self.user_model.rsplit('.', 1)[0])
