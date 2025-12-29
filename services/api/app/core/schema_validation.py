from typing import Any, Dict, List

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


class SchemaValidationException(Exception):
    def __init__(self, errors: List[str]):
        super().__init__("Schema validation failed")
        self.errors = errors


def validate_json(instance: Any, schema: Dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)
    if not errors:
        return

    messages: List[str] = []
    for e in errors[:30]:
        path = "/".join([str(p) for p in e.path])
        messages.append(f"{path}: {e.message}" if path else e.message)

    raise SchemaValidationException(messages)
