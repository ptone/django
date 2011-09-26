"""
Mixin classes for modifying HTTP headers
"""

from django.http import HttpResponseNotModified, HttpResponse
from django.utils.decorators import ViewDecoratorMixin
from django.utils.http import http_date, parse_http_date_safe, parse_etags, quote_etag
from django.utils.log import getLogger

logger = getLogger('django.request')

class HttpConditionMixin(ViewDecoratorMixin):

    etag = None
    last_modified = None

    def __init__(self):
        self.if_modified_since = None
        self.if_match = None
        self.if_none_match = None
        self.etags = []

    def get_http_headers(self):
        # Get HTTP request headers
        self.if_modified_since = self.request.META.get("HTTP_IF_MODIFIED_SINCE")
        if self.if_modified_since:
            self.if_modified_since = parse_http_date_safe(self.if_modified_since)
        self.if_none_match = self.request.META.get("HTTP_IF_NONE_MATCH")
        self.if_match = self.request.META.get("HTTP_IF_MATCH")
        if self.if_none_match or self.if_match:
            # There can be more than one ETag in the request, so we
            # consider the list of values.
            try:
                self.etags = parse_etags(self.if_none_match or self.if_match)
            except ValueError:
                # In case of invalid etag ignore all ETag headers.
                # Apparently Opera sends invalidly quoted headers at times
                # (we should be returning a 400 response, but that's a
                # little extreme) -- this is Django bug #10681.
                self.if_none_match = None
                self.if_match = None

    def get_etag(self):
        """
        returns the resources Etag
        """

        return self.etag

    def get_last_modified(self):
        """
        returns the resources last modified date
        """

        return self.last_modified

    def check_etags(self):
        if ((self.if_none_match and (self.get_etag() in self.etags)) or ("*" in self.etags and self.get_etag())):
            return True
        if (self.if_match and not (self.get_etag() in self.etags)):
            return True
        return False

    def check_last_modified(self):
        if self.get_last_modified() is None:
            return True
        if ((self.get_last_modified() and self.if_modified_since) and
                (self.get_last_modified() <= self.if_modified_since)):
            return True
        return False

    def precondition_failed(self):
        logger.warning('Precondition Failed: %s' % self.request.path,
            extra={
                'status_code': 412,
                'request': self.request
            }
        )
        return HttpResponse(status=412)

    def test_conditions(self):
        # Currently this completely mimics the logic flow of the original decorator
        # ideally it would be nice to see a clearer factoring with methods if
        # possible
        #
        if ((self.if_match and (self.if_modified_since or self.if_none_match)) or
            (self.if_match and self.if_none_match)):
            # we only get here if an invalid set of conditions are
            # specified
            return None
        if ((self.if_none_match and (self.get_etag() in self.etags or
                "*" in self.etags and self.get_etag())) and
                (not self.if_modified_since or
                    (self.get_last_modified() and self.if_modified_since and
                    self.get_last_modified() <= self.if_modified_since))):
            if self.request.method in ("GET", "HEAD"):
                return HttpResponseNotModified()
            else:
                return self.precondition_failed()
        elif self.if_match and ((not self.get_etag() and "*" in self.etags) or
                (self.get_etag() and self.get_etag() not in self.etags)):
            return self.precondition_failed()
        elif (not self.if_none_match and self.request.method == "GET" and
                self.get_last_modified() and self.if_modified_since and
                self.get_last_modified() <= self.if_modified_since):
            return HttpResponseNotModified()

    def set_headers(self, response):
        # Set relevant headers on the response if they don't already exist.
        if self.get_last_modified() and not response.has_header('Last-Modified'):
            response['Last-Modified'] = http_date(self.get_last_modified())
        if self.get_etag() and not response.has_header('ETag'):
            response['ETag'] = quote_etag(self.get_etag())

    def dispatch(self, request, *args, **kwargs):
        response = None
        response = self.test_conditions()
        if response is None:
            response = super(HTTPConditionMixin, self).dispatch(
                    request, *args, **kwargs)

        self.set_headers(response)
        return response

    def decorate_wrapped(self, view, request, *args, **kwargs):
        self.request = request
        print request
        if 'etag_func' in kwargs:
            self.etag = kwargs['etag_func'](request, *args, **kwargs)
        if 'last_modified_func' in kwargs:
            self.last_modified = kwargs['last_modified_func'](request, *args,
                    **kwargs)
        response = None
        response = self.test_conditions()
        if response is None:
            response = view(request, *args, **kwargs)
        self.set_headers(response)
        return response

class EtagMixin(ViewDecoratorMixin):
    """
    tests Etag against request
    """


