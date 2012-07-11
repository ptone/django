"Utilities for loading models and the modules that contain them."
import warnings

from django.apps import App, AppCache, app_cache

__all__ = (
    'App', 'get_apps', 'get_app', 'get_app_errors',
    'get_models', 'get_model', 'register_models', 'load_app',
    'app_cache_ready'
)


# Imported here for backwards compatibility

# These methods were always module level, so are kept that way for backwards
# compatibility.
get_apps = app_cache.get_models_modules
get_app = app_cache.get_models_module
get_app_errors = app_cache.get_app_errors
get_models = app_cache.get_models
get_model = app_cache.get_model
register_models = app_cache.register_models
load_app = app_cache.load_app
app_cache_ready = app_cache.ready

cache = app_cache

warnings.warn(
    'The utilities in django.db.models.loading have been moved to '
    'django.apps.cache. Please update your code accordingly.',
    PendingDeprecationWarning)

