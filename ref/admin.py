from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from ref.models import Subsidiary, Consultant, PyouPyouUser


class PyouPyouUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("trigramme", "password")}),
        (_("Personal info"), {"fields": ("full_name", "email")}),
        (
            _("Permissions"),
            {"fields": ("is_active", "token", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("trigramme", "password1", "password2")}),)

    list_display = ("trigramme", "email", "full_name", "is_staff")
    search_fields = ("trigramme", "full_name", "email")
    ordering = ("trigramme",)


class SubsidiaryAdmin(admin.ModelAdmin):
    filter_horizontal = ("informed",)


class InformedInline(admin.TabularInline):
    model = Subsidiary.informed.through


class ConsultantAdmin(admin.ModelAdmin):
    inlines = [
        InformedInline,
    ]


admin.site.register(Subsidiary, SubsidiaryAdmin)
admin.site.register(Consultant, ConsultantAdmin)
admin.site.register(PyouPyouUser, PyouPyouUserAdmin)
