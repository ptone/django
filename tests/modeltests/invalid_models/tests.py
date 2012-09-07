import sys

from django.apps import app_cache
from django.core.management.validation import get_validation_errors
from django.db.models.signals import post_syncdb
from django.utils import unittest
from django.utils.six import StringIO
from django.test.utils import override_settings


class InvalidModelTestCase(unittest.TestCase):
    """Import an application with invalid models and test the exceptions."""

    def setUp(self):
        # Make sure sys.stdout is not a tty so that we get errors without
        # coloring attached (makes matching the results easier). We restore
        # sys.stderr afterwards.
        app_cache.load_app("modeltests.invalid_models.invalid_models_app",
                installed=True)
        app = app_cache.get_app_instance('invalid_models_app')
        app.register_models()
        self.old_stdout = sys.stdout
        self.stdout = StringIO()
        sys.stdout = self.stdout
        # self.sync_receivers = post_syncdb.receivers
        # post_syncdb.receivers = []

    def tearDown(self):
        sys.stdout = self.old_stdout
        # post_syncdb.receivers = self.sync_receivers
        app_cache.unload_app(app_label="invalid_models_app")

    # Technically, this isn't an override -- TEST_SWAPPED_MODEL must be
    # set to *something* in order for the test to work. However, it's
    # easier to set this up as an override than to require every developer
    # to specify a value in their test settings.
    @override_settings(TEST_SWAPPED_MODEL='invalid_models.Target')
    def test_invalid_models(self):
        module = app_cache.get_models_module('invalid_models_app')
        count = get_validation_errors(self.stdout, module)
        self.stdout.seek(0)
        error_log = self.stdout.read()
        actual = error_log.split('\n')
        expected = module.model_errors.split('\n')

        unexpected = [err for err in actual if err not in expected]
        missing = [err for err in expected if err not in actual]
        self.assertFalse(unexpected, "Unexpected Errors: " + '\n'.join(unexpected))
        self.assertFalse(missing, "Missing Errors: " + '\n'.join(missing))
