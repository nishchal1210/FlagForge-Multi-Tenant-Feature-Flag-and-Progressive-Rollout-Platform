import logging
import os
import time

from flagforge_sdk import FlagForgeClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def main():
    sdk_key = os.environ.get("FLAGFORGE_SDK_KEY")

    if not sdk_key:
        raise RuntimeError(
            "Set FLAGFORGE_SDK_KEY in .env.docker "
            "before starting the demo"
        )

    client = FlagForgeClient(
        sdk_key=sdk_key,
        base_url=os.environ.get(
            "FLAGFORGE_BASE_URL",
            "http://api:8000",
        ),
        cache_path="/data/flagforge-production.json",
    )

    try:
        client.initialize()

        client.start_realtime(
            poll_interval_seconds=5.0,
        )

        while True:
            details = client.boolean_value_details(
                "reliability_test",
                user={
                    "key": "user-123",
                    "country": "IN",
                },
                default=False,
            )

            print(
                f"flag=reliability_test "
                f"value={details.value} "
                f"reason={details.reason} "
                f"priority={details.matched_rule_priority} "
                f"bucket={details.bucket}",
                flush=True,
            )

            time.sleep(2)

    except KeyboardInterrupt:
        pass

    finally:
        client.close()


if __name__ == "__main__":
    main()