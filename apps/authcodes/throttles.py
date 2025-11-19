# ==========================================
# apps/authcodes/throttles.py
# ==========================================
from rest_framework.throttling import SimpleRateThrottle


class RequestCodeThrottle(SimpleRateThrottle):
    scope = "request_code"

    def get_cache_key(self, request, view):
        # Por qué: limita por IP para evitar abuso del endpoint de envío de códigos
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
