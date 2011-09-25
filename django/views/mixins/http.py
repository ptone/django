"""
Mixin classes for modifying HTTP headers
"""

from django.http import HttpResponseNotAllowed, HttpResponseNotModified, HttpResponse
from django.utils.decorators import ViewDecoratorMixin
from django.utils.http import http_date, parse_http_date_safe, parse_etags, quote_etag
from django.utils.log import getLogger

logger = getLogger('django.request')

class HTTPConditionMixin(ViewDecoratorMixin):

    self.etag = None
    self.last_modified = None

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
        return self.etag

    def get_last_modified(self):
        return self.last_modified

    def check_etags(self):
        if (self.if_none_match and (self.get_etag() in self.etags)):
            return False
        if (self.if_match and not (self.get_etag() in self.etags)):
            return False
        return True

    def check_last_modified(self):
        if self.get_last_modified() is None:
            return True
        if ((self.get_last_modified() and self.if_modified_since) and
                (self.get_last_modified() <= self.if_modified_since)):
            return True
        return False

    def precondition_failed(self):
        logger.warning('Precondition Failed: %s' % request.path,
            extra={
                'status_code': 412,
                'request': request
            }
        )
        return HttpResponse(status=412)

    def test_conditions(self):
        pass
        # if conditions pass, return  HttpResponseNotModified
        # otherwise return return precondition_failed()
        #

    def dispatch(self):
        response = None
        response = self.test_conditions()
        if response is None:
            pass
            # want to return dispatch of Super of View subclass - not mixin
            # note that this does not effect use of mixin as decorator as much
            # as it effects mixin as mixn ;-)

        # Set relevant headers on the response if they don't already exist.
        if res_last_modified and not response.has_header('Last-Modified'):
            response['Last-Modified'] = http_date(res_last_modified)
        if res_etag and not response.has_header('ETag'):
            response['ETag'] = quote_etag(res_etag)

        return response

class EtagMixin(ViewDecoratorMixin):
    """
    tests Etag against request
    """


