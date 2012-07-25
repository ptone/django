from __future__ import absolute_import

import os
import sys

from django.apps import app_cache
from django.conf import settings
from django.core.management import call_command
from django.db.models.signals import post_syncdb
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings

from modeltests.proxy_model_inheritance.models import (ConcreteModel, ConcreteModelSubclass,
    ConcreteModelSubclassProxy)


class ProxyModelInheritanceTests(TransactionTestCase):
    """
    Proxy model inheritance across apps can result in syncdb not creating the table
    for the proxied model (as described in #12286).  This test creates two dummy
    apps and calls syncdb, then verifies that the table has been created.
    """

    def setUp(self):
        self.old_sys_path = sys.path[:]
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        app_cache.load_app('modeltests.proxy_model_inheritance.app1',
                installed=True)
        app_cache.load_app('modeltests.proxy_model_inheritance.app2',
                installed=True)
        app2 = app_cache.get_app_instance('app2')
        # loading an app does not by itself trigger model imports
        app2.register_models()

    def tearDown(self):
        sys.path = self.old_sys_path
        app_cache.unload_app(app_name='modeltests.proxy_model_inheritance.app1')
        app_cache.unload_app(app_name='modeltests.proxy_model_inheritance.app2')

    def test_table_exists(self):
        call_command('syncdb', verbosity=0)
        from modeltests.proxy_model_inheritance.app1.models import ProxyModel
        from modeltests.proxy_model_inheritance.app2.models import NiceModel
        self.assertEqual(NiceModel.objects.all().count(), 0)
        self.assertEqual(ProxyModel.objects.all().count(), 0)


class MultiTableInheritanceProxyTest(TestCase):

    def test_model_subclass_proxy(self):
        """
        Deleting an instance of a model proxying a multi-table inherited
        subclass should cascade delete down the whole inheritance chain (see
        #18083).

        """
        instance = ConcreteModelSubclassProxy.objects.create()
        instance.delete()
        self.assertEqual(0, ConcreteModelSubclassProxy.objects.count())
        self.assertEqual(0, ConcreteModelSubclass.objects.count())
        self.assertEqual(0, ConcreteModel.objects.count())
