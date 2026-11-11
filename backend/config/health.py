from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health(request):
    """Liveness check. Contract: contracts/openapi.yaml#/paths/~1api~1health"""
    return Response({"status": "ok"})
