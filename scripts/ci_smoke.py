import os
import tempfile
import time
import uuid

from pathlib import Path

import httpx

from flagforge_sdk import FlagForgeClient


BASE_URL = os.environ.get(
    "FLAGFORGE_TEST_URL",
    "http://127.0.0.1:8001",
)


def wait_for_api():
    deadline = time.monotonic() + 60

    with httpx.Client(
        base_url=BASE_URL,
        timeout=3.0,
    ) as http:
        while time.monotonic() < deadline:
            try:
                response = http.get("/openapi.json")

                if response.status_code == 200:
                    return

            except httpx.HTTPError:
                pass

            time.sleep(1)

    raise RuntimeError(
        f"API did not become available at {BASE_URL}"
    )


def create(http, path, payload):
    response = http.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def publish(http, environment_path):
    response = http.post(
        f"{environment_path}/config/publish"
    )
    response.raise_for_status()
    return response.json()


def main():
    wait_for_api()

    run_id = uuid.uuid4().hex[:12]

    with httpx.Client(
        base_url=BASE_URL,
        timeout=10.0,
    ) as http:
        tenant = create(
            http,
            "/api/v1/tenants",
            {"name": f"CI Tenant {run_id}"},
        )

        project = create(
            http,
            f"/api/v1/tenants/{tenant['id']}/projects",
            {
                "name": "CI Project",
                "key": f"ci_{run_id}",
            },
        )

        project_path = (
            f"/api/v1/tenants/{tenant['id']}"
            f"/projects/{project['id']}"
        )

        environment = create(
            http,
            f"{project_path}/environments",
            {
                "name": "CI Environment",
                "key": "ci",
            },
        )

        environment_path = (
            f"{project_path}/environments"
            f"/{environment['id']}"
        )

        create(
            http,
            f"{environment_path}/flags",
            {
                "key": "ci_flag",
                "name": "CI Flag",
                "enabled": True,
                "default_value": False,
            },
        )

        first_publication = publish(
            http,
            environment_path,
        )

        assert first_publication["version"] == 1

        key = create(
            http,
            f"{environment_path}/sdk-keys",
            {"name": f"ci_key_{run_id}"},
        )

        with tempfile.TemporaryDirectory() as directory:
            client = FlagForgeClient(
                sdk_key=key["key"],
                base_url=BASE_URL,
                cache_path=(
                    Path(directory) / "configuration.json"
                ),
            )

            user = {"key": "ci-user"}

            try:
                client.initialize()

                assert client.boolean_value(
                    "ci_flag",
                    user=user,
                    default=True,
                ) is False

                print("PASS: published snapshot downloaded")

                # Nothing changed: conditional refresh
                # should preserve the current state.
                assert client.refresh() is False

                print("PASS: unchanged refresh")

                response = http.patch(
                    f"{environment_path}/flags/ci_flag",
                    json={"default_value": True},
                )
                response.raise_for_status()

                # Editing a draft must not change
                # the downloadable snapshot.
                assert client.refresh() is False

                assert client.boolean_value(
                    "ci_flag",
                    user=user,
                ) is False

                print("PASS: draft remains unpublished")

                second_publication = publish(
                    http,
                    environment_path,
                )

                assert second_publication["version"] == 2
                assert client.refresh() is True

                assert client.boolean_value(
                    "ci_flag",
                    user=user,
                ) is True

                print("PASS: new publication adopted")

                response = http.delete(
                    f"{environment_path}"
                    f"/sdk-keys/{key['id']}"
                )
                response.raise_for_status()

                response = http.get(
                    "/api/sdk/v1/config",
                    headers={
                        "Authorization": (
                            f"Bearer {key['key']}"
                        ),
                    },
                )

                assert response.status_code == 401

                # Revocation blocks downloads but does
                # not erase the active local snapshot.
                assert client.boolean_value(
                    "ci_flag",
                    user=user,
                ) is True

                print("PASS: revoked key returns 401")
                print("PASS: local configuration retained")

            finally:
                client.close()

    print("All Docker integration checks passed.")


if __name__ == "__main__":
    main()