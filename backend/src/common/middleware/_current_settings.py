from django.utils.functional import SimpleLazyObject

from common.session import current_settings


class CurrentSettingsMiddleware:
    """Expose the administration's global context on every request.

    The settings are attached to the ``request`` object's ``current_settings``
    property. The property is resolved lazily, preventing database roundtrips
    on subsequent view renderings.

    The middleware must be installed after both ``SessionMiddleware`` and
    ``AuthenticationMiddleware``, which supply the session and the user.

    .. note::
        The memoization of the current user settings by the lazy initialization
        mechanism is essential because multiple inlines on the same page that
        access the ``request`` object will end up performing a single database
        lookup. This has a potential side effect of retrieving stale data.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.current_settings = SimpleLazyObject(lambda: current_settings(request))
        return self.get_response(request)
