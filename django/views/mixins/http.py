"""
Mixin classes for modifying HTTP headers
"""

from django.utils.decorators import ViewDecoratorMixin
from django.utils.http import http_date, parse_http_date_safe, parse_etags, quote_etag

class HTTPConditionMixin(ViewDecoratorMixin):

    def __init__(self):
        self.if_modified_since = None
        self.if_match = None
        self.if_none_match = None
        self.required_etag = None
        self.last_modified = None

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

    def get_response_etag(self):
        return None

    def get_last_modified(self):
        return None

    def check_etags(self):

class EtagMixin(ViewDecoratorMixin):
    """
    tests Etag against request
    """


