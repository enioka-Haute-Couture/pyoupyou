from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from ref.models import Subsidiary, Consultant, PyouPyouUser


class PyouPyouUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('trigramme', 'password')}),
        (_('Personal info'), {'fields': ('full_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('trigramme', 'password1', 'password2'),
        }),
    )

    list_display = ('trigramme', 'email', 'full_name', 'is_staff')
    search_fields = ('trigramme', 'full_name', 'email')
    ordering = ('trigramme',)


admin.site.register(Subsidiary)
admin.site.register(Consultant)
admin.site.register(PyouPyouUser, PyouPyouUserAdmin)
