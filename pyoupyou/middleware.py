import datetime

from django.contrib.auth.middleware import RemoteUserMiddleware
from django.http import HttpResponseForbidden

from ref.models import Consultant


class ProxyRemoteUserMiddleware(RemoteUserMiddleware):
    header = "HTTP_REMOTE_USER"


class ExternalCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.forbidden_content = b'<div style="display: flex; width: 100%; height: 100%; justify-content: center; align-items: center;">Please contact your system administrator</div>'

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.user.consultant.privilege != Consultant.PrivilegeLevel.ALL
            and request.user.consultant.limited_to_source is None
        ):
            return HttpResponseForbidden(content=self.forbidden_content)

        response = self.get_response(request)

        return response


class LastVisitedDateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.session.setdefault(request.path, request.user.last_login.timestamp())

        response = self.get_response(request)

        request.session[request.path] = datetime.datetime.now().timestamp()

        return response
