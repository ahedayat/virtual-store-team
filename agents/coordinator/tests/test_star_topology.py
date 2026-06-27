"""Tests for coordinator star-topology contract (Phase 10.1)."""

from __future__ import annotations

import ast
import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from agents.coordinator import specialist_clients, topology, workflow
from agents.coordinator.specialist_clients import (
    SpecialistAgentClient,
    SpecialistAgentHTTPError,
)
from agents.coordinator.topology import (
    COORDINATOR_SERVICE_NAME,
    SPECIALIST_AGENT_URL_ENV_VARS,
    SPECIALIST_PEER_CALL_PATHS,
    SPECIALIST_RUN_PATH,
    SpecialistAgentName,
    UnknownSpecialistAgentError,
    assert_star_topology,
    build_specialist_run_url,
    get_allowed_specialist_agents,
    parse_specialist_agent_name,
    resolve_specialist_base_url,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

SPECIALIST_AGENT_PACKAGES = ("sales", "content", "support")
OTHER_SPECIALIST_URL_ENV_VARS = {
    "sales": frozenset({"CONTENT_AGENT_URL", "SUPPORT_AGENT_URL"}),
    "content": frozenset({"SALES_AGENT_URL", "SUPPORT_AGENT_URL"}),
    "support": frozenset({"SALES_AGENT_URL", "CONTENT_AGENT_URL"}),
}


class StarTopologyContractTests(unittest.TestCase):
    def test_allowed_specialist_agents_are_sales_content_support(self) -> None:
        allowed = get_allowed_specialist_agents()

        self.assertEqual(len(allowed), 3)
        self.assertEqual(
            {agent.value for agent in allowed},
            {"sales", "content", "support"},
        )

    def test_assert_star_topology_passes(self) -> None:
        assert_star_topology()

    def test_no_specialist_peer_call_paths_defined(self) -> None:
        self.assertEqual(SPECIALIST_PEER_CALL_PATHS, frozenset())

    def test_coordinator_is_named_orchestrator(self) -> None:
        self.assertEqual(COORDINATOR_SERVICE_NAME, "coordinator-agent")

    def test_unknown_specialist_agent_name_is_rejected(self) -> None:
        with self.assertRaises(UnknownSpecialistAgentError):
            parse_specialist_agent_name("marketing")

        with self.assertRaises(UnknownSpecialistAgentError):
            build_specialist_run_url("inventory")

    def test_specialist_run_path_is_run(self) -> None:
        self.assertEqual(SPECIALIST_RUN_PATH, "/run")


class SpecialistUrlResolutionTests(unittest.TestCase):
    def test_resolve_specialist_urls_from_environment(self) -> None:
        env = {
            "SALES_AGENT_URL": "http://sales.test:9101",
            "CONTENT_AGENT_URL": "http://content.test:9102",
            "SUPPORT_AGENT_URL": "http://support.test:9103",
        }

        self.assertEqual(
            resolve_specialist_base_url(SpecialistAgentName.SALES, env=env),
            "http://sales.test:9101",
        )
        self.assertEqual(
            resolve_specialist_base_url(SpecialistAgentName.CONTENT, env=env),
            "http://content.test:9102",
        )
        self.assertEqual(
            resolve_specialist_base_url(SpecialistAgentName.SUPPORT, env=env),
            "http://support.test:9103",
        )

    def test_build_run_urls_for_all_specialists(self) -> None:
        env = {
            "SALES_AGENT_URL": "http://sales.test:9101/",
            "CONTENT_AGENT_URL": "http://content.test:9102/",
            "SUPPORT_AGENT_URL": "http://support.test:9103/",
        }

        self.assertEqual(
            build_specialist_run_url(SpecialistAgentName.SALES, env=env),
            "http://sales.test:9101/run",
        )
        self.assertEqual(
            build_specialist_run_url(SpecialistAgentName.CONTENT, env=env),
            "http://content.test:9102/run",
        )
        self.assertEqual(
            build_specialist_run_url(SpecialistAgentName.SUPPORT, env=env),
            "http://support.test:9103/run",
        )

    def test_urls_are_configurable_not_tenant_specific(self) -> None:
        custom_env = {"SALES_AGENT_URL": "http://tenant-neutral-sales:8201"}
        resolved = resolve_specialist_base_url(SpecialistAgentName.SALES, env=custom_env)

        self.assertEqual(resolved, "http://tenant-neutral-sales:8201")
        self.assertNotIn("prestia", resolved.lower())


class CoordinatorClientImportTests(unittest.TestCase):
    def test_coordinator_client_does_not_import_specialist_business_modules(self) -> None:
        forbidden_prefixes = (
            "agents.sales.analysis",
            "agents.sales.action_mapping",
            "agents.content.analysis",
            "agents.content.action_mapping",
            "agents.support.analysis",
            "agents.support.action_mapping",
        )

        for module_name in (topology.__name__, specialist_clients.__name__):
            module = importlib.import_module(module_name)
            loaded = {name for name in module.__dict__ if isinstance(name, str)}
            source_path = Path(module.__file__).resolve()
            source = source_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(source_path))

            imported_modules = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }
            imported_modules.update(
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )

            for forbidden in forbidden_prefixes:
                self.assertNotIn(
                    forbidden,
                    imported_modules,
                    msg=f"{module_name} must not import {forbidden}",
                )
                self.assertNotIn(forbidden, loaded)

    def test_coordinator_topology_module_is_explicit(self) -> None:
        self.assertTrue(hasattr(topology, "assert_star_topology"))
        self.assertTrue(hasattr(topology, "SPECIALIST_PEER_CALL_PATHS"))
        self.assertTrue(hasattr(specialist_clients, "SpecialistAgentClient"))


class SpecialistAgentPeerCallStaticTests(unittest.TestCase):
    def test_specialist_agents_do_not_reference_peer_agent_urls(self) -> None:
        for package in SPECIALIST_AGENT_PACKAGES:
            package_root = REPO_ROOT / "agents" / package
            disallowed_env_vars = OTHER_SPECIALIST_URL_ENV_VARS[package]
            violations: list[str] = []

            for path in package_root.rglob("*.py"):
                if "tests" in path.parts:
                    continue
                source = path.read_text(encoding="utf-8")
                for env_var in disallowed_env_vars:
                    if env_var in source:
                        violations.append(f"{path.relative_to(REPO_ROOT)} references {env_var}")

            self.assertEqual(
                violations,
                [],
                msg=f"{package}-agent must not reference peer specialist URLs",
            )


class WorkflowScaffoldTests(unittest.TestCase):
    def test_workflow_nodes_include_specialist_run_stubs(self) -> None:
        self.assertIn(workflow.WORKFLOW_NODE_FETCH_CONTEXT, workflow.DAILY_REPORT_WORKFLOW_NODES)
        self.assertIn(workflow.WORKFLOW_NODE_RUN_SALES, workflow.DAILY_REPORT_WORKFLOW_NODES)
        self.assertIn(workflow.WORKFLOW_NODE_RUN_CONTENT, workflow.DAILY_REPORT_WORKFLOW_NODES)
        self.assertIn(workflow.WORKFLOW_NODE_RUN_SUPPORT, workflow.DAILY_REPORT_WORKFLOW_NODES)
        self.assertIn(workflow.WORKFLOW_NODE_MERGE, workflow.DAILY_REPORT_WORKFLOW_NODES)
        self.assertIn(workflow.WORKFLOW_NODE_SUBMIT, workflow.DAILY_REPORT_WORKFLOW_NODES)

    def test_specialist_run_nodes_match_star_topology_agents(self) -> None:
        self.assertEqual(len(workflow.SPECIALIST_RUN_NODES), 3)
        self.assertEqual(
            workflow.SPECIALIST_RUN_NODES,
            frozenset(
                {
                    workflow.WORKFLOW_NODE_RUN_SALES,
                    workflow.WORKFLOW_NODE_RUN_CONTENT,
                    workflow.WORKFLOW_NODE_RUN_SUPPORT,
                }
            ),
        )


class SpecialistAgentClientMockedHttpTests(unittest.TestCase):
    def test_prepare_run_request_builds_post_target_and_headers(self) -> None:
        client = SpecialistAgentClient(
            service_token="service-jwt",
            request_id="trace-123",
            base_urls={SpecialistAgentName.SALES: "http://sales.test:9101"},
        )
        payload = {"report_run_id": "run-1", "store_id": "store-1"}

        url, headers, body = client.prepare_run_request(
            SpecialistAgentName.SALES,
            payload,
        )

        self.assertEqual(url, "http://sales.test:9101/run")
        self.assertEqual(headers["Authorization"], "Bearer service-jwt")
        self.assertEqual(headers["X-Request-ID"], "trace-123")
        self.assertEqual(body, payload)

    def test_mocked_post_to_sales_run_endpoint(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["authorization"] = request.headers.get("authorization")
            captured["request_id"] = request.headers.get("x-request-id")
            return httpx.Response(200, json={"status": "ok", "agent": "sales-agent"})

        client = self._build_client(
            handler,
            service_token="sales-jwt",
            request_id="req-sales",
            base_urls={SpecialistAgentName.SALES: "http://sales.test:9101"},
        )

        result = client.run_sales({"report_run_id": "run-sales"})

        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "http://sales.test:9101/run")
        self.assertEqual(captured["authorization"], "Bearer sales-jwt")
        self.assertEqual(captured["request_id"], "req-sales")
        self.assertEqual(result["agent"], "sales-agent")

    def test_mocked_post_to_content_run_endpoint(self) -> None:
        captured_url: str | None = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json={"metadata": {"agent_name": "content-agent"}})

        client = self._build_client(
            handler,
            base_urls={SpecialistAgentName.CONTENT: "http://content.test:9102"},
        )

        client.run_content({"report_run_id": "run-content"})

        self.assertEqual(captured_url, "http://content.test:9102/run")

    def test_mocked_post_to_support_run_endpoint(self) -> None:
        captured_url: str | None = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json={"agent": "support-agent"})

        client = self._build_client(
            handler,
            base_urls={SpecialistAgentName.SUPPORT: "http://support.test:9103"},
        )

        client.run_support({"report_run_id": "run-support"})

        self.assertEqual(captured_url, "http://support.test:9103/run")

    def test_non_2xx_response_raises_http_error(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "specialist failure"})

        client = self._build_client(
            handler,
            base_urls={SpecialistAgentName.SALES: "http://sales.test:9101"},
        )

        with self.assertRaises(SpecialistAgentHTTPError) as ctx:
            client.run_sales({"report_run_id": "run-fail"})

        self.assertEqual(ctx.exception.status_code, 500)

    @patch.dict(
        os.environ,
        {
            "SALES_AGENT_URL": "http://sales-env:8101",
            "CONTENT_AGENT_URL": "http://content-env:8102",
            "SUPPORT_AGENT_URL": "http://support-env:8103",
        },
        clear=False,
    )
    def test_client_resolves_urls_from_environment_when_base_urls_not_set(self) -> None:
        client = SpecialistAgentClient()

        sales_url, _, _ = client.prepare_run_request(
            SpecialistAgentName.SALES,
            {"report_run_id": "run-1"},
        )
        content_url, _, _ = client.prepare_run_request(
            SpecialistAgentName.CONTENT,
            {"report_run_id": "run-1"},
        )
        support_url, _, _ = client.prepare_run_request(
            SpecialistAgentName.SUPPORT,
            {"report_run_id": "run-1"},
        )

        self.assertEqual(sales_url, "http://sales-env:8101/run")
        self.assertEqual(content_url, "http://content-env:8102/run")
        self.assertEqual(support_url, "http://support-env:8103/run")

    def _build_client(
        self,
        handler,
        **kwargs,
    ) -> SpecialistAgentClient:
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        return SpecialistAgentClient(http_client=http_client, **kwargs)


if __name__ == "__main__":
    unittest.main()
