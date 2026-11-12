"""GET /api/hospitals. Contract: contracts/openapi.yaml (searchHospitals, T21 PR 2)."""

import logging

from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from hospitals import departments, service
from hospitals.http import SourceUnavailable

log = logging.getLogger(__name__)


class SearchParams(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)
    department = serializers.RegexField(r"^[0-9A-Z]{2}$")
    radius = serializers.IntegerField(min_value=100, max_value=10000, default=3000)
    open_now = serializers.BooleanField(default=False)
    night = serializers.BooleanField(default=False)
    weekend = serializers.BooleanField(default=False)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=30)

    def validate_department(self, code):
        dept = departments.lookup(code)
        if dept is None:
            raise serializers.ValidationError("지원하지 않는 진료과 코드입니다.")
        return dept


def _error(status: int, code: str, message: str) -> Response:
    return Response({"code": code, "message": message}, status=status)


@api_view(["GET"])
def search(request):
    params = SearchParams(data=request.query_params)
    params.is_valid(raise_exception=True)  # 422 validation_error via REST_FRAMEWORK handler
    try:
        body = service.search(service.Query(**params.validated_data))
    except service.OutOfServiceArea:
        return _error(
            422,
            "out_of_service_area",
            "이 위치에서는 병원을 찾을 수 없습니다. 지도를 눌러 국내 위치를 지정하세요.",
        )
    except SourceUnavailable as e:
        log.warning(
            "hospital source unavailable: %s %s", e.source, e.reason
        )  # no URL, key or coords
        return _error(
            503,
            "hospital_source_unavailable",
            "병원 정보를 잠시 불러올 수 없습니다. 잠시 후 다시 시도하세요.",
        )
    return Response(body)
