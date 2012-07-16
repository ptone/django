import imp
import sys
import os
import warnings
from collections import namedtuple

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module
from django.utils.module_loading import module_has_submodule

from django.apps.base import App
from django.apps.signals import app_loaded, post_apps_loaded, pre_apps_loaded


def _initialize():
    """
    Returns a dictionary to be used as the initial value of the
    shared state of the app cache.
    """
    return {
        # list of loaded app instances
        'loaded_apps': [],
        'apps': None,
        # -- Everything below here is only used when populating the cache --
        'loaded': False,
        'postponed': [],
        'nesting_level': 0,
        '_get_models_cache': {},
        # this is a hack used to preserve some global state across tests
        '_test_mode': False,
    }


class AppCache(object):
    """
    A cache that stores installed applications and their models. Used to
    provide reverse-relations and for app introspection (e.g. admin).
    """
    # Use the Borg pattern to share state between all instances. Details at
    # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/66531.
    __shared_state = dict(_initialize())
    __app_cache_cellar = {}

    def __init__(self):
        self.__dict__ = self.__shared_state

    def _reset(self):
        """
        Resets the cache to its initial (unseeded) state
        """
        if self._test_mode:
            for app in self.loaded_apps:
                self.__app_cache_cellar.setdefault(
                        app._meta.label, {}).update(app._meta.models)

        for app in self.loaded_apps:
            self._unload_app(app)

        self.__dict__ = self.__class__.__shared_state = dict(
                _initialize())

    def _reload(self):
        """
        Reloads the cache
        """
        self._reset()
        self._populate()

    def _populate(self):
        """
        Fill in all the cache information. This method is threadsafe, in the
        sense that every caller will see the same state upon return, and if the
        cache is already initialised, it does no work.
        """
        if self.loaded:
            return
        # Note that we want to use the import lock here - the app loading is
        # in many cases initiated implicitly by importing, and thus it is
        # possible to end up in deadlock when one thread initiates loading
        # without holding the importer lock and another thread then tries to
        # import something which also launches the app loading. For details of
        # this situation see #18251.
        imp.acquire_lock()
        try:
            if self.loaded:
                return
            pre_apps_loaded.send(sender=self)
            for app_name in settings.INSTALLED_APPS:
                if isinstance(app_name, (tuple, list)):
                    app_name, app_kwargs = app_name
                else:
                    app_kwargs = {}
                self.load_app(app_name, app_kwargs, can_postpone=True,
                        installed=True)
            if not self.nesting_level:
                for app_name, app_kwargs in self.postponed:
                    self.load_app(app_name, app_kwargs, installed=True)
                # check if there is more than one app with the same
                # db_prefix attribute
                models_apps = [app for app in self.loaded_apps if
                        app._meta.models_module]
                for app1 in models_apps:
                    for app2 in models_apps:
                        if (app1 != app2 and
                                app1._meta.db_prefix == app2._meta.db_prefix):
                            raise ImproperlyConfigured(
                                'The apps "%s" and "%s"'
                                ' have the same db_prefix "%s"'
                                % (app1, app2, app1._meta.db_prefix))
                for app in self.loaded_apps:
                    app.register_models()
                    post_load = getattr(app, 'post_load', None)
                    if post_load is not None and callable(post_load):
                        post_load()
                self.loaded = True
                self._setup_apps()
                # send the post_apps_loaded signal
                post_apps_loaded.send(sender=self, apps=self.loaded_apps)
                if self._test_mode:
                    self._test_repair()
        finally:
            imp.release_lock()

    def get_app_class(self, app_name):
        """
        Returns an app class for the given app name, which can be a
        dotted path to an app class or a dotted app module path.
        """
        try:
            app_path, app_attr = app_name.rsplit('.', 1)
        except ValueError:
            # First, return a new app class for the given module if
            # it's one level module path that can't be rsplit (e.g. 'myapp')
            return App.from_name(app_name)
        try:
            # Secondly, try to import the module directly,
            # because it'll fail with a class path or a bad path
            app_module = import_module(app_path)
        except ImportError, e:
            raise ImproperlyConfigured(
                "Could not import app '%s': %s" % (app_path, e))
        else:
            # Thirdly, check if there is the submodule and fall back if yes
            # If not look for the app class and do some type checks
            if not module_has_submodule(app_module, app_attr):
                try:
                    app_class = getattr(app_module, app_attr)
                except AttributeError:
                    raise ImproperlyConfigured(
                        "Could not find app '%s' in "
                        "module '%s'" % (app_attr, app_path))
                else:
                    if not issubclass(app_class, App):
                        raise ImproperlyConfigured(
                            "App '%s' must be a subclass of "
                            "'django.apps.App'" % app_name)
                    return app_class
        return App.from_name(app_name)

    def load_app(self, app_name, app_kwargs=None, can_postpone=False,
            installed=False, naive=False):
        """
        Loads the app with the provided fully qualified name, and returns the
        model module.

        Keyword Arguments:
            app_name: fully qualified name (e.g. 'django.contrib.auth')
            can_postpone: If set to True and the import raises an ImportError
                the loading will be postponed and tried again when all other
                modules are loaded.
            installed: is the app installed, such as listed in INSTALLED_APPS
        """
        if app_kwargs is None:
            app_kwargs = {}

        self.nesting_level += 1

        # check if an app instance with app_name already exists, if not
        # then create one
        app = self.get_app_instance(app_name.split('.')[-1])
        if app and not app._meta.installed:
            # a naive app was created by model imports
            # it will be removed when models are registered with app
            # at the end of the _populate function
            # reset app to None so a full app instance is created
            app = None
        if not app:
            app_class = self.get_app_class(app_name)
            if not app_class._meta.module and not naive:
                # In this case, the naive app created - and the time
                # the app options were created, no module could be imported
                # this is not an error for model imports, but is for app
                # being explicitly loaded
                # TODO this is temp disable in options as well
                # raise ImportError("the App %s could not be imported")
                pass
            app = app_class(**app_kwargs)
            self.loaded_apps.append(app)
            # Send the signal that the app has been loaded
            app_loaded.send(sender=app_class, app=app)
        else:
            # an existing app was found
            self.nesting_level -= 1
            if app._meta.name != app_name:
                raise ImproperlyConfigured(
                    'Multiple apps with the label %s can not be loaded' %
                    app._meta.label)

            app._meta.installed = installed
            return app._meta.models_module

        app._meta.installed = installed

        # if the app was created with a label only - it has no module known
        # and has no models module
        if not app._meta.module:
            self.nesting_level -= 1
            return app._meta.models_module

        self.nesting_level -= 1

        if installed:
            # we need to call this after each loaded app - to remove any
            # naive apps from self.loaded_apps, or it will be possible to have
            # multiple non-naive apps loaded because get_app_instance will
            # continue to return the naive version
            app.relocate_models()
        # TODO this will currently always return None
        # as we are postponing model import to register models
        # this is probably the best way to decouple model loading
        # from app loading
        return app._meta.models_module

    def _unload_app(self, app):
        for model in app._meta.models.itervalues():
            module = model.__module__
            if module in sys.modules:
                del sys.modules[module]

        if app._meta.module:
            app_module = app._meta.module.__name__
            if app_module in sys.modules:
                del sys.modules[app_module]

        if app._meta.models_module:
            models_module = app._meta.models_module.__name__
            if models_module in sys.modules:
                del sys.modules[models_module]
        app._meta.models = {}
        if app in self.loaded_apps:
            self.loaded_apps.remove(app)
        del(app)
        self._setup_apps()
        self._get_models_cache.clear()

    def unload_app(self, app_name=None, app_label=None):
        """
        Removes an app given either an app_name or app_label.

        This should generally only be used in a testing context.  Removing apps
        from a running Django process could lead to very unexpected results.
        """
        if app_name:
            for app in self.loaded_apps:
                if app._meta.name == app_name:
                    self._unload_app(app)
        elif app_label:
            app = self.get_app_instance(app_label)
            self._unload_app(app)

    def get_app_instance(self, app_label=None, app_name=None):
        """
        Returns the app instance that matches the given label.
        """
        if app_label:
            for app in self.loaded_apps:
                if app._meta.label == app_label:
                    return app
        elif app_name:
            for app in self.loaded_apps:
                if app._meta.name == app_name:
                    return app
        return None

    def find_app_by_models_module(self, models_module):
        """
        Returns the app instance that matches the models module
        """
        for app in self.loaded_apps:
            if app._meta.models_module == models_module:
                return app

    def ready(self):
        """
        Returns true if the model cache is fully populated.

        Useful for code that wants to cache the results of get_models() for
        themselves once it is safe to do so.
        """
        return self.loaded

    def get_models_modules(self):
        """
        Returns a list of all models modules.
        """
        self._populate()
        return [app._meta.models_module for app in self.loaded_apps
                if app._meta.models_module]

    def get_models_module(self, app_label, emptyOK=False):
        """
        Returns the module containing the models for the given app_label. If
        the app has no models in it and 'emptyOK' is True, returns None.
        """
        self._populate()
        app = self.get_app_instance(app_label)
        if app:
            mod = app._meta.models_module
            if mod is None:
                if emptyOK:
                    return None
            else:
                return mod
        raise ImproperlyConfigured(
                "App with label %s could not be found." % app_label)

    def get_app(self, app_label, emptyOK=False):
        warnings.warn(
            'get_app is deprecated, please use cache.get_models_module',
            PendingDeprecationWarning)
        return self.get_models_module(app_label, emptyOK=emptyOK)

    def get_apps(self):
        warnings.warn(
            'get_apps is deprecated, please use cache.get_models_modules',
            PendingDeprecationWarning)
        return self.get_models_modules()

    def get_app_errors(self):
        """
        Returns the map of known problems with the INSTALLED_APPS.
        """
        self._populate()
        errors = {}
        for app in self.loaded_apps:
            if app._meta.errors:
                errors.update({app._meta.label: app._meta.errors})
        return errors

    def get_models(self, app_mod=None,
                   include_auto_created=False, include_deferred=False,
                   only_installed=True):
        """
        Given a module containing models, returns a list of the models.
        Otherwise returns a list of all installed models.

        By default, auto-created models (i.e., m2m models without an
        explicit intermediate table) are not included. However, if you
        specify include_auto_created=True, they will be.

        By default, models created to satisfy deferred attribute
        queries are *not* included in the list of models. However, if
        you specify include_deferred, they will be.
        """
        cache_key = (app_mod, include_auto_created, include_deferred,
                     only_installed)
        try:
            return self._get_models_cache[cache_key]
        except KeyError:
            pass
        self._populate()
        app_list = []
        if app_mod:
            app = self.find_app_by_models_module(app_mod)
            if app:
                app_list = [app]
        else:
            app_list = self.loaded_apps
        model_list = []
        if only_installed:
            app_list = [app for app in app_list if app._meta.installed]
        for app in app_list:
            model_list.extend(
                model for model in app._meta.models.values()
                if ((not model._deferred or include_deferred) and
                    (not model._meta.auto_created or include_auto_created))
            )
        self._get_models_cache[cache_key] = model_list
        return model_list

    def get_model(self, app_label, model_name,
                  seed_cache=True, only_installed=True):
        """
        Returns the model matching the given app_label and case-insensitive
        model_name.

        Returns None if no model is found.
        """
        if seed_cache:
            self._populate()
        app = self.get_app_instance(app_label)
        if not app:
            return
        return app._meta.models.get(model_name.lower())

    def register_models(self, app_label, *models):
        """
        Register a set of models as belonging to an app.
        """
        app = self.get_app_instance(app_label)
        if not app:
            # create a 'naive' app
            # one that was created solely as a models holder
            app = App.from_label(app_label)()
            self.loaded_apps.append(app)
        for model in models:
            model_name = model._meta.object_name.lower()
            if model_name in app._meta.models:
                # The same model may be imported via different paths (e.g.
                # appname.models and project.appname.models). We use the source
                # filename as a means to detect identity.
                fname1 = os.path.abspath(
                        sys.modules[model.__module__].__file__)
                fname2 = os.path.abspath(sys.modules[
                            app._meta.models[model_name].__module__].__file__)
                # Since the filename extension could be .py the first time and
                # .pyc or .pyo the second time, ignore the extension when
                # comparing.
                if os.path.splitext(fname1)[0] == os.path.splitext(fname2)[0]:
                    continue
                else:
                    raise ImproperlyConfigured(
                            'A model named %s'
                            'is already registered for this app' % model_name)

            if app._meta.models_module is None:
                app._meta.models_module = sys.modules[model.__module__]
            app._meta.models[model_name] = model

        self._get_models_cache.clear()

    def _setup_apps(self):
        """
        Configures a namedtuple for easier access of loaded apps
        and their attributes
        """
        Apps = namedtuple(
                'Apps', [app._meta.label for app in self.loaded_apps])
        self.apps = Apps._make(self.loaded_apps)

    def _test_repair(self):
        """
        This is a huge hack - and is only used in a testing context

        Because of the way apps reference models and models reference apps
        a Python class imported in the scope of one test function, will not
        necasarily be reimported in another test funciton. As such the model
        metaclass is not called, and the model is not re-registered with a
        reset app_cache. This method keeps a copy of the model-app associations
        and reconnects them after a cache reset.
        """
        for app in self.loaded_apps:
            app_label = app._meta.label
            if app_label in self.__app_cache_cellar:
                for model, module in \
                        self.__app_cache_cellar[app_label].iteritems():
                    if model not in app._meta.models:
                        app._meta.models[model] = module
                for model in app._meta.models.itervalues():
                    model._meta.app = app
