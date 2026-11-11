"""Validate payloads against the OpenAPI contracts in contracts/ (JSON Schema 2020-12).

openapi.yaml and ml-service.openapi.yaml are registered together so the
cross-file $refs ('./openapi.yaml#/...') resolve.
"""

from functools import cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
BASE = "https://contracts.medipath.local/"


@cache
def _registry() -> Registry:
    resources = []
    for name in ("openapi.yaml", "ml-service.openapi.yaml"):
        doc = yaml.safe_load((CONTRACTS / name).read_text(encoding="utf-8"))
        resources.append(
            (BASE + name, Resource.from_contents(doc, default_specification=DRAFT202012))
        )
    return Registry().with_resources(resources)


def validate(instance, file: str, schema: str) -> None:
    ref = {"$ref": f"{BASE}{file}#/components/schemas/{schema}"}
    Draft202012Validator(ref, registry=_registry()).validate(instance)
