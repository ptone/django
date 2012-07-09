from django.apps import app_cache
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ImproperlyConfigured
from django.db import connection
from django.db.models.query import Q
from django.db.models.expressions import F
from django.db.models.manager import Manager
from django.db.models.base import Model
from django.db.models.aggregates import *
from django.db.models.fields import *
from django.db.models.fields.subclassing import SubfieldBase
from django.db.models.fields.files import FileField, ImageField
from django.db.models.fields.related import ForeignKey, OneToOneField, ManyToManyField, ManyToOneRel, ManyToManyRel, OneToOneRel
from django.db.models.deletion import CASCADE, PROTECT, SET, SET_NULL, SET_DEFAULT, DO_NOTHING, ProtectedError
from django.db.models import signals
from django.utils.decorators import wraps


# These have always been exposed through django.models, so are represented here
# for backwards compatability
get_apps = app_cache.get_models_modules
get_app = app_cache.get_models_module
get_app_errors = app_cache.get_app_errors
get_models = app_cache.get_models
get_model = app_cache.get_model
register_models = app_cache.register_models

def permalink(func):
    """
    Decorator that calls urlresolvers.reverse() to return a URL using
    parameters returned by the decorated function "func".

    "func" should be a function that returns a tuple in one of the
    following formats:
        (viewname, viewargs)
        (viewname, viewargs, viewkwargs)
    """
    from django.core.urlresolvers import reverse
    @wraps(func)
    def inner(*args, **kwargs):
        bits = func(*args, **kwargs)
        return reverse(bits[0], None, *bits[1:3])
    return inner
