from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import User, PermissionsMixin
from django.core.mail import send_mail
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _


class Subsidiary(models.Model):
    """Internal company / organisation unit"""

    name = models.CharField(_("Name"), max_length=200, unique=True)
    code = models.CharField(_("Code"), max_length=3, unique=True)
    responsible = models.ForeignKey("PyouPyouUser", null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Subsidiary")
        verbose_name_plural = _("Subsidiaries")
        ordering = ["name"]


class PyouPyouUserManager(BaseUserManager):
    def _create_user(self, trigramme, email, password, **extra_fields):
        """
        Creates and saves a User with the given username, email and password.
        """
        if not trigramme:
            raise ValueError("The given trigramme must be set")
        email = self.normalize_email(email)
        trigramme = self.model.normalize_username(trigramme)
        user = self.model(trigramme=trigramme, email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_user(self, trigramme, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(trigramme, email, password, **extra_fields)

    def create_superuser(self, trigramme, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(trigramme, email, password, **extra_fields)

    def get_by_natural_key(self, trigramme):
        return self.get(trigramme__iexact=trigramme)


class PyouPyouUser(AbstractBaseUser, PermissionsMixin):
    class PrivilegeLevel(models.IntegerChoices):
        ALL = 1, _("User is an insider consultant")
        EXTERNAL_EXTRA = 2, _("User is an external consultant with additional rights")
        EXTERNAL_FULL = 3, _("User is an external consultant")
        EXTERNAL_READONLY = 4, _("User is external and has only read rights")

    trigramme = models.CharField(max_length=4, unique=True)
    full_name = models.CharField(_("full name"), max_length=50, blank=True)
    email = models.EmailField(_("email address"), blank=True)

    is_staff = models.BooleanField(
        _("staff status"), default=False, help_text=_("Designates whether the user can log into this admin site.")
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. " "Unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    company = models.ForeignKey(
        Subsidiary, verbose_name=_("Subsidiary"), null=True, blank=True, on_delete=models.SET_NULL
    )

    # dst class written with string to avoid circular imports issues
    limited_to_source = models.ForeignKey(
        "interview.Sources",
        null=True,
        blank=True,
        default=None,
        on_delete=models.SET_NULL,
        verbose_name=_("Limit user to a source"),
        help_text=_("This field must be set if user is not an internal consultant"),
    )
    privilege = models.PositiveSmallIntegerField(
        choices=PrivilegeLevel.choices,
        verbose_name=_("Authority level"),
        default=PrivilegeLevel.ALL,
        help_text=_("Designates what a user can or cannot do"),
    )

    objects = PyouPyouUserManager()

    USERNAME_FIELD = "trigramme"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ("trigramme",)

    def __str__(self):
        return self.get_full_name()

    @property
    def is_external(self):
        return self.limited_to_source is not None

    def get_full_name(self):
        return "{} ({})".format(self.full_name, self.trigramme)

    def get_short_name(self):
        return self.full_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email], **kwargs)
