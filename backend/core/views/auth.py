from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from dj_rest_auth.registration.views import SocialLoginView


class GoogleLoginView(SocialLoginView):
    """
    Receives Google Access Token from NextAuth client:
    1. Validates token authenticity against Google OAuth provider.
    2. Provisions User and default Organization on initial registration (via signals).
    3. Issues DRF Auth Token / JWT back to the client.
    """
    adapter_class = GoogleOAuth2Adapter