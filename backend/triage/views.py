"""Contract: contracts/openapi.yaml (/api/triage/...)."""

import uuid

from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from triage import service
from triage.errors import ApiError
from triage.models import TriageSession


class CreateSessionSerializer(serializers.Serializer):
    region_code = serializers.RegexField(r"^[0-9]{5}$", required=False)


class MessageSerializer(serializers.Serializer):
    text = serializers.CharField(min_length=1, max_length=500, trim_whitespace=True)


def _reject_unknown_fields(data, serializer_cls):
    extra = set(data) - set(serializer_cls().fields) if isinstance(data, dict) else set()
    if extra:
        raise serializers.ValidationError({k: ["허용되지 않는 필드입니다."] for k in sorted(extra)})


def _get_session(session_id: str) -> TriageSession:
    try:
        return TriageSession.objects.get(pk=uuid.UUID(str(session_id)))
    except (ValueError, TriageSession.DoesNotExist):
        raise ApiError(
            404, "session_not_found", "세션을 찾을 수 없습니다. 새 세션을 시작하세요."
        ) from None


@api_view(["POST"])
def create_session(request):
    data = request.data or {}
    _reject_unknown_fields(data, CreateSessionSerializer)
    s = CreateSessionSerializer(data=data)
    s.is_valid(raise_exception=True)
    session = TriageSession.objects.create(region_code=s.validated_data.get("region_code", ""))
    body = {
        "session_id": str(session.id),
        "status": session.status,
        "created_at": session.created_at.isoformat(),
    }
    return Response(body, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def post_message(request, session_id):
    session = _get_session(session_id)
    _reject_unknown_fields(request.data, MessageSerializer)
    s = MessageSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    if session.status == TriageSession.Status.RESULT_READY:
        raise ApiError(
            409, "session_completed", "이 세션은 이미 결과가 확정됐습니다. 새 세션을 시작하세요."
        )
    return Response(service.handle_message(session, s.validated_data["text"]))


@api_view(["GET"])
def get_result(request, session_id):
    session = _get_session(session_id)
    if session.result is None:
        raise ApiError(409, "result_not_ready", "추가 질문에 먼저 답해 주세요.")
    return Response(session.result)
