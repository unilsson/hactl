import json
from urllib.parse import urlsplit, urlunsplit

import httpx
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect


class HomeAssistantError(Exception):
    pass


class HomeAssistantClient:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token

        self.client = httpx.Client(
            base_url=url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )

    def close(self):
        self.client.close()

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self.client.request(
                method,
                path,
                **kwargs,
            )

            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            raise HomeAssistantError(
                f"Home Assistant returned "
                f"{exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc

        except httpx.RequestError as exc:
            raise HomeAssistantError(
                f"Could not connect to Home Assistant: {exc}"
            ) from exc

        if response.content:
            return response.json()

        return None

    def _websocket_url(self) -> str:
        parsed = urlsplit(self.url)

        if parsed.scheme == "http":
            scheme = "ws"
        elif parsed.scheme == "https":
            scheme = "wss"
        else:
            raise HomeAssistantError(
                "Home Assistant URL must use http or https."
            )

        base_path = parsed.path.rstrip("/")
        websocket_path = f"{base_path}/api/websocket"

        return urlunsplit(
            (
                scheme,
                parsed.netloc,
                websocket_path,
                "",
                "",
            )
        )

    @staticmethod
    def _receive_websocket_json(websocket) -> dict:
        raw_message = websocket.recv()

        if isinstance(raw_message, bytes):
            raw_message = raw_message.decode("utf-8")

        try:
            message = json.loads(raw_message)
        except (TypeError, json.JSONDecodeError) as exc:
            raise HomeAssistantError(
                "Home Assistant returned an invalid WebSocket message."
            ) from exc

        if not isinstance(message, dict):
            raise HomeAssistantError(
                "Home Assistant returned an unexpected WebSocket message."
            )

        return message

    def _websocket_requests(
        self,
        requests: list[str | dict],
    ) -> list:
        try:
            with connect(
                self._websocket_url(),
                open_timeout=10.0,
                close_timeout=2.0,
                max_size=16 * 1024 * 1024,
            ) as websocket:
                hello = self._receive_websocket_json(
                    websocket
                )

                if hello.get("type") != "auth_required":
                    raise HomeAssistantError(
                        "Unexpected Home Assistant WebSocket handshake."
                    )

                websocket.send(
                    json.dumps(
                        {
                            "type": "auth",
                            "access_token": self.token,
                        }
                    )
                )

                auth_result = self._receive_websocket_json(
                    websocket
                )

                if auth_result.get("type") == "auth_invalid":
                    raise HomeAssistantError(
                        "Home Assistant WebSocket authentication failed."
                    )

                if auth_result.get("type") != "auth_ok":
                    raise HomeAssistantError(
                        "Unexpected Home Assistant WebSocket authentication response."
                    )

                results = []

                for request_id, request in enumerate(
                    requests,
                    start=1,
                ):
                    if isinstance(request, str):
                        payload = {
                            "type": request,
                        }
                    else:
                        payload = dict(request)

                    request_type = str(
                        payload.get(
                            "type",
                            "",
                        )
                    )
                    payload["id"] = request_id

                    websocket.send(
                        json.dumps(payload)
                    )

                    while True:
                        message = self._receive_websocket_json(
                            websocket
                        )

                        if message.get("id") != request_id:
                            continue

                        if message.get("type") != "result":
                            continue

                        if not message.get("success"):
                            error = message.get("error", {})
                            error_message = error.get(
                                "message",
                                "Unknown Home Assistant WebSocket error",
                            )

                            raise HomeAssistantError(
                                f"Home Assistant WebSocket request "
                                f"{request_type} failed: {error_message}"
                            )

                        results.append(
                            message.get("result")
                        )
                        break

                return results

        except HomeAssistantError:
            raise
        except (
            OSError,
            TimeoutError,
            WebSocketException,
        ) as exc:
            raise HomeAssistantError(
                f"Could not connect to Home Assistant WebSocket API: {exc}"
            ) from exc

    def get_states(self):
        return self._request(
            "GET",
            "/api/states",
        )

    def get_state(self, entity_id: str):
        return self._request(
            "GET",
            f"/api/states/{entity_id}",
        )

    def get_areas(self):
        return self._websocket_requests(
            [
                "config/area_registry/list",
            ]
        )[0]

    def get_devices(self):
        return self._websocket_requests(
            [
                "config/device_registry/list",
            ]
        )[0]

    def get_areas_and_devices(self):
        areas, devices = self._websocket_requests(
            [
                "config/area_registry/list",
                "config/device_registry/list",
            ]
        )

        return areas, devices

    def get_entity_registry(self):
        return self._websocket_requests(
            [
                "config/entity_registry/list",
            ]
        )[0]

    def get_registry_data(self):
        areas, devices, entities = self._websocket_requests(
            [
                "config/area_registry/list",
                "config/device_registry/list",
                "config/entity_registry/list",
            ]
        )

        return areas, devices, entities

    def update_entity_area(
        self,
        entity_id: str,
        area_id: str | None,
    ):
        return self._websocket_requests(
            [
                {
                    "type": "config/entity_registry/update",
                    "entity_id": entity_id,
                    "area_id": area_id,
                }
            ]
        )[0]

    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: dict | None = None,
    ):
        payload = {
            "entity_id": entity_id,
        }

        if data:
            payload.update(data)

        return self._request(
            "POST",
            f"/api/services/{domain}/{service}",
            json=payload,
        )
