import secrets

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import User, PermissionsMixin
from django.core.mail import send_mail
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Subsidiary(models.Model):
    """Internal company / organisation unit"""

    name = models.CharField(_("Name"), max_length=200, unique=True)
    code = models.CharField(_("Code"), max_length=3, unique=True)
    responsible = models.ForeignKey("Consultant", null=True, on_delete=models.SET_NULL)
    informed = models.ManyToManyField(
        "Consultant", blank=True, related_name="subsidiary_notifications", verbose_name=_("Informed consultants")
    )
    show_in_report_by_default = models.BooleanField(
        default=True, verbose_name=_("Show the subsidiary in the report analysis by default")
    )

    @property
    def notification_emails(self):
        res = [email for email in self.informed.all().values_list("user__email", flat=True)]
        if self.responsible:
            res.append(self.responsible.user.email)
        return res

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


def generate_token():
    return secrets.token_urlsafe(25)


class PyouPyouUser(AbstractBaseUser, PermissionsMixin):
    trigramme = models.CharField(max_length=40, unique=True)
    full_name = models.CharField(_("full name"), max_length=50, blank=True)
    email = models.EmailField(_("email address"), blank=True)
    token = models.CharField(max_length=50, blank=True, default=generate_token)  # urlsafe is number of bytes not char
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

    objects = PyouPyouUserManager()

    USERNAME_FIELD = "trigramme"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def get_full_name(self):
        return "{} ({})".format(self.full_name, self.trigramme)

    def get_short_name(self):
        return self.full_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email], **kwargs)


class ConsultantManager(models.Manager):
    @transaction.atomic
    def create_consultant(self, trigramme, email, company, full_name, **extra_fields):
        user = PyouPyouUser.objects.create_user(trigramme, email, full_name=full_name, **extra_fields)
        consultant = self.model(user=user, company=company)
        consultant.save()
        return consultant


class Consultant(models.Model):
    """A consultant that can do recruitment meeting"""

    @property
    def is_external(self):
        return self.limited_to_source is not None

    class PrivilegeLevel(models.IntegerChoices):
        ALL = 1, _("User is an insider consultant")
        EXTERNAL_RPO = 2, _("User is an external consultant with additional rights")
        EXTERNAL_FULL = 3, _("User is an external consultant")
        EXTERNAL_READONLY = 4, _("User is external and has only read rights")

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    company = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"), null=True, on_delete=models.SET_NULL)

    # dst class written with string to avoid circular imports issues
    limited_to_source = models.ForeignKey(
        "interview.Sources", null=True, blank=True, default=None, on_delete=models.SET_NULL
    )
    privilege = models.PositiveSmallIntegerField(
        choices=PrivilegeLevel.choices, verbose_name=_("Authority level"), default=PrivilegeLevel.ALL
    )

    objects = ConsultantManager()

    def __str__(self):
        return self.user.get_full_name()

    class Meta:
        ordering = ("user__trigramme",)
