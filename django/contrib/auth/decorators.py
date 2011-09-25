from django.contrib.auth.mixins import UserPassesTest, LoginRequired, PermissionRequired

# These are here for Backwards Compatibility

user_passes_test = UserPassesTest.as_decorator

login_required = LoginRequired.as_decorator

permission_required = PermissionRequired.as_decorator
