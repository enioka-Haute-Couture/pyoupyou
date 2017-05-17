from django.contrib.auth.middleware import RemoteUserMiddleware

class ProxyRemoteUserMiddleware(RemoteUserMiddleware):
    header = 'HTTP_REMOTE_USER'