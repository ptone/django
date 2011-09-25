from functools import partial, wraps
import urlparse

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.utils.decorators import ViewDecoratorMixin


class BaseUserPassesTest(ViewDecoratorMixin):

    redirect_field_name = REDIRECT_FIELD_NAME
    login_url = None

    def get_login_url(self):
        return self.login_url

    def get_redirect_field_name(self):
        return self.redirect_field_name

    def check_user_passes_test(self, user):
        raise NotImplementedError

    def user_failed_test(self, request):
        from django.contrib.auth.views import redirect_to_login

        path = request.build_absolute_uri()
        # If the login url is the same scheme and net location then just
        # use the path as the "next" url.
        login_scheme, login_netloc = urlparse.urlparse(self.get_login_url() or
                                                    settings.LOGIN_URL)[:2]
        current_scheme, current_netloc = urlparse.urlparse(path)[:2]
        if ((not login_scheme or login_scheme == current_scheme) and
            (not login_netloc or login_netloc == current_netloc)):
            path = request.get_full_path()
        return redirect_to_login(path, self.get_login_url(), self.get_redirect_field_name())

    def decorate_wrapped(self, view, request, *args, **kwargs):
        if self.check_user_passes_test(request.user):
            return view(request, *args, **kwargs)
        return self.user_failed_test(request)


class UserPassesTest(BaseUserPassesTest):

    def check_user_passes_test(self, user):
        return self.args[0](user)

    @classmethod
    def as_decorator(cls, *args, **kwargs):
        # This method is required for Backwards Compatibility. user_passes_test
        # decorator requires a callable to be it's first argument (instead of a
        # kwarg). This means that the normal test if an arg is callable to determine
        # if we are be called like @UserPassesTest.as_decorator or
        # @UserPassesTest.as_decorator() harder. Luckily user_passes_test requires
        # the second so we don't have to.

        if not args:
            raise TypeError("%r has a required argument." % cls.__name__)
        return wraps(cls.decorate)(partial(cls.decorate, args=args, kwargs=kwargs))


class LoginRequired(BaseUserPassesTest):

    def check_user_passes_test(self, user):
        return user.is_authenticated()


class PermissionRequired(BaseUserPassesTest):

    raise_exception = False

    def check_user_passes_test(self, user):
        return user.has_perm(self.args[0])

    def user_failed_test(self, request):
        if self.raise_exception:
            raise PermissionDenied
        return super(PermissionRequired, self).user_failed_test(request)
