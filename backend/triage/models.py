import uuid

from django.db import models


class TriageSession(models.Model):
    """One anonymous triage conversation.

    Storage policy (SPEC section 6): the user's raw text is never stored. Only
    structured symptoms (standard ids), a district code and the computed result.
    """

    class Status(models.TextChoices):
        COLLECTING = "collecting"
        RESULT_READY = "result_ready"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.COLLECTING)
    region_code = models.CharField(max_length=5, blank=True, default="")
    symptoms = models.JSONField(default=list)  # [{"symptom_id", "severity"?, "duration_days"?}]
    turns = models.PositiveSmallIntegerField(default=0)
    emergency = models.BooleanField(default=False)
    emergency_reasons = models.JSONField(default=list)
    result = models.JSONField(null=True, blank=True)  # TriageResult payload once ready
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
