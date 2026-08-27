"""Coverage for the MCP tool implementations.

These call the `*_impl` functions directly -- no MCP transport, no server
process. That is deliberate: the transport cannot be exercised from inside a
session (an MCP server is connected at session start), so all the behaviour
worth verifying lives in plain functions that pytest can reach.

The one thing these tests cannot cover is whether the server actually starts and
handshakes. That is a human check: see `app/mcp_server/server.py`.
"""

from __future__ import annotations

import subprocess

import pytest
from pydantic import ValidationError

from app.mcp_server.tools import probing, testing
from app.schemas.imports import ImportedPortfolioSnapshot
from app.tests.fixtures import price_rows_from_returns


class TestEngineModuleDerivation:
    @pytest.mark.parametrize(
        ("route", "expected"),
        [
            ("/engines/drawdown/run", "app.services.drawdown_engine"),
            ("/engines/distribution/run", "app.services.distribution_engine"),
            ("/engines/stress/run", "app.services.stress_engine"),
            ("/engines/exposure/run", "app.services.exposure_engine"),
            ("/engines/drift/run", "app.services.drift_engine"),
            ("/engines/attribution/run", "app.services.attribution_engine"),
            ("/engines/correlation/run", "app.services.correlation_engine"),
            ("/engines/provenance/run", "app.services.provenance_engine"),
            ("/engines/diagnostics/run", "app.services.diagnostics_engine"),
            # hyphenated prefixes must become underscores
            ("/engines/currency-risk/run", "app.services.currency_risk_engine"),
            (
                "/engines/dashboard-history/run",
                "app.services.dashboard_history_engine",
            ),
        ],
    )
    def test_derives_engine_module_from_route(self, route: str, expected: str) -> None:
        assert probing.engine_module_for(route) == expected

    @pytest.mark.parametrize(
        "route",
        ["/portfolios/import", "/cache/clear", "/market-data/history", "/health"],
    )
    def test_non_engine_routes_derive_nothing(self, route: str) -> None:
        assert probing.engine_module_for(route) is None

    def test_every_derived_module_is_importable(self) -> None:
        """Guards against the derivation drifting away from the real layout."""
        import importlib

        for route in ("/engines/drawdown/run", "/engines/currency-risk/run"):
            module = probing.engine_module_for(route)
            assert module is not None
            importlib.import_module(module)


class TestBuildSnapshot:
    def test_empty_snapshot_validates_against_the_schema(self) -> None:
        ImportedPortfolioSnapshot.model_validate(probing.build_snapshot_impl())

    def test_shorthand_positions_validate(self) -> None:
        payload = probing.build_snapshot_impl(
            positions=[
                {"symbol": "AAPL", "market_value": 500.0},
                {"symbol": "SPY", "market_value": 1500.0},
            ]
        )
        snapshot = ImportedPortfolioSnapshot.model_validate(payload)
        assert [p.symbol for p in snapshot.positions] == ["AAPL", "SPY"]

    def test_statement_overrides_reach_the_payload(self) -> None:
        payload = probing.build_snapshot_impl(
            statement_overrides={"importer": "freedom24"}
        )
        assert payload["statement"]["importer"] == "freedom24"
        # overriding one field must not drop the others
        assert payload["statement"]["detected_format"] == "ib_flex_2023"

    def test_invalid_position_still_fails_validation(self) -> None:
        """The builder is a convenience, not a validator -- garbage must not pass."""
        payload = probing.build_snapshot_impl(positions=[{"not_a_symbol": 1}])
        with pytest.raises(ValidationError):
            ImportedPortfolioSnapshot.model_validate(payload)


class TestProbeEngine:
    def test_drawdown_route_returns_a_response_with_mocked_market_data(self) -> None:
        payload = {
            "snapshot": probing.build_snapshot_impl(
                positions=[{"symbol": "AAPL", "market_value": 1000.0}]
            )
        }
        result = probing.probe_engine_impl(
            "/engines/drawdown/run",
            payload,
            histories={
                "AAPL": price_rows_from_returns([0.01, -0.05, 0.02, -0.03, 0.04])
            },
        )
        assert result["engine_module"] == "app.services.drawdown_engine"
        assert result["mocked"] is True
        # The route may reject the payload shape; what this pins is that the
        # probe reached the app and came back with a real HTTP response rather
        # than raising, and that no live network was touched.
        assert isinstance(result["status"], int)
        assert result["body"] is not None

    def test_patches_are_unwound_after_the_probe(self) -> None:
        import app.services.drawdown_engine as engine

        before = engine.MarketDataService
        probing.probe_engine_impl(
            "/engines/drawdown/run",
            {"snapshot": probing.build_snapshot_impl()},
            histories={},
        )
        assert engine.MarketDataService is before

    def test_explicit_engine_module_overrides_the_derivation(self) -> None:
        result = probing.probe_engine_impl(
            "/health",
            {},
            engine_module="app.services.drawdown_engine",
        )
        assert result["engine_module"] == "app.services.drawdown_engine"


class TestRunTestsParsing:
    def test_rejects_an_unknown_scope_without_running_anything(self) -> None:
        result = testing.run_tests_impl(scope="sideways")
        assert result["ok"] is False
        assert "unknown scope" in result["error"]
        assert set(result["valid_scopes"]) == set(testing.VALID_SCOPES)

    def test_parses_pytest_failure_lines(self) -> None:
        output = (
            "..F..\n"
            "FAILED app/tests/test_drawdown_engine.py::test_underwater_curve - "
            "AssertionError: assert 0.1 == 0.2\n"
            "ERROR app/tests/test_stress_engine.py::test_shock - fixture 'x' not found\n"
            "2 failed, 3 passed in 1.20s\n"
        )
        failures = testing._parse_failures("backend", output)
        assert [f["test"] for f in failures] == ["test_underwater_curve", "test_shock"]
        assert failures[0]["file"] == "app/tests/test_drawdown_engine.py"
        assert "assert 0.1 == 0.2" in failures[0]["message"]

    def test_parses_tsc_errors_with_position(self) -> None:
        output = (
            "src/features/portfolio/Card.tsx(12,3): error TS2345: "
            "Argument of type 'string' is not assignable.\n"
        )
        errors = testing._parse_failures("typecheck", output)
        assert errors == [
            {
                "file": "src/features/portfolio/Card.tsx",
                "line": 12,
                "column": 3,
                "message": (
                    "error TS2345: Argument of type 'string' is not assignable."
                ),
            }
        ]

    def test_failure_list_is_capped(self) -> None:
        output = "\n".join(
            f"FAILED app/tests/test_x.py::test_{i} - boom" for i in range(60)
        )
        failures = testing._parse_failures("backend", output)
        assert len(failures) == testing.MAX_FAILURES

    def test_tail_is_bounded_and_drops_blank_lines(self) -> None:
        tail = testing._tail("\n".join(str(i) for i in range(100)) + "\n\n\n")
        assert len(tail) == testing.TAIL_LINES
        assert tail[-1] == "99"

    def test_backend_scope_skips_the_golden_freshness_check(self, mocker) -> None:
        run = mocker.patch.object(
            testing,
            "_run",
            return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        )
        testing.run_tests_impl(scope="backend", path="app/tests/test_x.py", k="foo")
        command = run.call_args[0][0]
        assert command[-2:] == ["-k", "foo"]
        assert "app/tests/test_x.py" in command
        assert run.call_args[0][2] == {"SKIP_GOLDEN_FRESHNESS_CHECK": "1"}

    def test_full_scope_does_not_skip_the_freshness_check(self, mocker) -> None:
        run = mocker.patch.object(
            testing,
            "_run",
            return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        )
        testing.run_tests_impl(scope="full")
        assert run.call_args[0][2] is None


class TestGates:
    def test_check_gates_reports_every_gate(self, mocker) -> None:
        mocker.patch.object(
            testing,
            "_run",
            return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        )
        result = testing.check_gates_impl()
        assert set(result) == {
            "deadcode",
            "typecheck",
            "goldens_drifted",
            "commit_gate",
        }
        assert result["deadcode"]["ok"] is True
        assert result["goldens_drifted"] is False

    def test_check_gates_flags_goldens_drift(self, mocker) -> None:
        def fake_run(command, cwd, extra_env=None):
            stdout = " M " + testing.GOLDENS_PATH if command[0] == "git" else ""
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

        mocker.patch.object(testing, "_run", side_effect=fake_run)
        assert testing.check_gates_impl()["goldens_drifted"] is True

    def test_reset_goldens_checks_out_the_generated_file(self, mocker) -> None:
        run = mocker.patch.object(
            testing,
            "_run",
            return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        )
        result = testing.reset_goldens_impl()
        assert run.call_args[0][0] == ["git", "checkout", "--", testing.GOLDENS_PATH]
        assert result["ok"] is True
