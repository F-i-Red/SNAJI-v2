
class GovPTAuthentication:

    def authenticate(self, token):

        return {
            "authenticated": True,
            "provider": "gov.pt"
        }
