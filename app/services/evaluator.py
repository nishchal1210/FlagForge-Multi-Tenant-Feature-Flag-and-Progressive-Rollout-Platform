import hashlib
from dataclasses import dataclass
from typing import Any

from app.models.feature_flag import FeatureFlag
from app.models.rule_condition import RuleCondition
from app.models.targeting_rule import TargetingRule


@dataclass(frozen=True)
class EvaluationResult:
    value: bool
    reason: str
    matched_rule_priority: int | None = None
    bucket: int | None = None

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

def condition_matches(
    condition: RuleCondition,
    user: dict[str, Any],
) -> bool:
    if condition.attribute not in user:
        return False

    actual = user[condition.attribute]
    expected = condition.value

    if condition.operator == "equals":
        return actual == expected

    if condition.operator == "not_equals":
        return actual != expected

    if condition.operator == "in":
        return actual in expected

    if condition.operator == "not_in":
        return actual not in expected

    return False

def evaluate_rule(
    flag: FeatureFlag,
    rule: TargetingRule,
    user: dict[str, Any],
) -> EvaluationResult:
    if rule.serve_type == "fixed":
        return EvaluationResult(
            value=bool(rule.serve_value),
            reason="RULE_MATCH",
            matched_rule_priority=rule.priority,
        )

    user_key = user.get("key")

    if not isinstance(user_key, str) or not user_key:
        return EvaluationResult(
            value=flag.default_value,
            reason="MISSING_USER_KEY",
            matched_rule_priority=rule.priority,
        )

    bucket = calculate_bucket(
        flag_id=str(flag.id),
        user_key=user_key,
    )

    return EvaluationResult(
        value=bucket < rule.true_basis_points,
        reason="PERCENTAGE_ROLLOUT",
        matched_rule_priority=rule.priority,
        bucket=bucket,
    )


def evaluate_flag(
    flag: FeatureFlag,
    user: dict[str, Any],
) -> EvaluationResult:
    if not flag.enabled:
        return EvaluationResult(
            value=flag.default_value,
            reason="FLAG_DISABLED",
        )

    ordered_rules = sorted(
        flag.rules,
        key=lambda rule: rule.priority,
    )

    for rule in ordered_rules:
        matches = all(
            condition_matches(condition, user)
            for condition in rule.conditions
        )

        if matches:
            return evaluate_rule(
                flag=flag,
                rule=rule,
                user=user,
            )

    return EvaluationResult(
        value=flag.default_value,
        reason="DEFAULT_VALUE",
    )


def evaluate_rule(
    flag: FeatureFlag,
    rule: TargetingRule,
    user: dict[str, Any],
) -> EvaluationResult:
    if rule.serve_type == "fixed":
        return EvaluationResult(
            value=bool(rule.serve_value),
            reason="RULE_MATCH",
            matched_rule_priority=rule.priority,
        )

    user_key = user.get("key")

    if not isinstance(user_key, str) or not user_key:
        return EvaluationResult(
            value=flag.default_value,
            reason="MISSING_USER_KEY",
            matched_rule_priority=rule.priority,
        )

    bucket = calculate_bucket(
        flag_id=str(flag.id),
        user_key=user_key,
    )

    return EvaluationResult(
        value=bucket < rule.true_basis_points,
        reason="PERCENTAGE_ROLLOUT",
        matched_rule_priority=rule.priority,
        bucket=bucket,
    )


def evaluate_flag(
    flag: FeatureFlag,
    user: dict[str, Any],
) -> EvaluationResult:
    if not flag.enabled:
        return EvaluationResult(
            value=flag.default_value,
            reason="FLAG_DISABLED",
        )

    ordered_rules = sorted(
        flag.rules,
        key=lambda rule: rule.priority,
    )

    for rule in ordered_rules:
        matches = all(
            condition_matches(condition, user)
            for condition in rule.conditions
        )

        if matches:
            return evaluate_rule(
                flag=flag,
                rule=rule,
                user=user,
            )

    return EvaluationResult(
        value=flag.default_value,
        reason="DEFAULT_VALUE",
    )