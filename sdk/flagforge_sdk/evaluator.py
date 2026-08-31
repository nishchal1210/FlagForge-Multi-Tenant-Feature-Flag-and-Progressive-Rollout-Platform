import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationDetails:
    value: bool
    reason: str
    matched_rule_priority: int | None = None
    bucket: int | None = None


def condition_matches(
    condition: dict[str, Any],
    user: dict[str, Any],
) -> bool:
    attribute = condition["attribute"]

    if attribute not in user:
        return False

    actual = user[attribute]
    expected = condition["value"]
    operator = condition["operator"]

    if operator == "equals":
        return actual == expected

    if operator == "not_equals":
        return actual != expected

    if operator == "in":
        return actual in expected

    if operator == "not_in":
        return actual not in expected

    return False


def calculate_bucket(
    flag_id: str,
    user_key: str,
) -> int:
    data = f"{flag_id}:{user_key}".encode("utf-8")
    digest = hashlib.sha256(data).digest()

    number = int.from_bytes(
        digest[:8],
        byteorder="big",
    )

    return number % 10000


def evaluate_boolean_flag(
    configuration: dict[str, Any],
    flag_key: str,
    user: dict[str, Any],
    fallback: bool,
) -> EvaluationDetails:
    flag = configuration.get(
        "flags",
        {},
    ).get(flag_key)

    if flag is None:
        return EvaluationDetails(
            value=fallback,
            reason="FLAG_NOT_FOUND",
        )

    if not flag["enabled"]:
        return EvaluationDetails(
            value=flag["default_value"],
            reason="FLAG_DISABLED",
        )

    for rule in flag["rules"]:
        matches = all(
            condition_matches(condition, user)
            for condition in rule["conditions"]
        )

        if not matches:
            continue

        serve = rule["serve"]

        if serve["type"] == "fixed":
            return EvaluationDetails(
                value=serve["value"],
                reason="RULE_MATCH",
                matched_rule_priority=rule["priority"],
            )

        user_key = user.get("key")

        if not isinstance(user_key, str) or not user_key:
            return EvaluationDetails(
                value=flag["default_value"],
                reason="MISSING_USER_KEY",
                matched_rule_priority=rule["priority"],
            )

        bucket = calculate_bucket(
            flag_id=flag["id"],
            user_key=user_key,
        )

        return EvaluationDetails(
            value=(
                bucket
                < serve["true_basis_points"]
            ),
            reason="PERCENTAGE_ROLLOUT",
            matched_rule_priority=rule["priority"],
            bucket=bucket,
        )

    return EvaluationDetails(
        value=flag["default_value"],
        reason="DEFAULT_VALUE",
    )