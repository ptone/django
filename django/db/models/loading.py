"Utilities for loading models and the modules that contain them."
import warnings

from django.apps import App, AppCache, cache

__all__ = (
    'App', 'get_apps', 'get_app', 'get_app_errors',
    'get_models', 'get_model', 'register_models', 'load_app',
    'app_cache_ready'
)


# Imported here for backwards compatibility

# These methods were always module level, so are kept that way for backwards
# compatibility.
get_apps = cache.get_apps
get_app = cache.get_app
get_app_errors = cache.get_app_errors
get_models = cache.get_models
get_model = cache.get_model
register_models = cache.register_models
load_app = cache.load_app
app_cache_ready = cache.app_cache_ready

warnings.warn(
    'The utilities in django.db.models.loading have been moved to '
    'django.apps.cache. Please update your code accordingly.',
    PendingDeprecationWarning)

