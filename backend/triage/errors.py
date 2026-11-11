"""Map DRF/Django errors to the contract Error shape {code, message, details?}.

Pattern: DRF api-guide/exceptions.md "Custom exception handling".
"""

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler


class ApiError(exceptions.APIException):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        super().__init__(detail=message)


def _details(detail, prefix: str = "") -> list[dict]:
    if isinstance(detail, dict):
        return [d for k, v in detail.items() for d in _details(v, f"{prefix}{k}")]
    if isinstance(detail, list):
        return [{"field": prefix or "body", "message": str(m)} for m in detail]
    return [{"field": prefix or "body", "message": str(detail)}]


def exception_handler(exc, context):
    if isinstance(exc, ApiError):
        return Response({"code": exc.code, "message": str(exc.detail)}, status=exc.status_code)
    if isinstance(exc, (exceptions.ValidationError, exceptions.ParseError)):
        body = {
            "code": "validation_error",
            "message": "요청 값이 올바르지 않습니다.",
            "details": _details(exc.detail),
        }
        return Response(body, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    response = drf_handler(exc, context)
    if response is not None:
        response.data = {
            "code": getattr(exc, "default_code", "error"),
            "message": str(getattr(exc, "detail", exc)),
        }
    return response
