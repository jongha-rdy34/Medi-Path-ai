from django.test import override_settings

from triage import clients
from triage.http_clients import HttpLLMClient, HttpMLClient, HttpSafetyClient


@override_settings(TRIAGE_CLIENTS="http", ML_SERVICE_URL="http://ml-service:8001")
def test_http_clients_are_used_in_the_running_service():
    llm, ml, safety = clients.build()

    assert isinstance(llm, HttpLLMClient) and isinstance(ml, HttpMLClient)
    assert isinstance(safety, HttpSafetyClient) and ml.base_url == "http://ml-service:8001"


@override_settings(TRIAGE_CLIENTS="stub")
def test_stubs_are_used_in_tests():
    llm, ml, safety = clients.build()

    assert isinstance(llm, clients.StubLLMClient) and isinstance(ml, clients.StubMLClient)
    assert isinstance(safety, clients.StubSafetyClient)
