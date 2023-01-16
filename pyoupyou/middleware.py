from django.contrib.auth.middleware import RemoteUserMiddleware
from django.http import HttpResponseForbidden
from django.urls import resolve

from interview.views import get_global_filter
from ref.models import PyouPyouUser


class ProxyRemoteUserMiddleware(RemoteUserMiddleware):
    header = "HTTP_REMOTE_USER"


class ExternalCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.forbidden_content = b'<div style="display: flex; width: 100%; height: 100%; justify-content: center; align-items: center;">Please contact your system administrator</div>'

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.user.privilege != PyouPyouUser.PrivilegeLevel.ALL
            and request.user.limited_to_source is None
        ):
            return HttpResponseForbidden(content=self.forbidden_content)

        response = self.get_response(request)

        return response


class GlobalSubsidiaryFilterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        request.session.setdefault("subsidiary", "")

        # set current filter (if there is one) in session infos
        if "subsidiary" in request.GET:
            try:
                subsidiary_id = int(request.GET["subsidiary"])
            except ValueError:
                subsidiary_id = ""
            request.session["subsidiary"] = subsidiary_id

        # altering request.GET makes django-admin inaccessible
        if resolve(request.path_info).namespace not in ("admin",):
            # update current request.GET to match global filter
            # this is useful to automatically apply the filter on views that previously had a filter
            get_req = request.GET.copy()
            get_req.setdefault("subsidiary", request.session["subsidiary"])
            request.GET = get_req

        request.subsidiaries_filter = get_global_filter(request)
        return self.get_response(request)
