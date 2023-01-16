from functools import wraps

from django.contrib.auth.views import redirect_to_login

from ref.models import PyouPyouUser


# Strongly inspired by django's user_passes_test decorator


def privilege_level_check(authorised_level=None):
    """
    decorator that checks:
        - if user is connected
        - if user has correct privileges to access view
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            authorised = authorised_level
            if authorised is None:
                authorised = [PyouPyouUser.PrivilegeLevel.ALL]
            if request.user.is_authenticated and request.user.privilege in authorised:
                return view_func(request, *args, **kwargs)
            return redirect_to_login(next=request.path)

        return wrapper

    return decorator
