from django.test import TestCase
from .models import PyouPyouUser


class PyouPyouUserTestCase(TestCase):
    def test_longer_username_allowed(self):
        """Simple test to assert the migration aimed at increasing the maximum length of usernames works."""
        user_extended = PyouPyouUser.objects.create(
            trigramme="abcdefg", full_name="ab cdefg", email="abcdefg@mail.com", password="abK!àapec"
        )
        user_extended.full_clean()
