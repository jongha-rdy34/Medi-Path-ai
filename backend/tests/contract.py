"""Validate responses against contracts/openapi.yaml (JSON Schema 2020-12)."""

from functools import cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

OPENAPI = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
URI = "https://contracts.medipath.local/openapi.yaml"


@cache
def _registry() -> Registry:
    doc = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    return Registry().with_resource(
        URI, Resource.from_contents(doc, default_specification=DRAFT202012)
    )


def validate(instance, schema: str) -> None:
    Draft202012Validator(
        {"$ref": f"{URI}#/components/schemas/{schema}"}, registry=_registry()
    ).validate(instance)
