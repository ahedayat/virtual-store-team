import json
import os
import unittest
from unittest.mock import patch

import httpx

from agents.shared.django_client import (
    DjangoClient,
    DjangoConnectionError,
    DjangoHTTPError,
    DjangoJSONError,
    DjangoTimeoutError,
    join_url,
    normalize_base_url,
)


class UrlJoinTests(unittest.TestCase):
    def test_normalize_base_url_strips_trailing_slash(self):
        self.assertEqual(normalize_base_url("http://backend:8000/"), "http://backend:8000")

    def test_join_url_with_leading_slash_on_path(self):
        self.assertEqual(
            join_url("http://backend:8000/", "/internal/ai/context/1/"),
            "http://backend:8000/internal/ai/context/1/",
        )

    def test_join_url_without_leading_slash_on_path(self):
        self.assertEqual(
            join_url("http://backend:8000", "internal/ai/context/1/"),
            "http://backend:8000/internal/ai/context/1/",
        )


class HeaderForwardingTests(unittest.TestCase):
    def test_authorization_header_is_sent_when_service_token_provided(self):
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={"ok": True})

        client = self._build_client(handler, service_token="service-jwt")

        client.get("/internal/ai/auth-check/")

        self.assertEqual(
            captured_headers.get("authorization"),
            "Bearer service-jwt",
        )

    def test_request_id_header_is_sent_when_request_id_provided(self):
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={"ok": True})

        client = self._build_client(handler, request_id="corr-123")

        client.get("/internal/ai/auth-check/")

        self.assertEqual(captured_headers.get("x-request-id"), "corr-123")

    def _build_client(self, handler, **kwargs) -> DjangoClient:
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        return DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
            **kwargs,
        )


class SuccessfulRequestTests(unittest.TestCase):
    def test_successful_get_returns_parsed_json(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertEqual(
                str(request.url),
                "http://backend:8000/internal/ai/context/run-1/",
            )
            return httpx.Response(200, json={"report_run_id": "run-1"})

        client = self._build_client(handler)
        payload = client.get("/internal/ai/context/run-1/")

        self.assertEqual(payload, {"report_run_id": "run-1"})

    def test_successful_post_sends_json_and_returns_parsed_json(self):
        captured_body: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            captured_body.update(json.loads(request.content.decode("utf-8")))
            return httpx.Response(201, json={"created": True})

        client = self._build_client(handler)
        payload = client.post(
            "/internal/ai/actions/",
            json={"action_type": "sales.restock"},
        )

        self.assertEqual(captured_body, {"action_type": "sales.restock"})
        self.assertEqual(payload, {"created": True})

    def _build_client(self, handler) -> DjangoClient:
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        return DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )


class ErrorHandlingTests(unittest.TestCase):
    def test_non_2xx_response_raises_http_error_with_status_and_message(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"detail": "Not found."})

        client = self._build_client(handler)

        with self.assertRaises(DjangoHTTPError) as context:
            client.get("/missing/")

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(str(context.exception), "Not found.")

    def test_timeout_raises_timeout_specific_error(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=_request)

        client = self._build_client(handler)

        with self.assertRaises(DjangoTimeoutError):
            client.get("/internal/ai/context/run-1/")

    def test_connection_error_raises_connection_specific_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection failed", request=request)

        client = self._build_client(handler)

        with self.assertRaises(DjangoConnectionError):
            client.get("/internal/ai/context/run-1/")

    def test_invalid_json_raises_clear_json_error(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"not-json")

        client = self._build_client(handler)

        with self.assertRaises(DjangoJSONError) as context:
            client.get("/internal/ai/context/run-1/")

        self.assertIn("Invalid JSON response", str(context.exception))

    def _build_client(self, handler) -> DjangoClient:
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        return DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )


class RetryBehaviorTests(unittest.TestCase):
    def test_get_retries_transient_failures_and_eventually_succeeds(self):
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            if attempts["count"] < 3:
                return httpx.Response(503, json={"detail": "Unavailable"})
            return httpx.Response(200, json={"ok": True})

        client = self._build_client(handler, max_retries=2, retry_backoff_seconds=0)

        payload = client.get("/internal/ai/context/run-1/")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(attempts["count"], 3)

    def test_get_fails_after_retry_exhaustion(self):
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(502, json={"detail": "Bad gateway"})

        client = self._build_client(handler, max_retries=2, retry_backoff_seconds=0)

        with self.assertRaises(DjangoHTTPError) as context:
            client.get("/internal/ai/context/run-1/")

        self.assertEqual(context.exception.status_code, 502)
        self.assertEqual(attempts["count"], 3)

    def test_post_is_not_retried_by_default(self):
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(503, json={"detail": "Unavailable"})

        client = self._build_client(handler, max_retries=2, retry_backoff_seconds=0)

        with self.assertRaises(DjangoHTTPError):
            client.post("/internal/ai/actions/", json={"action_type": "sales.restock"})

        self.assertEqual(attempts["count"], 1)

    def test_get_retries_connection_errors(self):
        attempts = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise httpx.ConnectError("temporary", request=request)
            return httpx.Response(200, json={"ok": True})

        client = self._build_client(handler, max_retries=2, retry_backoff_seconds=0)

        payload = client.get("/internal/ai/context/run-1/")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(attempts["count"], 2)

    def _build_client(self, handler, **kwargs) -> DjangoClient:
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        return DjangoClient(
            base_url="http://backend:8000",
            http_client=http_client,
            **kwargs,
        )


class CreateAgentOutputTests(unittest.TestCase):
    def test_create_agent_output_posts_to_internal_endpoint(self):
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["json"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                201,
                json={
                    "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                    "agent_name": "coordinator-agent",
                    "output_type": "sales_analysis",
                    "report_run_id": "11111111-1111-4111-8111-111111111111",
                },
            )

        client = self._build_client(handler, service_token="coord-jwt", request_id="req-1")
        payload = {
            "output_type": "sales_analysis",
            "payload": {"summary": "ok"},
            "report_run_id": "11111111-1111-4111-8111-111111111111",
        }

        response = client.create_agent_output(payload)

        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["path"], "/internal/ai/agent-outputs/")
        self.assertEqual(captured["json"], payload)
        self.assertEqual(response["id"], "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

    def _build_client(self, handler, **kwargs) -> DjangoClient:
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        return DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
            **kwargs,
        )


class EnvironmentConfigurationTests(unittest.TestCase):
    def test_reads_client_settings_from_environment(self):
        env = {
            "DJANGO_INTERNAL_BASE_URL": "http://backend:8000/",
            "DJANGO_CLIENT_TIMEOUT_SECONDS": "45",
            "DJANGO_CLIENT_MAX_RETRIES": "1",
            "DJANGO_CLIENT_RETRY_BACKOFF_SECONDS": "0.5",
        }

        with patch.dict("os.environ", env, clear=False):
            client = DjangoClient(service_token="token")

        self.assertEqual(client.base_url, "http://backend:8000")
        self.assertEqual(client.timeout_seconds, 45.0)
        self.assertEqual(client.max_retries, 1)
        self.assertEqual(client.retry_backoff_seconds, 0.5)

    def test_missing_base_url_raises_value_error(self):
        env = os.environ.copy()
        env.pop("DJANGO_INTERNAL_BASE_URL", None)
        with patch.dict("os.environ", env, clear=True):
            with self.assertRaises(ValueError):
                DjangoClient()


if __name__ == "__main__":
    unittest.main()
