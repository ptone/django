import copy
import sys

from django.core.management.validation import get_validation_errors
from django.db.models.loading import cache
from django.utils import unittest
from django.utils.six import StringIO
from django.test.utils import override_settings


class InvalidModelTestCase(unittest.TestCase):
    """Import an application with invalid models and test the exceptions."""

    def setUp(self):
        # Make sure sys.stdout is not a tty so that we get errors without
        # coloring attached (makes matching the results easier). We restore
        # sys.stderr afterwards.
        self.old_stdout = sys.stdout
        self.stdout = StringIO()
        sys.stdout = self.stdout

    def tearDown(self):
        cache._reload()
        sys.stdout = self.old_stdout

    @override_settings(INSTALLED_APPS=("modeltests.invalid_models.invalid_models",))
    def test_invalid_models(self):
        cache._reload()
        module = cache.get_app('invalid_models')
        count = get_validation_errors(self.stdout, module)
        self.stdout.seek(0)
        error_log = self.stdout.read()
        actual = error_log.split('\n')
        expected = module.model_errors.split('\n')

        unexpected = [err for err in actual if err not in expected]
        missing = [err for err in expected if err not in actual]
        self.assertFalse(unexpected, "Unexpected Errors: " + '\n'.join(unexpected))
        self.assertFalse(missing, "Missing Errors: " + '\n'.join(missing))
