from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import (Group, User, SiteProfileNotAvailable,
    UserManager)
from django.contrib.auth.tests.utils import skipIfCustomUser
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import six


@skipIfCustomUser
@override_settings(USE_TZ=False, AUTH_PROFILE_MODULE='')
class ProfileTestCase(TestCase):

    def test_site_profile_not_available(self):
        user = User.objects.create(username='testclient')

        # calling get_profile without AUTH_PROFILE_MODULE set
        del settings.AUTH_PROFILE_MODULE
        with six.assertRaisesRegex(self, SiteProfileNotAvailable,
                "You need to set AUTH_PROFILE_MODULE in your project"):
            user.get_profile()

        # Bad syntax in AUTH_PROFILE_MODULE:
        settings.AUTH_PROFILE_MODULE = 'foobar'
        with six.assertRaisesRegex(self, SiteProfileNotAvailable,
                "app_label and model_name should be separated by a dot"):
            user.get_profile()

        # module that doesn't exist
        settings.AUTH_PROFILE_MODULE = 'foo.bar'
        with six.assertRaisesRegex(self, SiteProfileNotAvailable,
                "Unable to load the profile model"):
            user.get_profile()


@skipIfCustomUser
@override_settings(USE_TZ=False)
class NaturalKeysTestCase(TestCase):
    fixtures = ['authtestdata.json']

    def test_user_natural_key(self):
        staff_user = User.objects.get(username='staff')
        self.assertEqual(User.objects.get_by_natural_key('staff'), staff_user)
        self.assertEqual(staff_user.natural_key(), ('staff',))

    def test_group_natural_key(self):
        users_group = Group.objects.create(name='users')
        self.assertEqual(Group.objects.get_by_natural_key('users'), users_group)


@skipIfCustomUser
@override_settings(USE_TZ=False)
class LoadDataWithoutNaturalKeysTestCase(TestCase):
    fixtures = ['regular.json']

    def test_user_is_created_and_added_to_group(self):
        user = User.objects.get(username='my_username')
        group = Group.objects.get(name='my_group')
        self.assertEqual(group, user.groups.get())


@skipIfCustomUser
@override_settings(USE_TZ=False)
class LoadDataWithNaturalKeysTestCase(TestCase):
    fixtures = ['natural.json']

    def test_user_is_created_and_added_to_group(self):
        user = User.objects.get(username='my_username')
        group = Group.objects.get(name='my_group')
        self.assertEqual(group, user.groups.get())


@skipIfCustomUser
class UserManagerTestCase(TestCase):

    def test_create_user(self):
        email_lowercase = 'normal@normal.com'
        user = User.objects.create_user('user', email_lowercase)
        self.assertEqual(user.email, email_lowercase)
        self.assertEqual(user.username, 'user')
        self.assertEqual(user.password, '!')

    def test_create_user_email_domain_normalize_rfc3696(self):
        # According to  http://tools.ietf.org/html/rfc3696#section-3
        # the "@" symbol can be part of the local part of an email address
        returned = UserManager.normalize_email(r'Abc\@DEF@EXAMPLE.com')
        self.assertEqual(returned, r'Abc\@DEF@example.com')

    def test_create_user_email_domain_normalize(self):
        returned = UserManager.normalize_email('normal@DOMAIN.COM')
        self.assertEqual(returned, 'normal@domain.com')

    def test_create_user_email_domain_normalize_with_whitespace(self):
        returned = UserManager.normalize_email('email\ with_whitespace@D.COM')
        self.assertEqual(returned, 'email\ with_whitespace@d.com')

    def test_empty_username(self):
        self.assertRaisesMessage(ValueError,
                                 'The given username must be set',
                                  User.objects.create_user, username='')

class IsActiveTestCase(TestCase):
    """
    Tests the behavior of the guaranteed is_active attribute
    """

    def test_builtin_user_isactive(self):
        user = User.objects.create(username='foo', email='foo@bar.com')
        # is_active is true by default
        self.assertTrue(user.is_active)
        user.is_active = False
        user.save()
        user_fetched = User.objects.get(pk=user.pk)
        # the is_active flag is saved
        self.assertFalse(user_fetched.is_active)

    @override_settings(AUTH_USER_MODEL='auth.IsActiveTestUser1')
    def test_is_active_field_default(self):
        """
        tests that the default value for is_active is provided
        """
        UserModel = get_user_model()
        user = UserModel(username='foo')
        self.assertTrue(user.is_active)
        with self.assertRaises(AttributeError):
            # the default attribute is not settable
            user.is_active = False
        # there should be no problem saving
        user.save()

    @override_settings(AUTH_USER_MODEL='auth.IsActiveTestUser3')
    def test_is_active_class_attr(self):
        """
        test whether class attribute for is_active is valid
        """
        UserModel = get_user_model()
        user = UserModel(username='foo')
        # this test class defines a class attribute of False
        self.assertFalse(user.is_active)
        # it is valid to set this attribute on the instance
        user.is_active = True
        user.save()
        # it is not saved
        user_fetched = UserModel.objects.get(pk=user.pk)
        self.assertFalse(user_fetched.is_active)

    @override_settings(AUTH_USER_MODEL='auth.IsActiveTestUser4')
    def test_is_active_instance_attr(self):
        """
        test whether non-field instance attribute for is_active is valid
        """
        UserModel = get_user_model()
        user = UserModel(username='foo')
        # this test class specifies instance attribute of False
        self.assertFalse(user.is_active)
        # it is valid to set this attribute
        user.is_active = True
        user.save()
        # it is not saved
        user_fetched = UserModel.objects.get(pk=user.pk)
        self.assertFalse(user_fetched.is_active)
