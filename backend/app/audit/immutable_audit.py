
import hashlib

class ImmutableAudit:

    def register(self, content):

        return hashlib.sha256(
            content.encode()
        ).hexdigest()
