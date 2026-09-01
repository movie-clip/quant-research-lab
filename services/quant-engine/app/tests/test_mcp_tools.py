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
import sys

import pytest
from pydantic import ValidationError

from app.mcp_server.tools import probing, testing
from app.schemas.imports import ImportedPortfolioSnapshot
from app.tests.fixtures import price_rows, price_rows_from_returns


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
        # /engines/drawdown/run is a FLAT route: the snapshot fields go at the
        # top level, not under a "snapshot" key.
        payload = {
            **probing.build_snapshot_impl(
                positions=[{"symbol": "AAPL", "market_value": 1000.0}]
            ),
            "benchmark_symbol": "SPY",
        }
        result = probing.probe_engine_impl(
            "/engines/drawdown/run",
            payload,
            default_rows=price_rows_from_returns(
                [0.01, -0.02, 0.015, -0.01, 0.02] * 12
            ),
        )
        assert result["engine_module"] == "app.services.drawdown_engine"
        assert result["mocked"] is True
        assert result["status"] == 200
        assert result["body"] is not None
        # Correct shape for this route -> no mismatch warning.
        assert result["request_shape"] == "flat"
        assert result["shape_mismatch"] is None

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


class TestProbeShapeClassification:
    """F-1: the probe reports which request-body shape the route expects."""

    @staticmethod
    def _snapshot() -> dict:
        return probing.build_snapshot_impl(
            positions=[{"symbol": "AAPL", "market_value": 1000.0}]
        )

    def test_flat_route_shape_and_model(self) -> None:
        result = probing.probe_engine_impl(
            "/engines/drawdown/run",
            {**self._snapshot(), "benchmark_symbol": "SPY"},
            histories={},
        )
        assert result["request_shape"] == "flat"
        assert result["request_model"] == "DrawdownEngineRequest"
        assert result["shape_mismatch"] is None

    def test_snapshot_wrapped_route_shape_and_model(self) -> None:
        result = probing.probe_engine_impl(
            "/engines/provenance/run",
            {"snapshot": self._snapshot()},
            default_rows=price_rows(40),
        )
        assert result["request_shape"] == "snapshot-wrapped"
        assert result["request_model"] == "ProvenanceRequest"
        assert result["shape_mismatch"] is None

    def test_bare_snapshot_route_shape_and_model(self) -> None:
        result = probing.probe_engine_impl(
            "/engines/diagnostics/run-imported",
            self._snapshot(),
            default_rows=price_rows(40),
        )
        assert result["request_shape"] == "bare-snapshot"
        assert result["request_model"] == "ImportedPortfolioSnapshot"
        assert result["shape_mismatch"] is None

    def test_wrong_shape_payload_warns_without_raising(self) -> None:
        # A snapshot-wrapped payload sent to the FLAT drawdown route: the
        # mismatch is reported, the probe still returns the route's real
        # response, and nothing raises.
        result = probing.probe_engine_impl(
            "/engines/drawdown/run",
            {"snapshot": self._snapshot()},
            histories={},
        )
        assert result["shape_mismatch"] is not None
        assert result["shape_mismatch"]["expected"] == "flat"
        assert result["shape_mismatch"]["supplied"] == "snapshot-wrapped"
        assert result["status"] == 200
        assert result["body"] is not None

    def test_unclassified_route_is_disclosed_not_guessed(self) -> None:
        # Real engine prefix (module derivable -> probe stays offline) but a
        # misspelled action segment, so no APIRoute matches.
        result = probing.probe_engine_impl(
            "/engines/drawdown/bogus", {}, histories={}
        )
        assert result["request_shape"] == "unclassified"
        assert result["request_model"] is None
        assert result["shape_mismatch"] is None
        assert result["status"] == 404


class TestProbeTrustGating:
    """F-1: `ok` means the route answered, not merely `status < 400`."""

    @staticmethod
    def _flat_payload() -> dict:
        return {
            **probing.build_snapshot_impl(
                positions=[{"symbol": "AAPL", "market_value": 1000.0}]
            ),
            "benchmark_symbol": "SPY",
        }

    def test_unavailable_trust_downgrades_ok_despite_2xx(self) -> None:
        # No positions -> drawdown fails closed with trust "unavailable" at a
        # 200 status.
        result = probing.probe_engine_impl(
            "/engines/drawdown/run", {"benchmark_symbol": "SPY"}, histories={}
        )
        assert result["status"] == 200
        assert result["ok"] is False
        assert result["ok_downgraded_by"] == {"trust": "unavailable"}

    def test_non_unavailable_trust_keeps_ok(self) -> None:
        result = probing.probe_engine_impl(
            "/engines/drawdown/run",
            self._flat_payload(),
            default_rows=price_rows_from_returns([0.01, -0.011, 0.009, -0.008] * 15),
        )
        assert result["status"] == 200
        assert result["body"]["trust"] == "synthetic"
        assert result["ok"] is True
        assert result["ok_downgraded_by"] is None

    def test_trust_downgrade_helper_fires_only_on_unavailable(self) -> None:
        assert probing._trust_downgrade({"trust": "unavailable"}) == {
            "trust": "unavailable"
        }
        assert probing._trust_downgrade(
            {"portfolio_return_trust": "unavailable"}
        ) == {"portfolio_return_trust": "unavailable"}
        assert probing._trust_downgrade({"trust": "verified"}) is None
        assert probing._trust_downgrade({"trust": "degraded"}) is None
        assert probing._trust_downgrade({"trust": "withheld"}) is None
        assert probing._trust_downgrade({"trust": "synthetic"}) is None
        # depth-1 only: nested per-row trust does not downgrade
        assert probing._trust_downgrade({"row": {"trust": "unavailable"}}) is None
        assert probing._trust_downgrade(["not", "a", "dict"]) is None


class TestProbeBodyBounding:
    """F-2: long arrays are bounded head/tail; `fields=` filters first."""

    def test_long_array_bounded_head_tail_with_sentinel(self) -> None:
        body, paths = probing._bound_arrays({"series": list(range(100))})
        series = body["series"]
        assert len(series) == 11
        assert series[:5] == [0, 1, 2, 3, 4]
        assert series[-5:] == [95, 96, 97, 98, 99]
        marker = series[5]["__probe_truncated__"]
        assert marker["original_count"] == 100
        assert marker["dropped"] == 90
        assert marker["kept_head"] == 5
        assert marker["kept_tail"] == 5
        assert "probe_engine truncated this array" in marker["note"]
        assert paths == ["series"]

    def test_short_array_is_untouched(self) -> None:
        # exactly HEAD + TAIL + 1 -> not over the limit
        body, paths = probing._bound_arrays({"series": list(range(11))})
        assert body["series"] == list(range(11))
        assert paths == []

    def test_empty_array_and_null_pass_through(self) -> None:
        assert probing._bound_arrays({"series": []}) == ({"series": []}, [])
        assert probing._bound_arrays(None) == (None, [])
        assert probing._bound_arrays([]) == ([], [])

    def test_nested_array_path_is_dotted(self) -> None:
        body, paths = probing._bound_arrays(
            {"episodes": [{"pts": list(range(40))}]}
        )
        assert paths == ["episodes.0.pts"]
        assert len(body["episodes"][0]["pts"]) == 11

    def test_apply_fields_keeps_named_keys_plus_trust(self) -> None:
        body = {"a": 1, "b": 2, "c": 3, "trust": "synthetic", "x_trust": "verified"}
        kept, fields_kept, omitted = probing._apply_fields(body, ["a", "c"])
        assert set(kept) == {"a", "c", "trust", "x_trust"}
        assert kept["a"] == 1 and kept["c"] == 3
        assert fields_kept == ["a", "c", "trust", "x_trust"]
        assert omitted == 1

    def test_apply_fields_on_non_dict_is_a_noop(self) -> None:
        assert probing._apply_fields([1, 2, 3], ["a"]) == ([1, 2, 3], None, None)

    def test_drawdown_probe_over_long_history_is_bounded(self) -> None:
        flat = {
            **probing.build_snapshot_impl(
                positions=[{"symbol": "AAPL", "market_value": 1000.0}]
            ),
            "benchmark_symbol": "SPY",
        }
        long_rows = price_rows_from_returns([0.01, -0.011, 0.009, -0.008] * 150)
        result = probing.probe_engine_impl(
            "/engines/drawdown/run", flat, default_rows=long_rows
        )
        assert result["body"]["trust"] == "synthetic"
        assert "underwater_series" in result["truncation"]
        series = result["body"]["underwater_series"]
        assert len(series) == 11
        assert series[5]["__probe_truncated__"]["original_count"] > 100

    def test_fields_filter_runs_before_truncation(self) -> None:
        flat = {
            **probing.build_snapshot_impl(
                positions=[{"symbol": "AAPL", "market_value": 1000.0}]
            ),
            "benchmark_symbol": "SPY",
        }
        long_rows = price_rows_from_returns([0.01, -0.011, 0.009, -0.008] * 150)
        result = probing.probe_engine_impl(
            "/engines/drawdown/run",
            flat,
            default_rows=long_rows,
            fields=["max_drawdown_pct"],
        )
        assert result["fields_kept"] is not None
        assert "max_drawdown_pct" in result["body"]
        assert "underwater_series" not in result["body"]
        assert result["fields_omitted_count"] >= 1
        # underwater_series was filtered out before truncation ran
        assert result["truncation"] == []
        # trust key is always retained so ok / ok_downgraded_by stay explainable
        assert "trust" in result["body"]


class TestProbeAllowUnmocked:
    """F-3: a non-derivable route fails safe, not live."""

    def test_non_derivable_route_is_refused_by_default(self) -> None:
        result = probing.probe_engine_impl("/health", {})
        assert result["refused"] is True
        assert result["ok"] is False
        assert result["status"] is None
        assert result["body"] is None
        assert "allow_unmocked" in result["reason"]

    def test_allow_unmocked_runs_and_is_disclosed(self) -> None:
        result = probing.probe_engine_impl("/health", {}, allow_unmocked=True)
        assert result["refused"] is False
        assert result["unmocked"] is True
        assert result["mocked"] is False
        assert result["engine_module"] is None
        assert isinstance(result["status"], int)

    def test_typod_explicit_engine_module_raises_loudly(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            probing.probe_engine_impl(
                "/engines/drawdown/run",
                {},
                engine_module="app.services.drawdon_engine",
            )

    def test_typod_route_segment_raises_loudly(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            probing.probe_engine_impl("/engines/drawdon/run", {})

    def test_normal_engine_route_is_unaffected(self) -> None:
        result = probing.probe_engine_impl(
            "/engines/drawdown/run",
            {**probing.build_snapshot_impl(), "benchmark_symbol": "SPY"},
            histories={},
        )
        assert result["refused"] is False
        assert result["mocked"] is True
        assert result["unmocked"] is False


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
            "timeouts",
            "commit_gate",
        }
        assert result["deadcode"]["ok"] is True
        assert result["goldens_drifted"] is False
        assert result["timeouts"] == []

    def test_check_gates_flags_goldens_drift(self, mocker) -> None:
        def fake_run(command, cwd, extra_env=None, *, timeout=None):
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


class TestRunTestsTimeout:
    """F-4: a hung subprocess returns a structured result, it does not hang."""

    def test_run_tests_passes_a_scope_appropriate_timeout(self, mocker) -> None:
        run = mocker.patch.object(
            testing,
            "_run",
            return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        )
        testing.run_tests_impl(scope="full")
        assert run.call_args.kwargs["timeout"] == testing.TIMEOUTS["full"]

        testing.run_tests_impl(scope="backend", path="app/tests/test_x.py")
        assert run.call_args.kwargs["timeout"] == testing.TIMEOUTS["backend"]

        # the full-suite budget is distinct from a single-file iteration and
        # from the per-gate budget check_gates uses
        assert testing.TIMEOUTS["full"] != testing.TIMEOUTS["backend"]
        assert testing.TIMEOUTS["full"] != testing.TIMEOUTS["gate"]

    def test_timeout_result_is_structured_and_does_not_raise(self, mocker) -> None:
        mocker.patch.object(
            testing,
            "_run",
            side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=600),
        )
        result = testing.run_tests_impl(scope="backend")
        assert result["timed_out"] is True
        assert result["ok"] is False
        assert result["exit_code"] is None
        assert result["failures"] == []
        assert result["failure_count"] == 0
        assert result["timeout_seconds"] == testing.TIMEOUTS["backend"]
        assert result["scope"] == "backend"

    def test_timeout_is_distinguishable_from_pass_and_from_failure(
        self, mocker
    ) -> None:
        mocker.patch.object(
            testing,
            "_run",
            return_value=subprocess.CompletedProcess(
                [], 0, stdout="1 passed in 0.10s\n", stderr=""
            ),
        )
        passed = testing.run_tests_impl(scope="backend")
        assert passed["timed_out"] is False and passed["ok"] is True

        mocker.patch.object(
            testing,
            "_run",
            return_value=subprocess.CompletedProcess(
                [],
                1,
                stdout="FAILED app/tests/test_x.py::test_a - boom\n1 failed\n",
                stderr="",
            ),
        )
        failed = testing.run_tests_impl(scope="backend")
        assert failed["timed_out"] is False
        assert failed["ok"] is False
        assert failed["exit_code"] == 1
        assert failed["failure_count"] == 1


class TestGatesTimeout:
    """F-4: check_gates reports a per-gate timeout, keeps the completed gates."""

    def test_gate_and_git_subprocesses_get_their_own_timeouts(self, mocker) -> None:
        run = mocker.patch.object(
            testing,
            "_run",
            return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        )
        testing.check_gates_impl()
        timeouts_used = {call.kwargs.get("timeout") for call in run.call_args_list}
        assert testing.TIMEOUTS["gate"] in timeouts_used
        assert testing.TIMEOUTS["git"] in timeouts_used

    def test_one_gate_timing_out_still_reports_the_others(self, mocker) -> None:
        def fake_run(command, cwd, extra_env=None, *, timeout=None):
            if command[0] == sys.executable:  # the deadcode subprocess
                raise subprocess.TimeoutExpired(cmd="deadcode", timeout=timeout)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        mocker.patch.object(testing, "_run", side_effect=fake_run)
        result = testing.check_gates_impl()
        assert "deadcode" in result["timeouts"]
        assert result["deadcode"]["timed_out"] is True
        # the gates that completed still carry real results
        assert result["typecheck"]["timed_out"] is False
        assert result["goldens_drifted"] is False
        assert result["commit_gate"]["marker_present"] in (True, False)

    def test_fast_gate_run_carries_no_timeout_marker(self, mocker) -> None:
        mocker.patch.object(
            testing,
            "_run",
            return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        )
        result = testing.check_gates_impl()
        assert result["timeouts"] == []
        assert result["deadcode"]["timed_out"] is False
        assert result["typecheck"]["timed_out"] is False


class TestResetGoldensRecordsDiscard:
    """F-5: reset_goldens captures what it is about to discard, before it does."""

    def test_diff_is_captured_before_the_checkout(self, mocker) -> None:
        calls: list[list[str]] = []

        def fake_run(command, cwd, extra_env=None, *, timeout=None):
            calls.append(command)
            if command[:3] == ["git", "diff", "--stat"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout=" file | 2 +-\n", stderr=""
                )
            if command[:2] == ["git", "diff"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout="@@ -1 +1 @@\n-a\n+b\n", stderr=""
                )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        mocker.patch.object(testing, "_run", side_effect=fake_run)
        result = testing.reset_goldens_impl()

        assert calls[0][:3] == ["git", "diff", "--stat"]
        assert calls[1][:2] == ["git", "diff"]
        assert calls[2][:3] == ["git", "checkout", "--"]
        assert result["diff_stat"] == "file | 2 +-"
        assert "+b" in result["diff"]
        assert result["discarded"] is True
        assert result["ok"] is True

    def test_checkout_failure_still_carries_the_capture(self, mocker) -> None:
        def fake_run(command, cwd, extra_env=None, *, timeout=None):
            if command[:3] == ["git", "diff", "--stat"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout=" f | 1 +\n", stderr=""
                )
            if command[:2] == ["git", "diff"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout="patch text\n", stderr=""
                )
            return subprocess.CompletedProcess(
                command, 1, stdout="", stderr="error: pathspec"
            )

        mocker.patch.object(testing, "_run", side_effect=fake_run)
        result = testing.reset_goldens_impl()

        assert result["ok"] is False
        assert result["stderr"] == "error: pathspec"
        assert result["diff_stat"] == "f | 1 +"
        assert "patch text" in result["diff"]
        assert result["discarded"] is True

    def test_no_drift_reports_nothing_discarded(self, mocker) -> None:
        mocker.patch.object(
            testing,
            "_run",
            return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        )
        result = testing.reset_goldens_impl()
        assert result["discarded"] is False
        assert result["diff_stat"] == ""
        assert result["diff"] == ""
        assert result["ok"] is True
