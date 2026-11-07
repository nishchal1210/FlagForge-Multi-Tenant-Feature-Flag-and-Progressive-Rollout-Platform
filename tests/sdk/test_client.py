import httpx
import pytest

from flagforge_sdk import FlagForgeClient
from flagforge_sdk.client import calculate_checksum


USER = {
    "key": "user-123",
    "country": "IN",
}


def make_payload(
    version: int = 1,
    value: bool = True,
) -> dict:
    configuration = {
        "flags": {
            "new_checkout": {
                "id": "checkout-flag-id",
                "enabled": True,
                "default_value": value,
                "rules": [],
            }
        }
    }

    return {
        "version": version,
        "checksum": calculate_checksum(configuration),
        "configuration": configuration,
    }


def make_client(handler, cache_path=None):
    return FlagForgeClient(
        sdk_key="test-sdk-key",
        base_url="http://flagforge.test",
        cache_path=cache_path,
        transport=httpx.MockTransport(handler),
    )


def test_evaluation_makes_no_http_requests():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json=make_payload(),
        )

    client = make_client(handler)

    try:
        client.initialize()

        assert len(requests) == 1

        for _ in range(100):
            assert client.boolean_value(
                "new_checkout",
                user=USER,
            ) is True

        assert len(requests) == 1

    finally:
        client.close()


def test_unchanged_configuration_uses_etag():
    payload = make_payload()
    requests = []

    def handler(request):
        requests.append(request)

        if len(requests) == 1:
            return httpx.Response(
                200,
                json=payload,
            )

        assert request.headers["If-None-Match"] == (
            f'"{payload["checksum"]}"'
        )

        return httpx.Response(304)

    client = make_client(handler)

    try:
        client.initialize()

        assert client.refresh() is False

        assert client.boolean_value(
            "new_checkout",
            user=USER,
        ) is True

    finally:
        client.close()


def test_bad_checksum_preserves_active_configuration():
    good_payload = make_payload()
    bad_payload = make_payload(
        version=2,
        value=False,
    )
    bad_payload["checksum"] = "incorrect"

    responses = iter([
        good_payload,
        bad_payload,
    ])

    def handler(request):
        return httpx.Response(
            200,
            json=next(responses),
        )

    client = make_client(handler)

    try:
        client.initialize()

        with pytest.raises(
            ValueError,
            match="checksum mismatch",
        ):
            client.refresh()

        assert client.boolean_value(
            "new_checkout",
            user=USER,
        ) is True

    finally:
        client.close()


def test_failed_refresh_preserves_active_configuration():
    request_count = 0

    def handler(request):
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            return httpx.Response(
                200,
                json=make_payload(),
            )

        raise httpx.ConnectError(
            "Server unavailable",
            request=request,
        )

    client = make_client(handler)

    try:
        client.initialize()

        with pytest.raises(httpx.ConnectError):
            client.refresh()

        assert client.boolean_value(
            "new_checkout",
            user=USER,
        ) is True

    finally:
        client.close()


def test_restart_uses_disk_cache_when_server_is_down(
    tmp_path,
):
    cache_path = tmp_path / "configuration.json"

    first_client = make_client(
        lambda request: httpx.Response(
            200,
            json=make_payload(),
        ),
        cache_path=cache_path,
    )

    try:
        first_client.initialize()
    finally:
        first_client.close()

    def offline_handler(request):
        raise httpx.ConnectError(
            "Server unavailable",
            request=request,
        )

    restarted_client = make_client(
        offline_handler,
        cache_path=cache_path,
    )

    try:
        restarted_client.initialize()

        assert restarted_client.boolean_value(
            "new_checkout",
            user=USER,
        ) is True

    finally:
        restarted_client.close()


def test_older_version_is_rejected():
    responses = iter([
        make_payload(version=3, value=True),
        make_payload(version=2, value=False),
    ])

    client = make_client(
        lambda request: httpx.Response(
            200,
            json=next(responses),
        )
    )

    try:
        client.initialize()

        with pytest.raises(
            ValueError,
            match="moved backwards",
        ):
            client.refresh()

        assert client.boolean_value(
            "new_checkout",
            user=USER,
        ) is True

    finally:
        client.close()


def test_missing_flag_returns_caller_default():
    client = make_client(
        lambda request: httpx.Response(
            200,
            json=make_payload(),
        )
    )

    try:
        client.initialize()

        details = client.boolean_value_details(
            "unknown_flag",
            user=USER,
            default=False,
        )

        assert details.value is False
        assert details.reason == "FLAG_NOT_FOUND"

    finally:
        client.close()