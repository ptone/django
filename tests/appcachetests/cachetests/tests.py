#!/usr/bin/env python
import os
import sys
import threading

from django.apps import app_cache
from django.apps.cache import _initialize
from django.apps.signals import app_loaded, post_apps_loaded
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test.testcases import AppCacheTestCase
from django.utils.datastructures import SortedDict
from django.utils import unittest


class ReloadTests(AppCacheTestCase):
    """
    Tests for the _reload function
    """

    def test_reload(self):
        """
        Test reloading the app_cache
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_cache._populate()
        self.assertEquals(len(app_cache.loaded_apps), 1)
        self.assertEquals(app_cache.loaded_apps[0]._meta.name,
                'appcachetests.cachetests.model_app')
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.anothermodel_app',
                'appcachetests.cachetests.model_app')
        app_cache._reload()
        self.assertEquals(len(app_cache.loaded_apps), 2)
        self.assertEquals(app_cache.loaded_apps[0]._meta.name,
                'appcachetests.cachetests.anothermodel_app')

    def test_reload_register_models(self):
        """
        Test that models are registered with the app_cache again after it
        was reloaded
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_cache._populate()
        self.assertTrue('model_app' in [app._meta.label for app in app_cache.loaded_apps])
        app_cache._reload()
        self.assertTrue('model_app' in [app._meta.label for app in app_cache.loaded_apps])


class AppCacheReadyTests(AppCacheTestCase):
    """
    Tests for the ready function that indicates if the cache
    is fully populated.
    """

    def test_not_initialized(self):
        """
        Should return False if the AppCache hasn't been initialized
        """
        self.assertFalse(app_cache.ready())

    def test_load_app(self):
        """
        Should return False after executing the load_app function
        """
        app_cache.load_app('appcachetests.cachetests.nomodel_app')
        self.assertFalse(app_cache.ready())
        app_cache.load_app('appcachetests.cachetests.nomodel_app',
                can_postpone=True)
        self.assertFalse(app_cache.ready())

    def test_cache_ready(self):
        """
        populate should result in the cache being ready
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MyApp',)
        app_cache._populate()
        self.assertTrue(app_cache.ready())

class GetAppClassTests(AppCacheTestCase):
    """Tests for the get_app_class function"""

    def test_app_class(self):
        """
        Tests that the full path app class is returned
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MyApp',)
        from model_app.app import MyApp
        app_class = app_cache.get_app_class(settings.INSTALLED_APPS[0])
        self.assertEquals(app_class, MyApp)

    def test_one_level_module(self):
        """
        Tests that a new app class is generated for an one level app module
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_class = app_cache.get_app_class(settings.INSTALLED_APPS[0])
        self.assertEquals(app_class.__name__, 'ModelApp')

    def test_multi_level_module(self):
        """
        Tests that a new app class is generated for a multiple level app module
        """
        settings.INSTALLED_APPS = ('django.contrib.admin',)
        app_class = app_cache.get_app_class(settings.INSTALLED_APPS[0])
        self.assertEquals(app_class.__name__, 'Admin')

    def test_defunct_module(self):
        """
        Tests that a wrong module raises an ImproperlyConfigured exception
        """
        settings.INSTALLED_APPS = ('lalalala.admin',)
        self.assertRaises(ImproperlyConfigured, app_cache.get_app_class,
                          settings.INSTALLED_APPS[0])

    def test_missing_attribute(self):
        """
        Tests that a missing attribute raises an ImproperlyConfigured exception
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.nomodel_app.app.NotThereApp',)
        self.assertRaises(ImproperlyConfigured, app_cache.get_app_class,
                          settings.INSTALLED_APPS[0])

    def test_incorrect_subclass(self):
        """
        Tests that a class not subclassing django.apps.App raises an
        ImproperlyConfigured exception
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.nomodel_app.app.ObjectApp',)
        self.assertRaises(ImproperlyConfigured, app_cache.get_app_class,
                          settings.INSTALLED_APPS[0])


class GetModelsModulesTests(AppCacheTestCase):
    """Tests for the get_models_modules function"""

    def test_app_classes(self):
        """
        Test that the correct models modules are returned for app classes
        installed via the INSTALLED_APPS setting
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MyApp',)
        apps = app_cache.get_models_modules()
        self.assertTrue(app_cache.ready())
        self.assertEquals(apps[0].__name__,
                'appcachetests.cachetests.model_app.othermodels')

    def test_installed_apps(self):
        """
        Test that the correct models modules are returned for apps installed
        via the INSTALLED_APPS setting
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        apps = app_cache.get_models_modules()
        self.assertTrue(app_cache.ready())
        self.assertEquals(apps[0].__name__,
                'appcachetests.cachetests.model_app.models')

    def test_same_app_in_both_settings(self):
        """
        Test that if an App is listed multiple times in INSTALLED_APPS
        only one of them is loaded
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MyApp',
                'appcachetests.cachetests.model_app')
        apps = app_cache.get_models_modules()
        self.assertEquals(len(apps), 1)
        self.assertEquals(apps[0].__name__,
                'appcachetests.cachetests.model_app.othermodels')

    def test_empty_models(self):
        """
        Test that modules that don't contain models are not returned
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.nomodel_app',)
        self.assertEqual(app_cache.get_models_modules(), [])
        self.assertTrue(app_cache.ready())

    def test_db_prefix_exception(self):
        """
        Test that an exception is raised if two app instances
        have the same db_prefix attribute
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.anothermodel_app.app.MyOtherApp',
                'appcachetests.cachetests.model_app.app.MyOtherApp')
        self.assertRaises(ImproperlyConfigured, app_cache._populate)


class GetModelsModuleTests(AppCacheTestCase):
    """Tests for the get_models_module function"""

    def test_installed_apps(self):
        """
        Test that the correct module is returned when the app was installed
        via the INSTALLED_APPS setting
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        mod = app_cache.get_models_module('model_app')
        self.assertTrue(app_cache.ready())
        self.assertEquals(mod.__name__,
                'appcachetests.cachetests.model_app.models')

    def test_not_found_exception(self):
        """
        Test that an ImproperlyConfigured exception is raised if an app
        could not be found
        """
        self.assertRaises(ImproperlyConfigured, app_cache.get_models_module,
                          'notarealapp')
        self.assertTrue(app_cache.ready())

    def test_emptyOK(self):
        """
        Test that None is returned if emptyOK is True and the module
        has no models
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.nomodel_app',)
        module = app_cache.get_models_module('nomodel_app', emptyOK=True)
        self.assertTrue(app_cache.ready())
        self.failUnless(module is None)

    def test_exception_if_no_models(self):
        """
        Test that an ImproperlyConfigured exception is raised if the app
        has no modules and the emptyOK arg is False
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.nomodel_app',)
        self.assertRaises(ImproperlyConfigured, app_cache.get_models_module,
                          'nomodel_app')
        self.assertTrue(app_cache.ready())


class GetAppErrorsTests(AppCacheTestCase):
    """Tests for the get_app_errors function"""

    def test_get_app_errors(self):
        """Test that the function returns an empty dict"""
        self.assertEqual(app_cache.get_app_errors(), {})
        self.assertTrue(app_cache.ready())


class GetModelsTests(AppCacheTestCase):
    """Tests for the get_models function"""

    def test_installed(self):
        """
        Test that only models from apps are returned that are listed in
        the INSTALLED_APPS setting
        """
        from anothermodel_app.models import Person
        from model_app.models import Person
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        models = app_cache.get_models()
        self.assertTrue(app_cache.ready())
        self.assertEqual(models, [Person])

    def test_not_only_installed(self):
        """
        Test that not only installed models are returned
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        from anothermodel_app.models import Job, Person, Contact
        from model_app.models import Person as p2
        app_cache._populate()
        models = app_cache.get_models(only_installed=False)
        self.assertTrue(app_cache.ready())
        self.assertEqual(set(models), set([Job, Person, Contact, p2]))

    def test_app_mod(self):
        """
        Test that the correct models are returned if an models module is
        passed and the app is listed in INSTALLED_APPS
        """
        from model_app import models
        from model_app.models import Person
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',
                'appcachetests.cachetests.anothermodel_app')
        models_list = app_cache.get_models(app_mod=models)
        self.assertTrue(app_cache.ready())
        self.assertEqual(models_list, [Person])

    def test_app_mod_not_installed(self):
        """
        Test that no models are returned when a models module is
        passed and the app is _not_ listed in INSTALLED_APPS
        """
        from appcachetests.cachetests.model_app import models
        from appcachetests.cachetests.model_app.models import Person
        loaded_models = app_cache.get_models(app_mod=models)
        self.assertEqual(loaded_models, [])

    def test_include_auto_created(self):
        """
        Test that auto created models are included
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.anothermodel_app',)
        app_cache._populate()
        app_cache._reload()
        from anothermodel_app.models import Job, Person
        models = app_cache.get_models(include_auto_created=True)
        self.assertTrue(app_cache.ready())
        self.assertEqual(models[0], Job)
        self.assertEqual(models[1].__name__, 'Person_jobs')
        self.assertEqual(models[2], Person)

    def test_related_objects_cache(self):
        """
        Test that the related objects app_cache is filled correctly
        """
        from anothermodel_app.models import Contact
        self.assertEqual(Contact._meta.get_all_field_names(),
                         ['id', 'person'])

    def test_related_many_to_many_cache(self):
        """
        Test that the related m2m cache is filled correctly
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.anothermodel_app',)
        app_cache._populate()
        from anothermodel_app.models import Job
        self.assertEqual(Job._meta.get_all_field_names(),
                         ['id', 'name', 'person'])


class GetModelTests(AppCacheTestCase):
    """Tests for the get_model function"""

    def test_seeded_only_installed_valid(self):
        """
        Test that the correct model is returned if the cache is seeded
        and only models from apps listed in INSTALLED_APPS should be returned
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        model = app_cache.get_model('model_app', 'Person')
        self.assertEqual(model.__name__, 'Person')
        self.assertTrue(app_cache.ready())

    def test_seeded_only_installed_invalid(self):
        """
        Test that None is returned if the cache is seeded but the model
        was not registered with the cache
        """
        model = app_cache.get_model('model_app', 'Person')
        self.assertEqual(model, None)
        self.assertTrue(app_cache.ready())

    def test_unseeded_only_installed_invalid(self):
        """
        Test that None is returned if the cache is unseeded and the model
        was not registered with the cache
        """
        model = app_cache.get_model('model_app', 'Person', seed_cache=False)
        self.assertEqual(model, None)
        self.assertFalse(app_cache.ready())

    def test_seeded_all_models_valid(self):
        """
        Test that the correct model is returned if the cache is seeded and
        all models (including unbound) should be returned
        """
        app_cache._populate()
        from model_app.models import Person
        model = app_cache.get_model('model_app', 'Person',
                only_installed=False)
        self.assertEquals(model, Person)

    def test_seeded_all_models_invalid(self):
        """
        Test that None is returned if the cache is seeded and all models
        should be returned, but the model wasnt registered with the cache
        """
        app_cache._populate()
        model = app_cache.get_model('model_app', 'Person',
                only_installed=False)
        self.assertEquals(model, None)

    def test_unseeded_all_models_valid(self):
        """
        Test that the correct model is returned if the cache is unseeded and
        all models should be returned
        """
        from model_app.models import Person
        model = app_cache.get_model('model_app', 'Person',
                seed_cache=False, only_installed=False)
        self.assertEquals(model, Person)

    def test_unseeded_all_models_invalid(self):
        """
        Test that None is returned if the cache is unseeded, all models should
        be returned but the model wasn't registered with the cache
        """
        model = app_cache.get_model('model_app', 'Person',
                seed_cache=False, only_installed=False)
        self.assertEquals(model, None)

    def test_instance_get_model(self):
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_cache._populate()
        from model_app.models import Person
        model_app = app_cache.get_app_instance('model_app')
        fetched_model = model_app.get_model('person')
        self.assertEquals(fetched_model, Person)

class LoadAppTests(AppCacheTestCase):
    """Tests for the load_app function"""

    def test_with_models(self):
        """
        Test that an app instance is created and the models
        module is returned
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_cache._populate()
        app = app_cache.loaded_apps[0]
        mod = app._meta.models_module
        self.assertEqual(len(app_cache.loaded_apps), 1)
        self.assertEqual(app._meta.name, 'appcachetests.cachetests.model_app')
        self.assertEqual(app._meta.models_module.__name__,
                'appcachetests.cachetests.model_app.models')
        self.assertEqual(mod.__name__,
                'appcachetests.cachetests.model_app.models')

    def test_with_inheritance(self):
        from model_app.app import MyApp
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MyOtherApp',)
        app_cache._populate()
        app = app_cache.loaded_apps[0]
        mod = app._meta.models_module
        self.assertEqual(app._meta.name,
                'appcachetests.cachetests.model_app')
        self.assertEqual(app._meta.models_module.__name__,
                'appcachetests.cachetests.model_app.othermodels')
        self.assertEqual(mod.__name__, 'appcachetests.cachetests.model_app.othermodels')
        self.assertEqual(app.__class__.__bases__, (MyApp,))
        self.assertEqual(app._meta.models_path,
                'appcachetests.cachetests.model_app.othermodels')
        self.assertEqual(app._meta.db_prefix, 'nomodel_app')
        self.assertEqual(app._meta.verbose_name, 'model_app')

    def test_with_multiple_inheritance(self):
        from model_app.app import MyOtherApp
        from django.apps import App
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MySecondApp',)
        app_cache._populate()
        app = app_cache.loaded_apps[0]
        mod = app._meta.models_module
        self.assertEqual(app._meta.name, 'appcachetests.cachetests.model_app')
        self.assertEqual(app._meta.models_module.__name__,
                'appcachetests.cachetests.model_app.models')
        self.assertEqual(mod.__name__,
                'appcachetests.cachetests.model_app.models')
        self.assertEqual(app.__class__.__bases__, (MyOtherApp,))
        self.assertEqual(app._meta.models_path,
                'appcachetests.cachetests.model_app.models')
        self.assertEqual(app._meta.db_prefix, 'nomodel_app')
        self.assertEqual(app._meta.verbose_name, 'model_app')

    def test_with_complicated_inheritance(self):
        from model_app.app import MySecondApp, YetAnotherApp
        from django.apps import App
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MyThirdApp',)
        app_cache._populate()
        app = app_cache.loaded_apps[0]
        mod = app._meta.models_module
        self.assertEqual(app._meta.name, 'appcachetests.cachetests.model_app')
        self.assertEqual(app._meta.models_module.__name__,
                'appcachetests.cachetests.model_app.yetanother')
        self.assertEqual(mod.__name__,
                'appcachetests.cachetests.model_app.yetanother')
        self.assertEqual(app.__class__.__bases__, (YetAnotherApp, MySecondApp))
        self.assertEqual(app._meta.models_path,
                'appcachetests.cachetests.model_app.yetanother')
        self.assertEqual(app._meta.db_prefix, 'nomodel_app')
        self.assertEqual(app._meta.verbose_name, 'model_app')

    def test_with_custom_models(self):
        """
        Test that custom models are imported correctly, if the App specifies
        an models_path attribute
        """
        from model_app.app import MyApp
        mod = app_cache.load_app(
                'appcachetests.cachetests.model_app.app.MyApp',
                can_postpone=False)
        app = app_cache.loaded_apps[0]
        self.assertEqual(app._meta.models_module.__name__,
                'appcachetests.cachetests.model_app.othermodels')
        self.assertTrue(isinstance(app, MyApp))
        self.assertEqual(mod.__name__,
                'appcachetests.cachetests.model_app.othermodels')

    def test_without_models(self):
        """
        Test that an app instance is created even when there are
        no models provided
        """
        mod = app_cache.load_app('appcachetests.cachetests.nomodel_app')
        app = app_cache.loaded_apps[0]
        self.assertEqual(len(app_cache.loaded_apps), 1)
        self.assertEqual(app._meta.name,
                'appcachetests.cachetests.nomodel_app')
        self.assertEqual(mod, None)

    def test_loading_the_same_app_twice(self):
        """
        Test that loading the same app twice results in only one app instance
        being created
        """
        mod = app_cache.load_app('appcachetests.cachetests.model_app',
                installed=True)
        mod2 = app_cache.load_app('appcachetests.cachetests.model_app',
                installed=True)
        self.assertEqual(len(app_cache.loaded_apps), 1)
        self.assertEqual('model_app', app_cache.loaded_apps[0]._meta.label)

    def test_importerror(self):
        """
        Test that an ImportError exception is raised if a package cannot
        be imported
        """
        settings.INSTALLED_APPS = ('garageland',)
        self.assertRaises(ImportError, app_cache._populate)

    def test_bad_models_path(self):
        """
        Test that an error is raised if an invalid models_path is used in Meta
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MyBadModelsPathApp',)
        self.assertRaises(ImportError, app_cache._populate)

    def test_bad_installed_apps_string(self):
        """
        Test that a non existant module in installed apps raises an error
        """
        settings.INSTALLED_APPS = ('no.such.path',)
        self.assertRaises(ImproperlyConfigured, app_cache._populate)

    def test_bad_appclass(self):
        """
        Test that an invalid path to an App subclass raises an error
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.NoSuchApp',)
        self.assertRaises(ImproperlyConfigured, app_cache._populate)

    def test_post_load_hook(self):
        """
        Test that the post load hook is fired
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MyApp',)
        settings.POST_LOAD_HOOK_FIRED = False
        app_cache._populate()
        self.assertTrue(settings.POST_LOAD_HOOK_FIRED)


class RegisterModelsTests(AppCacheTestCase):
    """Tests for the register_models function"""

    def test_seeded_cache(self):
        """
        Test that the models are attached to the correct app instance
        in a seeded cache
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_cache._populate()
        self.assertTrue(app_cache.ready())
        app_models = app_cache.loaded_apps[0]._meta.models.values()
        self.assertEqual(len(app_models), 1)
        self.assertEqual(app_models[0].__name__, 'Person')

    def test_seeded_cache_invalid_app(self):
        """
        Test that registering models with an app that doesn't have an app
        instance works
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_cache._populate()
        self.assertTrue(app_cache.ready())
        from model_app.models import Person
        app_cache.register_models('model_app_NONEXISTENT', *(Person,))
        naive_app = app_cache.get_app_instance('model_app_NONEXISTENT')
        loaded_person = naive_app._meta.models['person']
        self.assertEquals(loaded_person, Person)

    def test_unseeded_cache(self):
        """
        Test that models can be registered with an unseeded cache
        """
        from model_app.models import Person
        self.assertFalse(app_cache.ready())
        naive_app = app_cache.get_app_instance('model_app')
        loaded_person = naive_app._meta.models['person']
        self.assertEquals(loaded_person, Person)


class GetAppInstanceTests(AppCacheTestCase):
    """Tests for the get_app_instance function"""

    def test_seeded(self):
        """
        Test that the correct app is returned when the cache is seeded
        """
        from django.apps import App
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_cache._populate()
        self.assertTrue(app_cache.ready())
        app = app_cache.get_app_instance('model_app')
        self.assertEquals(app._meta.name,
                'appcachetests.cachetests.model_app')
        self.assertTrue(isinstance(app, App))
        self.assertEquals(app.__repr__(),
                '<App: appcachetests.cachetests.model_app>')

    def test_seeded_invalid(self):
        """
        Test that None is returned if an app could not be found
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_cache._populate()
        self.assertTrue(app_cache.ready())
        app = app_cache.get_app_instance('model_app_NOTVALID')
        self.assertEquals(app, None)

    def test_unseeded(self):
        """
        Test that the correct app is returned when the cache is unseeded
        """
        from django.apps import App
        app_cache.load_app('appcachetests.cachetests.model_app')
        self.assertFalse(app_cache.ready())
        app = app_cache.get_app_instance('model_app')
        self.assertEquals(app._meta.name, 'appcachetests.cachetests.model_app')
        self.assertTrue(isinstance(app, App))

    def test_option_override(self):
        """
        Tests that options of the app can be overridden in the settings
        """
        settings.INSTALLED_APPS = (
            ('django.contrib.admin', {
                'spam': 'spam',
            }),
            ('appcachetests.cachetests.model_app.app.MyOverrideApp', {
                'db_prefix': 'foobar_prefix',
                'eggs': 'eggs',
            }),
            ('django.contrib.auth.app.AuthApp', {
                'user_model': 'django.contrib.auth.tests.custom_user.CustomUser',
                }),
        )
        app_cache._populate()
        admin = app_cache.get_app_instance('admin')
        self.assertRaises(AttributeError, lambda: admin._meta.spam)
        self.assertEquals(admin.spam, 'spam')
        model_app = app_cache.get_app_instance('model_app')
        self.assertEquals(model_app._meta.db_prefix, 'foobar_prefix')
        self.assertEquals(model_app.eggs, 'eggs')

    def test_conflicting_option_override(self):
        """
        Tests that when overrdiding the db_prefix option in the settings
        it still throws an exception
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.anothermodel_app.app.MyOtherApp'
            'appcachetests.cachetests.anothermodel_app.app.MyOtherApp',
            ('appcachetests.cachetests.model_app.app.MyOtherApp', {
                'db_prefix': 'nomodel_app',
            }),
        )
        self.assertRaises(ImproperlyConfigured, app_cache._populate)

    def test_class_attribute(self):
        """
        Tests that class attributes of apps are correctly set in the
        instances, not only the _meta options.
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MyApp',)
        app_cache._reload()
        model_app = app_cache.get_app_instance('model_app')
        self.assertEquals(model_app._meta.db_prefix, 'model_app')
        self.assertEquals(model_app.some_attribute, True)

    def test_find_app_by_models_module(self):
        """
        Tests that an app can be found using only its models module
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app.app.MyApp',)
        app_cache._populate()
        from appcachetests.cachetests.model_app import othermodels
        app = app_cache.get_app_instance('model_app')
        found_app = app_cache.find_app_by_models_module(othermodels)
        self.assertEquals(found_app, app)

    def test_apps_collection_access(self):
        """
        test the namedtuple convenience collection
        """
        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_cache._populate()
        app1 = app_cache.get_app_instance('model_app')
        app2 = app_cache.apps.model_app
        self.assertEquals(app1, app2)

class SignalTests(AppCacheTestCase):
    """Tests for the signals"""

    def setUp(self):
        super(SignalTests, self).setUp()
        self.signal_fired = False

    def test_app_loaded(self):
        """
        Test the app_loaded signal
        """
        # connect the callback before the cache is initialized
        def app_loaded_callback(sender, app, **kwargs):
            self.assertEqual(app._meta.name,
                    'appcachetests.cachetests.model_app')
            self.signal_fired = True
        app_loaded.connect(app_loaded_callback)

        settings.INSTALLED_APPS = ('appcachetests.cachetests.model_app',)
        app_cache._populate()
        self.assertTrue(app_cache.ready())
        self.assertTrue(self.signal_fired)

    def test_post_apps_loaded(self):
        """
        Test the post_apps_loaded signal
        """
        settings.INSTALLED_APPS = (
                'appcachetests.cachetests.model_app',
                'appcachetests.cachetests.anothermodel_app')
        def callback(sender, apps, **kwargs):
            self.assertEqual(len(apps), 2)
            self.assertEqual(apps[0]._meta.name,
                    'appcachetests.cachetests.model_app')
            self.assertEqual(apps[1]._meta.name,
                    'appcachetests.cachetests.anothermodel_app')
            self.signal_fired = True
        post_apps_loaded.connect(callback)
        app_cache._populate()
        self.assertTrue(app_cache.ready())
        self.assertTrue(self.signal_fired)


class EggLoadingTests(AppCacheTestCase):
    """Tests loading apps from eggs"""

    def setUp(self):
        super(EggLoadingTests, self).setUp()
        self.egg_dir = '%s/eggs' % os.path.abspath(os.path.dirname(__file__))
        self.old_path = sys.path[:]

    def tearDown(self):
        super(EggLoadingTests, self).tearDown()
        sys.path = self.old_path

    def test_egg1(self):
        """
        Models module can be loaded from an app in an egg
        """
        egg_name = '%s/modelapp.egg' % self.egg_dir
        sys.path.append(egg_name)
        settings.INSTALLED_APPS = ('app_with_models',)
        app_cache._populate()
        models_module = app_cache.get_app_instance(
                'app_with_models')._meta.models_module
        self.assertFalse(models_module is None)

    def test_egg2(self):
        """
        Loading an app from an egg that has no models returns no models
        (and no error)
        """
        egg_name = '%s/nomodelapp.egg' % self.egg_dir
        sys.path.append(egg_name)
        models = app_cache.load_app('app_no_models')
        self.assertTrue(models is None)

    def test_egg3(self):
        """
        Models module can be loaded from an app located under an egg's
        top-level package
        """
        egg_name = '%s/omelet.egg' % self.egg_dir
        sys.path.append(egg_name)
        settings.INSTALLED_APPS = ('omelet.app_with_models',)
        app_cache._populate()
        models_module = app_cache.get_app_instance(
                'app_with_models')._meta.models_module
        self.assertFalse(models_module is None)

    def test_egg4(self):
        """
        Loading an app with no models from under the top-level egg package
        generates no error
        """
        egg_name = '%s/omelet.egg' % self.egg_dir
        sys.path.append(egg_name)
        models = app_cache.load_app('omelet.app_no_models')
        self.assertTrue(models is None)

    def test_egg5(self):
        """
        Loading an app from an egg that has an import error in its models
        module raises that error
        """
        egg_name = '%s/brokenapp.egg' % self.egg_dir
        sys.path.append(egg_name)
        settings.INSTALLED_APPS = ('broken_app',)
        self.assertRaises(ImportError, app_cache._populate)
        # TODO this will require a separate tests - as once populate runs
        # it can't be run a second time in a single test, and load() does
        # not trigger imports by itself
        # try:
            # app_cache.load_app('broken_app')
        # except ImportError, e:
            # # Make sure the message is indicating the actual
            # # problem in the broken app.
            # self.assertTrue("modelz" in e.args[0])

if __name__ == '__main__':
    unittest.main()
