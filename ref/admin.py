from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from ref.models import Subsidiary, PyouPyouUser


class PyouPyouUserAdmin(UserAdmin):
    fieldsets = (
        (_("Personal info"), {"fields": ("full_name", "trigramme", "password", "email", "company")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "privilege",
                    "limited_to_source",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("trigramme", "password1", "password2")}),)

    list_display = ("trigramme", "email", "full_name", "is_staff")
    search_fields = ("trigramme", "full_name", "email")
    ordering = ("trigramme",)


admin.site.register(Subsidiary)
admin.site.register(PyouPyouUser, PyouPyouUserAdmin)
