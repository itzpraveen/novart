from django.http import HttpResponseNotFound, HttpResponseRedirect

from .public_site import erp_redirect_url, is_public_host, is_public_path


class PublicSiteHostMiddleware:
    """Keep the marketing site on the public host and ERP routes on the ERP host."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_public_host(request) and not is_public_path(request.path):
            redirect_to = erp_redirect_url(request)
            if redirect_to:
                return HttpResponseRedirect(redirect_to)
            return HttpResponseNotFound()
        return self.get_response(request)
