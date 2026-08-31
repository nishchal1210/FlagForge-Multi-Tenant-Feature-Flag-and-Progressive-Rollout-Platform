import hashlib
import json
from typing import Any

from app.models.environment import Environment


def build_configuration(
    environment: Environment,
) -> dict[str, Any]:
    flags: dict[str, Any] = {}

    for flag in sorted(
        environment.flags,
        key=lambda item: item.key,
    ):
        rules: list[dict[str, Any]] = []

        for rule in sorted(
            flag.rules,
            key=lambda item: item.priority,
        ):
            conditions = [
                {
                    "attribute": condition.attribute,
                    "operator": condition.operator,
                    "value": condition.value,
                }
                for condition in sorted(
                    rule.conditions,
                    key=lambda item: (
                        item.attribute,
                        item.operator,
                        json.dumps(
                            item.value,
                            sort_keys=True,
                        ),
                    ),
                )
            ]

            if rule.serve_type == "fixed":
                serve = {
                    "type": "fixed",
                    "value": bool(rule.serve_value),
                }
            else:
                serve = {
                    "type": "percentage",
                    "true_basis_points": (
                        rule.true_basis_points
                    ),
                }

            rules.append(
                {
                    "priority": rule.priority,
                    "conditions": conditions,
                    "serve": serve,
                }
            )

        flags[flag.key] = {
            "id": str(flag.id),
            "enabled": flag.enabled,
            "default_value": flag.default_value,
            "rules": rules,
        }

    return {
        "schema_version": 1,
        "environment": {
            "id": str(environment.id),
            "key": environment.key,
        },
        "flags": flags,
    }


def calculate_checksum(
    configuration: dict[str, Any],
) -> str:
    canonical_json = json.dumps(
        configuration,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()