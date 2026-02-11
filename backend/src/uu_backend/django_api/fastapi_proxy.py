"""Helpers for proxying Django-routed requests to the legacy FastAPI app."""

from asgiref.sync import async_to_sync
from django.http import HttpResponse
from rest_framework.views import APIView

from uu_backend.api.main import app as fastapi_app

try:
    import httpx
except Exception:  # pragma: no cover - surfaced at runtime if unavailable
    httpx = None


async def _proxy_to_fastapi(method: str, path: str, request) -> HttpResponse:
    if httpx is None:
        return HttpResponse("httpx is required for proxy routing", status=500)

    query_string = request.META.get("QUERY_STRING") or ""
    url = f"http://fastapi.local{path}"
    if query_string:
        url = f"{url}?{query_string}"

    headers = {}
    for key, value in request.headers.items():
        lowered = key.lower()
        if lowered in {"host", "content-length"}:
            continue
        headers[key] = value

    body = request.body if method in {"POST", "PUT", "PATCH", "DELETE"} else None

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://fastapi.local") as client:
        response = await client.request(method=method, url=url, headers=headers, content=body)

    django_response = HttpResponse(
        content=response.content,
        status=response.status_code,
        content_type=response.headers.get("content-type"),
    )
    for key, value in response.headers.items():
        lowered = key.lower()
        if lowered in {"content-length", "transfer-encoding", "connection", "content-type"}:
            continue
        django_response[key] = value
    return django_response


class FastAPIProxyView(APIView):
    """Base APIView that proxies methods to a FastAPI path template."""

    authentication_classes: list = []
    permission_classes: list = []
    target_path_template: str = "/"

    def _path(self, **kwargs) -> str:
        return self.target_path_template.format(**kwargs)

    def _proxy(self, request, method: str, **kwargs):
        return async_to_sync(_proxy_to_fastapi)(method, self._path(**kwargs), request)

    def get(self, request, **kwargs):
        return self._proxy(request, "GET", **kwargs)

    def post(self, request, **kwargs):
        return self._proxy(request, "POST", **kwargs)

    def put(self, request, **kwargs):
        return self._proxy(request, "PUT", **kwargs)

    def patch(self, request, **kwargs):
        return self._proxy(request, "PATCH", **kwargs)

    def delete(self, request, **kwargs):
        return self._proxy(request, "DELETE", **kwargs)

