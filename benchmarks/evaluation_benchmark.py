import csv
import math
import platform
import statistics
from pathlib import Path
from time import perf_counter_ns
import json
import os
import subprocess

from datetime import datetime, timezone

import httpx

from flagforge_sdk import FlagForgeClient
from flagforge_sdk.client import calculate_checksum


SAMPLES = 20_000
REPEATS = 3
WARMUP = 2_000

FLAG_COUNTS = (1, 10, 100, 1000)

CASES = (
    "fixed",
    "first_rule",
    "last_rule",
    "no_match",
    "percentage",
    "missing_flag",
)

USER = {
    "key": "user-123",
    "country": "IN",
}

RESULTS_DIR = Path(__file__).resolve().parent / "results"
def git_output(*arguments):
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            check=True,
        )

        return result.stdout.strip()

    except (OSError, subprocess.CalledProcessError):
        return None


def create_run_directory(name, **settings):
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    run_dir = RESULTS_DIR / f"{name}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=False)

    status = git_output("status", "--porcelain")

    metadata = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": os.environ.get(
            "BENCHMARK_CPU",
            platform.processor(),
        ),
        "git_commit": git_output("rev-parse", "HEAD"),
        "git_dirty": (
            status != ""
            if status is not None
            else None
        ),
        "settings": settings,
    }

    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    return run_dir


def make_rule(priority, matches, percentage=False):
    serve = (
        {
            "type": "percentage",
            "true_basis_points": 1500,
        }
        if percentage
        else {
            "type": "fixed",
            "value": True,
        }
    )

    return {
        "priority": priority,
        "conditions": [
            {
                "attribute": "country",
                "operator": "equals",
                "value": "IN" if matches else "NEVER",
            }
        ],
        "serve": serve,
    }


def make_configuration(case, flag_count):
    if case == "first_rule":
        rules = [
            make_rule(i, matches=(i == 1))
            for i in range(1, 11)
        ]

    elif case == "last_rule":
        rules = [
            make_rule(i, matches=(i == 10))
            for i in range(1, 11)
        ]

    elif case == "no_match":
        rules = [
            make_rule(i, matches=False)
            for i in range(1, 11)
        ]

    elif case == "percentage":
        rules = [
            make_rule(1, matches=True, percentage=True)
        ]

    else:
        rules = [
            {
                "priority": 1,
                "conditions": [],
                "serve": {
                    "type": "fixed",
                    "value": True,
                },
            }
        ]

    flags = {
        "benchmark_flag": {
            "id": "11111111-1111-4111-8111-111111111111",
            "enabled": True,
            "default_value": False,
            "rules": rules,
        }
    }

    for i in range(flag_count - 1):
        flags[f"unused_flag_{i}"] = {
            "id": f"{i + 2:032x}",
            "enabled": True,
            "default_value": False,
            "rules": [],
        }

    return {
        "schema_version": 1,
        "environment": {
            "id": "22222222-2222-4222-8222-222222222222",
            "key": "benchmark",
        },
        "flags": flags,
    }


def percentile(sorted_values, fraction):
    index = math.ceil(len(sorted_values) * fraction) - 1
    return sorted_values[max(0, index)]


def benchmark_case(case, flag_count):
    configuration = make_configuration(case, flag_count)

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

    flag_key = (
        "unknown_flag"
        if case == "missing_flag"
        else "benchmark_flag"
    )

    def evaluate():
        return client.boolean_value(
            flag_key,
            user=USER,
            default=False,
        )

    try:
        client.initialize()

        expected_reason = {
            "fixed": "RULE_MATCH",
            "first_rule": "RULE_MATCH",
            "last_rule": "RULE_MATCH",
            "no_match": "DEFAULT_VALUE",
            "percentage": "PERCENTAGE_ROLLOUT",
            "missing_flag": "FLAG_NOT_FOUND",
        }[case]

        details = client.boolean_value_details(
            flag_key,
            user=USER,
            default=False,
        )

        assert details.reason == expected_reason, details

        for _ in range(WARMUP):
            evaluate()

        durations = []
        throughput_runs = []

        for _ in range(REPEATS):
            # Individual timings for latency percentiles.
            for _ in range(SAMPLES):
                started = perf_counter_ns()
                evaluate()
                elapsed = perf_counter_ns() - started

                durations.append(elapsed)

            # Separate batch timing for throughput.
            started = perf_counter_ns()

            for _ in range(SAMPLES):
                evaluate()

            elapsed = perf_counter_ns() - started

            throughput_runs.append(
                SAMPLES * 1_000_000_000 / elapsed
            )

        # Initialization is the only HTTP request.
        assert request_count == 1, (
            "Evaluation unexpectedly made HTTP requests"
        )

        durations.sort()

        return {
            "case": case,
            "flags": flag_count,
            "p50_us": round(
                percentile(durations, 0.50) / 1000, 3
            ),
            "p95_us": round(
                percentile(durations, 0.95) / 1000, 3
            ),
            "p99_us": round(
                percentile(durations, 0.99) / 1000, 3
            ),
            "evaluations_per_second": round(
                statistics.median(throughput_runs)
            ),
        }

    finally:
        client.close()


def main():
    run_dir = create_run_directory(
        "evaluation",
        samples=SAMPLES,
        repeats=REPEATS,
        warmup=WARMUP,
        mode="sequential, fixed user and selected flag",
    )

    metadata = (
        f"Python: {platform.python_version()}\n"
        f"OS: {platform.platform()}\n"
        f"Processor: {platform.processor() or 'unknown'}\n"
        f"Samples per repeat: {SAMPLES}\n"
        f"Repeats: {REPEATS}\n"
        f"Warmup per case: {WARMUP}\n"
        "Mode: sequential, one process, no realtime threads\n"
    )

    print(metadata)

    (run_dir / "environment.txt").write_text(
        metadata,
        encoding="utf-8",
    )

    rows = []

    for flag_count in FLAG_COUNTS:
        for case in CASES:
            row = benchmark_case(case, flag_count)
            rows.append(row)

            print(
                f"{case:14} "
                f"flags={flag_count:4} "
                f"p50={row['p50_us']:8.3f} us "
                f"p95={row['p95_us']:8.3f} us "
                f"p99={row['p99_us']:8.3f} us "
                f"eval/s={row['evaluations_per_second']}"
            )

    output = run_dir / "evaluation.csv"

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

    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()