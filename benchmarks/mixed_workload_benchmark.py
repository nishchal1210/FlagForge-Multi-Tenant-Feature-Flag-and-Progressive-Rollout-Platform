import csv
import gzip
import random
import statistics
import uuid

from collections import Counter
from time import perf_counter_ns

import httpx

from flagforge_sdk import FlagForgeClient
from flagforge_sdk.client import calculate_checksum

from evaluation_benchmark import (
    create_run_directory,
    percentile,
)


SAMPLES = 20_000
REPEATS = 3
WARMUP = 2_000
USER_COUNT = 1_000
SEED = 42

FLAG_COUNTS = (1, 10, 100, 1000)


def fixed_rule(priority, attribute, value):
    return {
        "priority": priority,
        "conditions": [
            {
                "attribute": attribute,
                "operator": "equals",
                "value": value,
            }
        ],
        "serve": {
            "type": "fixed",
            "value": True,
        },
    }


def make_configuration(flag_count):
    flags = {}

    for i in range(flag_count):
        rules = [
            fixed_rule(1, "internal", True),
            {
                "priority": 2,
                "conditions": [
                    {
                        "attribute": "country",
                        "operator": "equals",
                        "value": "IN",
                    }
                ],
                "serve": {
                    "type": "percentage",
                    "true_basis_points": (
                        1500, 3000, 5000
                    )[i % 3],
                },
            },
            fixed_rule(3, "country", "US"),
        ]

        # Rules that require scanning but never match
        # the synthetic countries used below.
        rules.extend(
            fixed_rule(
                priority,
                "country",
                f"UNUSED-{priority}",
            )
            for priority in range(4, 10)
        )

        rules.append(
            fixed_rule(10, "country", "BR")
        )

        flags[f"flag_{i}"] = {
            "id": str(uuid.UUID(int=i + 1)),
            "enabled": True,
            "default_value": False,
            "rules": rules,
        }

    return {
        "schema_version": 1,
        "environment": {
            "id": "22222222-2222-4222-8222-222222222222",
            "key": "benchmark",
        },
        "flags": flags,
    }


def make_queries(flag_count):
    rng = random.Random(SEED)

    users = [
        {
            "key": f"user-{i}",
            "country": ("IN", "US", "BR", "DE")[i % 4],
            "internal": i % 17 == 0,
        }
        for i in range(USER_COUNT)
    ]

    queries = []

    for _ in range(SAMPLES):
        flag_key = (
            "missing_flag"
            if rng.randrange(10) == 0
            else f"flag_{rng.randrange(flag_count)}"
        )

        queries.append(
            (flag_key, rng.choice(users))
        )

    return queries


def run_case(flag_count, run_dir):
    configuration = make_configuration(flag_count)
    queries = make_queries(flag_count)

    payload = {
        "version": 1,
        "checksum": calculate_checksum(configuration),
        "configuration": configuration,
    }

    request_count = 0

    def handler(request):
        nonlocal request_count
        request_count += 1

        return httpx.Response(200, json=payload)

    client = FlagForgeClient(
        sdk_key="benchmark-only",
        base_url="http://flagforge.test",
        cache_path=None,
        transport=httpx.MockTransport(handler),
    )

    try:
        client.initialize()

        # Record the workload's actual execution paths.
        # This happens outside the timed sections.
        paths = Counter()

        for flag_key, user in queries:
            details = client.boolean_value_details(
                flag_key,
                user=user,
                default=False,
            )

            path = (
                details.reason,
                details.matched_rule_priority,
            )
            paths[path] += 1

        required_paths = {
            ("FLAG_NOT_FOUND", None),
            ("DEFAULT_VALUE", None),
            ("RULE_MATCH", 1),
            ("RULE_MATCH", 3),
            ("RULE_MATCH", 10),
            ("PERCENTAGE_ROLLOUT", 2),
        }

        assert required_paths <= set(paths), paths

        evaluate = client.boolean_value

        for flag_key, user in queries[:WARMUP]:
            evaluate(
                flag_key,
                user=user,
                default=False,
            )

        durations = []
        throughput_runs = []

        for _ in range(REPEATS):
            for flag_key, user in queries:
                started = perf_counter_ns()

                evaluate(
                    flag_key,
                    user=user,
                    default=False,
                )

                durations.append(
                    perf_counter_ns() - started
                )

            # Measure throughput separately from
            # individually timed latency samples.
            started = perf_counter_ns()

            for flag_key, user in queries:
                evaluate(
                    flag_key,
                    user=user,
                    default=False,
                )

            elapsed = perf_counter_ns() - started

            throughput_runs.append(
                len(queries) * 1_000_000_000 / elapsed
            )

        assert request_count == 1, (
            "Evaluation unexpectedly made HTTP requests"
        )

        # Preserve individual timing samples as well
        # as the summarized percentiles.
        with gzip.open(
            run_dir / f"samples_{flag_count}.csv.gz",
            "wt",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.writer(file)
            writer.writerow(["duration_ns"])
            writer.writerows(
                (duration,) for duration in durations
            )

        with (
            run_dir / f"paths_{flag_count}.csv"
        ).open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.writer(file)

            writer.writerow(
                ["reason", "priority", "query_count"]
            )

            for (reason, priority), count in paths.items():
                writer.writerow(
                    [reason, priority, count]
                )

        durations.sort()

        return {
            "flags": flag_count,
            "p50_us": round(
                percentile(durations, 0.50) / 1000,
                3,
            ),
            "p95_us": round(
                percentile(durations, 0.95) / 1000,
                3,
            ),
            "p99_us": round(
                percentile(durations, 0.99) / 1000,
                3,
            ),
            "evaluations_per_second": round(
                statistics.median(throughput_runs)
            ),
        }

    finally:
        client.close()


def main():
    run_dir = create_run_directory(
        "mixed",
        samples=SAMPLES,
        repeats=REPEATS,
        warmup=WARMUP,
        users=USER_COUNT,
        seed=SEED,
        mode="sequential, varied users and flag keys",
    )

    rows = []

    for flag_count in FLAG_COUNTS:
        row = run_case(flag_count, run_dir)
        rows.append(row)

        print(
            f"flags={flag_count:4} "
            f"p50={row['p50_us']:.3f} us "
            f"p95={row['p95_us']:.3f} us "
            f"p99={row['p99_us']:.3f} us "
            f"eval/s={row['evaluations_per_second']}"
        )

    with (run_dir / "summary.csv").open(
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

    print(f"\nSaved results to: {run_dir}")


if __name__ == "__main__":
    main()