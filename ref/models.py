from django.db import models
from django.utils.translation import ugettext_lazy as _


class Subsidiary(models.Model):
    """Internal company / organisation unit"""
    name = models.CharField(_("Name"), max_length=200, unique=True)
    code = models.CharField(_("Code"), max_length=3, unique=True)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _("Subsidiary")
        verbose_name_plural = _("Subsidiaries")
        ordering = ["name", ]


class Consultant(models.Model):
    """A consultant that can do recruitment meeting"""
    name = models.CharField(max_length=50)
    trigramme = models.CharField(max_length=4, unique=True)
    company = models.ForeignKey(Subsidiary, verbose_name=_("Subsidiary"))
    productive = models.BooleanField(_("Productive"), default=True)
    active = models.BooleanField(_("Active"), default=True)

    def __unicode__(self):
        return self.name

    def full_name(self):
        return u"%s (%s)" % (self.name, self.trigramme)
