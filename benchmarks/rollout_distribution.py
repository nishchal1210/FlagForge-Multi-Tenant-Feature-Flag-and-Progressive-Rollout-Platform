import csv
from pathlib import Path

from flagforge_sdk.evaluator import evaluate_boolean_flag


USER_COUNT = 100_000
ROLLOUTS = (0, 1500, 3000, 5000, 10000)

FLAG_KEY = "new_checkout"
FLAG_ID = "11111111-1111-4111-8111-111111111111"

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def make_configuration(basis_points):
    return {
        "schema_version": 1,
        "environment": {
            "id": "22222222-2222-4222-8222-222222222222",
            "key": "benchmark",
        },
        "flags": {
            FLAG_KEY: {
                "id": FLAG_ID,
                "enabled": True,
                "default_value": False,
                "rules": [
                    {
                        "priority": 1,
                        "conditions": [
                            {
                                "attribute": "country",
                                "operator": "equals",
                                "value": "IN",
                            }
                        ],
                        "serve": {
                            "type": "percentage",
                            "true_basis_points": basis_points,
                        },
                    }
                ],
            }
        },
    }


def evaluate(configuration, user_key, country="IN"):
    return evaluate_boolean_flag(
        configuration=configuration,
        flag_key=FLAG_KEY,
        user={
            "key": user_key,
            "country": country,
        },
        fallback=False,
    )


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    selected_users = {}
    rows = []

    for basis_points in ROLLOUTS:
        configuration = make_configuration(basis_points)

        enabled = {
            i
            for i in range(USER_COUNT)
            if evaluate(
                configuration,
                f"user-{i}",
            ).value
        }

        selected_users[basis_points] = enabled

        configured_percent = basis_points / 100
        observed_percent = len(enabled) / USER_COUNT * 100

        row = {
            "basis_points": basis_points,
            "configured_percent": configured_percent,
            "users": USER_COUNT,
            "enabled_users": len(enabled),
            "observed_percent": round(observed_percent, 4),
        }

        rows.append(row)

        print(
            f"Configured={configured_percent:6.2f}% "
            f"Observed={observed_percent:8.4f}% "
            f"Enabled={len(enabled)}"
        )

    # Boundary behavior.
    assert len(selected_users[0]) == 0
    assert len(selected_users[10000]) == USER_COUNT

    # Increasing the threshold must preserve enabled users.
    for lower, higher in zip(ROLLOUTS, ROLLOUTS[1:]):
        assert selected_users[lower] <= selected_users[higher], (
            f"Users were lost between {lower} and {higher}"
        )

    configuration = make_configuration(1500)

    # Repeated evaluations must remain stable.
    for i in range(1000):
        user_key = f"user-{i}"

        first = evaluate(configuration, user_key)
        second = evaluate(configuration, user_key)

        assert first == second

    # Users outside the targeted country remain disabled.
    for i in range(1000):
        result = evaluate(
            configuration,
            f"user-{i}",
            country="US",
        )

        assert result.value is False
        assert result.reason == "DEFAULT_VALUE"

    output = RESULTS_DIR / "rollout_distribution.csv"

    with output.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0]),
        )

        writer.writeheader()
        writer.writerows(rows)

    print("\nPASS: 0% and 100% boundaries")
    print("PASS: increasing rollouts preserve enabled users")
    print("PASS: repeated evaluations remain stable")
    print("PASS: country targeting excludes US users")
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()