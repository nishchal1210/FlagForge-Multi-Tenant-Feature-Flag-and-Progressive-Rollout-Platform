import hashlib
import json
import threading
from pathlib import Path
from typing import Any
import random
import time


import httpx
import logging

logger = logging.getLogger(__name__)

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
    ).hexdigest() # return the hash as a hexadecimal string

class FlagForgeClient:
    def __init__(
        self,
        sdk_key: str,
        base_url: str,
        cache_path: str | Path | None = None,
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
        # HTTP REQ timeout is 5 secs, this prevents the sdk from 
        # waiting forever when the flagforage server is unavailable
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
            transport = transport
        )

        self._lock = threading.RLock() # Reading and replacing the active in-memory state
        self._configuration: dict[str, Any] | None = None
        self._version: int | None = None
        self._checksum: str | None = None
        self._stop_event = threading.Event()
        self._stream_thread: threading.Thread | None = None
        self._poll_thread: threading.Thread | None = None
        self._refresh_lock = threading.Lock() # The complete refresh operation

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
        with self._refresh_lock:
            with self._lock:
                current_checksum = self._checksum
                current_version = self._version

            headers = {}

            if current_checksum is not None:
                headers["If-None-Match"] = (
                    f'"{current_checksum}"'
                )

            response = self._http.get(
                "/api/sdk/v1/config",
                headers=headers,
            )

            if response.status_code == 304:
                if current_checksum is None:
                    raise ValueError(
                        "Received 304 without a local configuration"
                    )

                return False

            response.raise_for_status()

            payload = response.json()

            if not isinstance(payload, dict):
                raise ValueError(
                    "Configuration response must be an object"
                )

            version = payload.get("version")
            expected_checksum = payload.get("checksum")
            configuration = payload.get("configuration")

            if type(version) is not int or version < 1:
                raise ValueError(
                    "Configuration version must be a positive integer"
                )

            if not isinstance(expected_checksum, str):
                raise ValueError(
                    "Configuration checksum must be a string"
                )

            if (
                not isinstance(configuration, dict)
                or not isinstance(
                    configuration.get("flags"),
                    dict,
                )
            ):
                raise ValueError(
                    "Configuration must contain a flags object"
                )

            actual_checksum = calculate_checksum(
                configuration
            )

            if actual_checksum != expected_checksum:
                raise ValueError(
                    "Configuration checksum mismatch"
                )

            if current_version is not None:
                if version < current_version:
                    raise ValueError(
                        "Configuration version moved backwards"
                    )

                if version == current_version:
                    if expected_checksum != current_checksum:
                        raise ValueError(
                            "An existing configuration version changed"
                        )

                    return False

            # Preserve the earlier save-before-activation behaviour.
            self._save_cache(payload)

            with self._lock:
                self._configuration = configuration
                self._version = version
                self._checksum = expected_checksum

            return True

    def initialize(self) -> None:
        cache_loaded = self._load_cache()
        try:
            self.refresh()
        except Exception:
            if not cache_loaded:
                raise # server unavailable and no cache exist

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

    def _handle_sse_event(
        self,
        event_name: str | None,
        data: str,
    ) -> None:
        if event_name != "config_updated":
            return # ignore unrelated events

        try:
            event = json.loads(data)
            event_version = event["version"]

            with self._lock:
                current_version = self._version

            if (
                current_version is None
                or event_version > current_version
            ):
                self.refresh()

        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):# invalid sse data is ignored rather than terminating the realtime thread.
            return

    def _stream_loop(self) -> None:
        retry_delay = 1.0

        while not self._stop_event.is_set():
            try:
                # Recover anything missed while disconnected.
                self.refresh()

                with httpx.stream(
                    "GET",
                    (
                        f"{self._http.base_url}"
                        "/api/sdk/v1/config/stream"
                    ),
                    headers={
                        "Authorization": (
                            f"Bearer {self._sdk_key}"
                        ),
                    },
                    timeout=httpx.Timeout(
                        connect=5.0,
                        read=30.0,
                        write=5.0,
                        pool=5.0,
                    ),
                ) as response:
                    response.raise_for_status()

                    retry_delay = 1.0
                    event_name = None
                    data_lines: list[str] = []

                    for line in response.iter_lines():
                        if self._stop_event.is_set():
                            return

                        if line == "":
                            if data_lines:
                                self._handle_sse_event(
                                    event_name,
                                    "\n".join(data_lines),
                                )

                            event_name = None
                            data_lines = []
                            continue

                        if line.startswith("event:"):
                            event_name = line[6:].strip()

                        elif line.startswith("data:"):
                            data_lines.append(
                                line[5:].strip()
                            )

            except (
                httpx.HTTPError,
                OSError,
                ValueError,
            ):
                if self._stop_event.is_set():
                    return

                logger.exception(
                    "SSE update failed; reconnecting"
                )

                jitter = random.uniform(0, 0.5)

                self._stop_event.wait(
                    retry_delay + jitter
                )

                retry_delay = min(
                    retry_delay * 2,
                    30.0,
                )


    def _poll_loop(
        self,
        poll_interval_seconds: float,
    ) -> None:
        while not self._stop_event.wait(
            poll_interval_seconds
        ):
            try:
                self.refresh()
            except (
                httpx.HTTPError,
                OSError,
                ValueError,
            ):
                logger.exception(
                    "Polling refresh failed; keeping existing configuration"
                )


    def start_realtime(
        self,
        poll_interval_seconds: float = 60.0,
    ) -> None:
        if (
            self._stream_thread is not None
            and self._stream_thread.is_alive()
        ):
            return
        self._stop_event.clear()
        self._stream_thread = threading.Thread(
            target=self._stream_loop,
            name="flagforge-sse",
            daemon=True,
        )
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            args=(poll_interval_seconds,),
            name="flagforge-poll",
            daemon=True,
        )
        self._stream_thread.start()
        self._poll_thread.start()

    def stop_realtime(self) -> None:
        self._stop_event.set()

        if self._stream_thread is not None:
            self._stream_thread.join(timeout=5)

        if self._poll_thread is not None:
            self._poll_thread.join(timeout=5)

    def close(self) -> None:
        self.stop_realtime()
        self._http.close()