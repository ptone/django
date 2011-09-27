"""
Decorators for views based on HTTP headers.
"""

from calendar import timegm
from functools import wraps

from django.utils.decorators import decorator_from_middleware, available_attrs
from django.utils.http import http_date, parse_http_date_safe, parse_etags, quote_etag
from django.utils.log import getLogger
from django.middleware.http import ConditionalGetMiddleware
from django.http import HttpResponseNotAllowed, HttpResponseNotModified, HttpResponse
from django.views.mixins.http import HttpConditionMixin

conditional_page = decorator_from_middleware(ConditionalGetMiddleware)

logger = getLogger('django.request')


def require_http_methods(request_method_list):
    """
    Decorator to make a view only accept particular request methods.  Usage::

        @require_http_methods(["GET", "POST"])
        def my_view(request):
            # I can assume now that only GET or POST requests make it this far
            # ...

    Note that request methods should be in uppercase.
    """
    def decorator(func):
        @wraps(func, assigned=available_attrs(func))
        def inner(request, *args, **kwargs):
            if request.method not in request_method_list:
                logger.warning('Method Not Allowed (%s): %s', request.method, request.path,
                    extra={
                        'status_code': 405,
                        'request': request
                    }
                )
                return HttpResponseNotAllowed(request_method_list)
            return func(request, *args, **kwargs)
        return inner
    return decorator

require_GET = require_http_methods(["GET"])
require_GET.__doc__ = "Decorator to require that a view only accept the GET method."

require_POST = require_http_methods(["POST"])
require_POST.__doc__ = "Decorator to require that a view only accept the POST method."

require_safe = require_http_methods(["GET", "HEAD"])
require_safe.__doc__ = "Decorator to require that a view only accept safe methods: GET and HEAD."

condition = HttpConditionMixin.as_decorator

# Shortcut decorators for common cases based on ETag or Last-Modified only
def etag(etag_func):
    return condition(etag_func=etag_func)

def last_modified(last_modified_func):
    return condition(last_modified_func=last_modified_func)

