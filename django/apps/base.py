import re
import sys

from django.apps.options import AppOptions, DEFAULT_NAMES
from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module
from django.utils.module_loading import module_has_submodule

module_name_re = re.compile(r'_([a-z])')


class AppBase(type):
    """
    Metaclass for all apps.
    """
    def __new__(cls, name, bases, attrs):
        super_new = super(AppBase, cls).__new__
        parents = [b for b in bases if isinstance(b, AppBase)]
        if not parents:
            # If this isn't a subclass of App, don't do anything special.
            return super_new(cls, name, bases, attrs)
        module = attrs.pop('__module__', None)
        new_class = super_new(cls, name, bases, {'__module__': module})
        attr_meta = attrs.pop('Meta', None)
        if not attr_meta:
            meta = getattr(new_class, 'Meta', None)
        else:
            meta = attr_meta
        app_name = attrs.pop('_name', None)
        if app_name is None:
            # Figure out the app_name by looking one level up.
            # For 'django.contrib.sites.app', this would be
            # 'django.contrib.sites'
            app_module = sys.modules[new_class.__module__]
            app_name = app_module.__name__.rsplit('.', 1)[0]
        new_class.add_to_class('_meta', AppOptions(app_name, meta))
        # For easier Meta inheritance
        new_class.add_to_class('Meta', attr_meta)
        # Add all remaining attributes to the class.
        for obj_name, obj in attrs.items():
            new_class.add_to_class(obj_name, obj)
        return new_class

    def add_to_class(cls, name, value):
        if hasattr(value, 'contribute_to_class'):
            value.contribute_to_class(cls, name)
        else:
            setattr(cls, name, value)


class App(object):
    """
    The base app class to be subclassed for own uses.
    """
    __metaclass__ = AppBase

    def __init__(self, **options):
        for key, value in options.items():
            if key in DEFAULT_NAMES:
                setattr(self._meta, key, value)
            else:
                setattr(self, key, value)

    def __repr__(self):
        return '<App: %s>' % self._meta.name

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
        if not self._meta.installed:
            return
        from django.apps import app_cache
        # make sure models registered at import time are assigned to the app
        same_label_apps = [app for app in app_cache.loaded_apps if
                app._meta.label == self._meta.label]
        for app in same_label_apps:
            if app != self:
                if app._meta.installed:
                    raise ImproperlyConfigured(
                        'Multiple apps with the label %s can not be loaded' %
                        app._meta.label)
                else:
                    self._meta.models.update(app._meta.models)
                    if app._meta.models_module:
                        self._meta.models_module = app._meta.models_module
                    app_cache._unload_app(app)


    def register_models(self):
        from django.apps import app_cache
        if not self._meta.models_module:
            try:
                models = import_module(self._meta.models_path)
                self._meta.models_module = models
            except ImportError:
                # If the app doesn't have a models module, we can just ignore the
                # ImportError and return no models for it.
                if not module_has_submodule(self._meta.module, 'models'):
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
        for model in self._meta.models.values():
            # update the models reference to the app it is associated with
            model._meta.app = self
            # update the db_table of the model if set by the app
            if (self._meta.label != self._meta.db_prefix and
                    model._meta.db_table.startswith(self._meta.label)):
                # this should be safe as it should always have been called
                # early on before any syncdb
                model._meta.db_table = model._meta.db_table.replace(
                        self._meta.label,
                        self._meta.db_prefix)

        parents = [p for p in self.__class__.mro()
                    if hasattr(p, '_meta')]
        for parent in reversed(parents):
            parent._meta.installed = self._meta.installed
            parent_models = parent._meta.models
            for model in parent_models.values():
                pass
                # TODO what really should these parents be set to here?
                # model._meta.app_label = self._meta.label
                # model._meta.app = self
            self._meta.models.update(parent_models)
        app_cache._get_models_cache.clear()

    def get_model(self, name):
        return self._meta.models.get(name, None)
