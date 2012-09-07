import re
import sys

from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module
from django.utils.module_loading import module_has_submodule
from django.utils.text import get_verbose_name

module_name_re = re.compile(r'_([a-z])')



class App(object):
    """
    The base app class to be subclassed.
    """

    def __init__(self, **options):

        # set to true when the app in instantiated by app_cache._populate
        # but remains false for naive apps
        self.installed = False

        # TODO should this happen after the __dict__update below?
        # _name is an option passed in from the factory class methods
        self.name = options.get('_name', self.__module__)

        # TODO is this really still needed?
        if self.name in sys.modules:
            self.path = sys.modules[self.name].__file__
        else:
            self.path = ''

        # TODO - think this can go away as an attribute
        # can just be retrieved from the class if needed
        self.module = None

        if '.' in self.name:
            self.label = self.name.split('.')[-1]
        else:
            self.label = self.name

        self.models_path = '%s.models' % self.name
        # update attributes on self with kwarg like configuration
        # from INSTALLED_APPS
        self.__dict__.update(options)
        self.verbose_name = get_verbose_name(self.label),

    def __repr__(self):
        return '<App: %s>' % self.name

    @classmethod
    def from_name(cls, name):
        upper = lambda match: match.group(1).upper()
        cls_name = module_name_re.sub(upper, name.split('.')[-1])
        return type(cls_name[0].upper() +
                cls_name[1:], (cls,), {'_name': name})

    @classmethod
    def from_label(cls, label):
        label = str(label)
        upper = lambda match: match.group(1).upper()
        cls_name = module_name_re.sub(upper, label)
        return type(cls_name[0].upper() +
                cls_name[1:], (cls,), {'_name': label})

    def relocate_models(self):
        if not self.installed:
            # we are a naive app, and don't relocate models
            return
        from django.apps import app_cache
        # make sure models registered at import time are assigned to the app
        same_label_apps = [app for app in app_cache.loaded_apps if
                app.label == self.label]
        for app in same_label_apps:
            if app != self:
                if app.installed:
                    raise ImproperlyConfigured(
                        'Multiple apps with the label %s can not be loaded' %
                        app.label)
                else:
                    self.models.update(app.models)
                    if app.models_module:
                        self.models_module = app.models_module
                    app_cache._unload_app(app)


    def register_models(self):
        from django.apps import app_cache
        if not self.models_module:
            try:
                models = import_module(self.models_path)
                self.models_module = models
            except ImportError:
                # If the app doesn't have a models module, we can just ignore the
                # ImportError and return no models for it.
                if not module_has_submodule(self.__module__, 'models'):
                    return None
                # But if the app does have a models module, we need to figure out
                # whether to suppress or propagate the error. If can_postpone is
                # True then it may be that the package is still being imported by
                # Python and the models module isn't available yet. So we add the
                # app to the postponed list and we'll try it again after all the
                # recursion has finished (in populate). If can_postpone is False
                # then it's time to raise the ImportError.
                else:
                    raise
        for model in self.models.values():
            # update the models reference to the app it is associated with
            # TODO remove the backref - and associated bits in model options
            model._meta.app = self

            # TODO this commented out block should be removed
            # we let models always use the standard way of determining db_table
            ## update the db_table of the model if set by the app
            # if (self._meta.label != self._meta.db_prefix and
                    # model._meta.db_table.startswith(self._meta.label)):
                ## this should be safe as it should always have been called
                ## early on before any syncdb
                # model._meta.db_table = model._meta.db_table.replace(
                        # self._meta.label,
                        # self._meta.db_prefix)

        app_cache._get_models_cache.clear()

    def get_model(self, name):
        return self.models.get(name, None)
