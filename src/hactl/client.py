import httpx


class HomeAssistantError(Exception):
    pass


class HomeAssistantClient:
    def __init__(self, url: str, token: str):
        self.url = url

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
