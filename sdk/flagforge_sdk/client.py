import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import httpx

from flagforge_sdk.evaluator import (
    EvaluationDetails,
    evaluate_boolean_flag,
)


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

class FlagForgeClient:
    def __init__(
        self,
        sdk_key: str,
        base_url: str,
        cache_path: str | Path | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._sdk_key = sdk_key
        self._cache_path = (
            Path(cache_path)
            if cache_path is not None
            else None
        )

        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            headers={
                "Authorization": f"Bearer {sdk_key}",
            },
        )

        self._lock = threading.RLock()
        self._configuration: dict[str, Any] | None = None
        self._version: int | None = None
        self._checksum: str | None = None

    def _load_cache(self) -> bool:
        if (
            self._cache_path is None
            or not self._cache_path.exists()
        ):
            return False

        try:
            payload = json.loads(
                self._cache_path.read_text(
                    encoding="utf-8"
                )
            )

            configuration = payload["configuration"]
            expected_checksum = payload["checksum"]

            if (
                calculate_checksum(configuration)
                != expected_checksum
            ):
                return False

            with self._lock:
                self._configuration = configuration
                self._version = payload["version"]
                self._checksum = expected_checksum

            return True

        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return False


    def _save_cache(
        self,
        payload: dict[str, Any],
    ) -> None:
        if self._cache_path is None:
            return

        self._cache_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self._cache_path.with_suffix(
            self._cache_path.suffix + ".tmp"
        )

        temporary_path.write_text(
            json.dumps(
                payload,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        temporary_path.replace(self._cache_path)

    def refresh(self) -> bool:
        headers = {}

        with self._lock:
            checksum = self._checksum

        if checksum is not None:
            headers["If-None-Match"] = f'"{checksum}"'

        response = self._http.get(
            "/api/sdk/v1/config",
            headers=headers,
        )

        if response.status_code == 304:
            return False

        response.raise_for_status()

        payload = response.json()

        configuration = payload["configuration"]
        expected_checksum = payload["checksum"]

        actual_checksum = calculate_checksum(
            configuration
        )

        if actual_checksum != expected_checksum:
            raise ValueError(
                "Configuration checksum mismatch"
            )

        # Save before making it active.
        self._save_cache(payload)

        with self._lock:
            self._configuration = configuration
            self._version = payload["version"]
            self._checksum = expected_checksum

        return True

    def initialize(self) -> None:
        cache_loaded = self._load_cache()
        try:
            self.refresh()
        except Exception:
            if not cache_loaded:
                raise

    def boolean_value_details(
        self,
        flag_key: str,
        user: dict[str, Any],
        default: bool = False,
    ) -> EvaluationDetails:
        with self._lock:
            configuration = self._configuration

        if configuration is None:
            return EvaluationDetails(
                value=default,
                reason="CLIENT_NOT_INITIALIZED",
            )

        return evaluate_boolean_flag(
            configuration=configuration,
            flag_key=flag_key,
            user=user,
            fallback=default,
        )


    def boolean_value(
        self,
        flag_key: str,
        user: dict[str, Any],
        default: bool = False,
    ) -> bool:
        return self.boolean_value_details(
            flag_key=flag_key,
            user=user,
            default=default,
        ).value


    def close(self) -> None:
        self._http.close()