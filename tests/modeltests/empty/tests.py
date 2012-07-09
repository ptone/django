from __future__ import absolute_import

from django.apps import app_cache
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from .models import Empty


class EmptyModelTests(TestCase):
    def test_empty(self):
        m = Empty()
        self.assertEqual(m.id, None)
        m.save()
        m2 = Empty.objects.create()
        self.assertEqual(len(Empty.objects.all()), 2)
        self.assertTrue(m.id is not None)
        existing = Empty(m.id)
        existing.save()

class NoModelTests(TestCase):
    """
    Test for #7198 to ensure that the proper error message is raised
    when attempting to load an app with no models.py file.

    Because the test runner won't currently load a test module with no
    models.py file, this TestCase instead lives in this module.

    It seemed like an appropriate home for it.
    """
    def setUp(self):
        app_cache.load_app("modeltests.empty.no_models", installed=True)

    def tearDown(self):
        app_cache.unload_app(app_label='no_models')

    def test_no_models(self):
        with self.assertRaisesRegexp(ImproperlyConfigured,
                    'App with label no_models could not be found.'):
            app_cache.get_models_module('no_models')

    def test_no_models_emptyOK(self):
        self.assertEquals(app_cache.get_models_module('no_models', emptyOK=True), None)

