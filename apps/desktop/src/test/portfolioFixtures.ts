import type {
  DashboardHistoryInvestorEconomicsPartialUnlock,
  DashboardHistoryRunMetadata,
  DiagnosticsEngineResponse,
  DiagnosticsRunMetadata,
  ExposureEngineResponse,
  ImportedBootstrapResponse,
  ImportedBaselineSource,
  ImportedDashboardSource,
  ImportedHistoryContext,
  PortfolioProofBucketEvidence,
  PortfolioProofMetadata,
  PortfolioRiskSummary,
  ReturnBasisEvidence,
} from '../features/portfolio/types'
import {
  ff2026ImportedDashboardGoldenFixture,
  ib2026DashboardGolden,
  ib2026ImportedDashboardGoldenFixture,
} from './dashboardGoldens'

type DashboardGoldenFixture = ImportedDashboardSource & {
  risk_summary: PortfolioRiskSummary
}

function createUnavailableReturnBasisEvidence(disqualifiers: string[]): ReturnBasisEvidence {
  return {
    verification_status: 'unavailable',
    economic_basis: 'unavailable',
    construction_method: 'unknown',
    disqualifiers,
    fallbacks_used: [],
    source_price_field: null,
    scope: {},
  }
}

function createProofBucketFixture(overrides: Partial<PortfolioProofBucketEvidence>): PortfolioProofBucketEvidence {
  return {
    status: 'unavailable',
    positive_evidence: [],
    negative_evidence: [],
    disqualifiers: [],
    hard_disqualifiers: [],
    witnesses: [],
    ...overrides,
  }
}

function createPortfolioProofFixture(status: 'withheld' | 'unavailable' = 'withheld'): PortfolioProofMetadata {
  if (status === 'unavailable') {
    const unavailableScope = {
      account_id: null,
      base_currency: null,
      history_source: 'unavailable',
      valuation_window_start: null,
      valuation_window_end: null,
      valuation_date_count: 0,
      statement_window_start: null,
      statement_window_end: null,
      statement_window_count: 0,
    }
    const unavailableBucket = createProofBucketFixture({
      status: 'disqualified',
      negative_evidence: ['portfolio_history_unavailable'],
      disqualifiers: ['portfolio_history_unavailable'],
      hard_disqualifiers: ['portfolio_history_unavailable'],
    })
    const missingProofBuckets = [
      'boundary_hardening',
      'capital_boundary_proof',
      'corporate_action_proof',
      'fx_proof',
      'investor_economics_proof',
      'opening_state_admission',
      'return_basis_metadata',
      'valuation_basis_separation',
    ]
    return {
      proof_system: 'portfolio_verified_total_return_v1',
      portfolio_path: 'unavailable' as const,
      replay_status: 'replay_unavailable' as const,
      opening_state_status: 'opening_state_unavailable' as const,
      verification_status: 'unavailable' as const,
      output_status: 'unavailable' as const,
      verified_total_return_emitted: false,
      benchmark_proof_independent: true,
      disqualifiers: ['portfolio_history_unavailable'],
      hard_disqualifiers: ['portfolio_history_unavailable'],
      preparation: {
        readiness_status: 'not_applicable',
        all_prerequisite_buckets_supported: false,
        exact_slice_target: {
          account_set: [],
          base_currency: null,
          valuation_window: {
            start_date: null,
            end_date: null,
            count: 0,
          },
          statement_window: {
            start_date: null,
            end_date: null,
            count: 0,
          },
          opening_state_anchor: {
            required_anchor_date: null,
            observed_anchor_date: null,
            status: 'unavailable',
          },
          fx_scope: {
            translation_case: 'unavailable',
            base_currency: null,
            observed_currencies: [],
            required_pairs: [],
            required_pair_dates: [],
          },
          corporate_action_scope: {
            scope: 'broker_scope_unproven',
            scope_start_date: null,
            scope_end_date: null,
            statement_window_count: 0,
            positive_proof_classes: [],
            unproven_disqualifying_classes: ['portfolio_history_unavailable'],
          },
        },
        readiness_gaps: [
          {
            code: 'portfolio_history_unavailable',
            bucket: 'portfolio_admission',
            provenance_buckets: ['portfolio_history'],
            gap_type: 'missing',
          },
        ],
        policy_blockers: [],
      },
      admission: {
        status: 'not_applicable' as const,
        readiness_status: 'not_applicable' as const,
        scope: unavailableScope,
        blocking_reasons: [
          {
            code: 'portfolio_history_unavailable',
            bucket: 'portfolio_admission',
            provenance_bucket: 'portfolio_history',
            reason_type: 'missing' as const,
          },
        ],
        missing_proof_buckets: missingProofBuckets,
        bucket_decisions: [
          'return_basis_metadata',
          'capital_boundary_proof',
          'valuation_basis_separation',
          'boundary_hardening',
          'opening_state_admission',
          'fx_proof',
          'corporate_action_proof',
          'investor_economics_proof',
          ].map((bucket) => ({
          bucket,
          status: 'not_applicable' as const,
          blocks_admission: true,
          provenance_buckets: [bucket],
          blocking_reasons: ['portfolio_history_unavailable'],
          scope: unavailableScope,
        })),
      },
      evidence: {
        opening_state_basis: unavailableBucket,
        valuation_basis: unavailableBucket,
        cash_flow_basis: unavailableBucket,
        fx_basis: unavailableBucket,
        corporate_action_basis: {
          ...unavailableBucket,
          policy: {
            scope: 'broker_scope_unproven' as const,
            cash_dividend_coverage_status: 'cash_dividend_coverage_unproven' as const,
            cash_dividend_observation_status: 'cash_dividend_observation_unproven' as const,
            non_dividend_status: 'non_dividend_corporate_actions_unproven_and_disqualifying' as const,
            scope_start_date: null,
            scope_end_date: null,
            statement_window_count: 0,
          },
        },
        terminal_reconciliation_basis: unavailableBucket,
        calendar_coverage_basis: unavailableBucket,
        investor_economics_proof: {
          ...createProofBucketFixture({
            status: 'unavailable',
            negative_evidence: ['portfolio_history_unavailable'],
            disqualifiers: ['portfolio_history_unavailable'],
            hard_disqualifiers: ['portfolio_history_unavailable'],
          }),
          claim_id: 'portfolio_investor_economics_proof_v1',
        claim: 'Investor-economics-grade exact-slice proof for portfolio returns.',
        decision: 'not_applicable',
        preparation_status: 'not_applicable',
        required_inputs: missingProofBuckets,
        blocking_reasons: ['portfolio_history_unavailable'],
        missing_proof_buckets: missingProofBuckets,
        scope_mismatches: [],
        scope: unavailableScope,
      },
      },
    }
  }

  const withheldScope = {
    account_id: 'U8516450',
    base_currency: 'USD',
    history_source: 'synthetic_snapshot_history',
    valuation_window_start: '2025-01-02',
    valuation_window_end: '2025-03-03',
    valuation_date_count: 2,
    statement_window_start: null,
    statement_window_end: null,
    statement_window_count: 0,
  }
  const withheldMissingProofBuckets = [
    'boundary_hardening',
    'capital_boundary_proof',
    'corporate_action_proof',
    'investor_economics_proof',
    'opening_state_admission',
    'return_basis_metadata',
    'valuation_basis_separation',
  ]

  return {
    proof_system: 'portfolio_verified_total_return_v1',
    portfolio_path: 'withheld' as const,
    replay_status: 'replay_usable' as const,
    opening_state_status: 'opening_state_unverified' as const,
    verification_status: 'unverified' as const,
    output_status: 'withheld' as const,
    verified_total_return_emitted: false,
    benchmark_proof_independent: true,
    disqualifiers: [
      'calendar_coverage_not_broker_proven',
      'cash_flow_classification_incomplete',
      'corporate_action_proof_missing',
      'portfolio_verified_total_return_withheld',
      'raw_price_used_for_valuation',
      'synthetic_snapshot_history',
    ],
    hard_disqualifiers: [
      'calendar_coverage_not_broker_proven',
      'corporate_action_proof_missing',
      'raw_price_used_for_valuation',
      'synthetic_snapshot_history',
    ],
    preparation: {
      readiness_status: 'exact_slice_prerequisites_incomplete',
      all_prerequisite_buckets_supported: false,
      exact_slice_target: {
        account_set: ['U8516450'],
        base_currency: 'USD',
        valuation_window: {
          start_date: '2025-01-02',
          end_date: '2025-03-03',
          count: 2,
        },
        statement_window: {
          start_date: null,
          end_date: null,
          count: 0,
        },
        opening_state_anchor: {
          required_anchor_date: '2025-01-02',
          observed_anchor_date: null,
          status: 'synthetic_snapshot_opening_state',
        },
        fx_scope: {
          translation_case: 'base_currency_only',
          base_currency: 'USD',
          observed_currencies: ['USD'],
          required_pairs: [],
          required_pair_dates: [],
        },
        corporate_action_scope: {
          scope: 'broker_scope_unproven',
          scope_start_date: null,
          scope_end_date: null,
          statement_window_count: 0,
          positive_proof_classes: [],
          unproven_disqualifying_classes: ['non_dividend_corporate_actions'],
        },
      },
      readiness_gaps: [
        {
          code: 'raw_price_used_for_valuation',
          bucket: 'return_basis_metadata',
          provenance_buckets: ['valuation_basis'],
          gap_type: 'blocking',
        },
        {
          code: 'synthetic_snapshot_history',
          bucket: 'capital_boundary_proof',
          provenance_buckets: ['cash_flow_basis'],
          gap_type: 'blocking',
        },
        {
          code: 'calendar_coverage_not_broker_proven',
          bucket: 'boundary_hardening',
          provenance_buckets: ['calendar_coverage_basis'],
          gap_type: 'blocking',
        },
        {
          code: 'statement_window_scope_unproven_for_portfolio_slice',
          bucket: 'boundary_hardening',
          provenance_buckets: ['calendar_coverage_basis'],
          gap_type: 'scope_mismatch',
        },
        {
          code: 'synthetic_snapshot_opening_state',
          bucket: 'opening_state_admission',
          provenance_buckets: ['opening_state_basis'],
          gap_type: 'blocking',
        },
        {
          code: 'corporate_action_proof_missing',
          bucket: 'corporate_action_proof',
          provenance_buckets: ['corporate_action_basis'],
          gap_type: 'blocking',
        },
      ],
      policy_blockers: [
        {
          code: 'portfolio_verified_total_return_withheld',
          bucket: 'investor_economics_proof',
          provenance_buckets: ['portfolio_proof_admission_governor_v1'],
          gap_type: 'policy_withheld',
        },
      ],
    },
    admission: {
      status: 'rejected' as const,
      readiness_status: 'exact_slice_prerequisites_incomplete' as const,
      scope: withheldScope,
      blocking_reasons: [
        { code: 'raw_price_used_for_valuation', bucket: 'return_basis_metadata', provenance_bucket: 'valuation_basis', reason_type: 'blocking' as const },
        { code: 'synthetic_snapshot_history', bucket: 'return_basis_metadata', provenance_bucket: 'valuation_basis', reason_type: 'blocking' as const },
        { code: 'synthetic_snapshot_history', bucket: 'capital_boundary_proof', provenance_bucket: 'cash_flow_basis', reason_type: 'blocking' as const },
        { code: 'raw_price_used_for_valuation', bucket: 'valuation_basis_separation', provenance_bucket: 'valuation_basis', reason_type: 'blocking' as const },
        { code: 'synthetic_snapshot_history', bucket: 'valuation_basis_separation', provenance_bucket: 'valuation_basis', reason_type: 'blocking' as const },
        { code: 'calendar_coverage_not_broker_proven', bucket: 'boundary_hardening', provenance_bucket: 'calendar_coverage_basis', reason_type: 'blocking' as const },
        { code: 'statement_window_scope_unproven_for_portfolio_slice', bucket: 'boundary_hardening', provenance_bucket: 'calendar_coverage_basis', reason_type: 'scope_mismatch' as const },
        { code: 'synthetic_snapshot_opening_state', bucket: 'opening_state_admission', provenance_bucket: 'opening_state_basis', reason_type: 'blocking' as const },
        { code: 'corporate_action_proof_missing', bucket: 'corporate_action_proof', provenance_bucket: 'corporate_action_basis', reason_type: 'blocking' as const },
        { code: 'corporate_action_scope_unproven_for_portfolio_slice', bucket: 'corporate_action_proof', provenance_bucket: 'corporate_action_basis', reason_type: 'scope_mismatch' as const },
        { code: 'missing_investor_economics_proof_bucket', bucket: 'investor_economics_proof', provenance_bucket: 'portfolio_proof_admission_governor_v1', reason_type: 'missing' as const },
        { code: 'portfolio_verified_total_return_withheld', bucket: 'investor_economics_proof', provenance_bucket: 'portfolio_proof_admission_governor_v1', reason_type: 'withheld' as const },
      ],
      missing_proof_buckets: withheldMissingProofBuckets,
      bucket_decisions: [
        {
          bucket: 'return_basis_metadata',
          status: 'rejected' as const,
          blocks_admission: true,
          provenance_buckets: ['valuation_basis'],
          blocking_reasons: ['raw_price_used_for_valuation', 'synthetic_snapshot_history'],
          scope: {
            base_currency: 'USD', history_source: 'synthetic_snapshot_history', valuation_window_start: '2025-01-02', valuation_window_end: '2025-03-03', valuation_date_count: 2,
          },
        },
        {
          bucket: 'capital_boundary_proof',
          status: 'rejected' as const,
          blocks_admission: true,
          provenance_buckets: ['cash_flow_basis'],
          blocking_reasons: ['synthetic_snapshot_history'],
          scope: {
            account_id: 'U8516450', base_currency: 'USD', history_source: 'synthetic_snapshot_history', valuation_window_start: '2025-01-02', valuation_window_end: '2025-03-03',
          },
        },
        {
          bucket: 'valuation_basis_separation',
          status: 'rejected' as const,
          blocks_admission: true,
          provenance_buckets: ['valuation_basis'],
          blocking_reasons: ['raw_price_used_for_valuation', 'synthetic_snapshot_history'],
          scope: {
            base_currency: 'USD', history_source: 'synthetic_snapshot_history', valuation_window_start: '2025-01-02', valuation_window_end: '2025-03-03', valuation_date_count: 2,
          },
        },
        {
          bucket: 'boundary_hardening',
          status: 'rejected' as const,
          blocks_admission: true,
          provenance_buckets: ['calendar_coverage_basis', 'terminal_reconciliation_basis'],
          blocking_reasons: ['calendar_coverage_not_broker_proven', 'statement_window_scope_unproven_for_portfolio_slice'],
          scope: {
            account_id: 'U8516450', base_currency: 'USD', valuation_window_start: '2025-01-02', valuation_window_end: '2025-03-03', statement_window_start: null, statement_window_end: null, statement_window_count: 0,
          },
        },
        {
          bucket: 'opening_state_admission',
          status: 'rejected' as const,
          blocks_admission: true,
          provenance_buckets: ['opening_state_basis'],
          blocking_reasons: ['synthetic_snapshot_opening_state'],
          scope: {
            account_id: 'U8516450', base_currency: 'USD', history_source: 'synthetic_snapshot_history', slice_start: '2025-01-02',
          },
        },
        {
          bucket: 'fx_proof',
          status: 'withheld' as const,
          blocks_admission: false,
          provenance_buckets: ['fx_basis'],
          blocking_reasons: [],
          scope: {
            base_currency: 'USD', valuation_window_start: '2025-01-02', valuation_window_end: '2025-03-03', valuation_date_count: 2,
          },
        },
        {
          bucket: 'corporate_action_proof',
          status: 'rejected' as const,
          blocks_admission: true,
          provenance_buckets: ['corporate_action_basis'],
          blocking_reasons: ['corporate_action_proof_missing', 'corporate_action_scope_unproven_for_portfolio_slice'],
          scope: {
            base_currency: 'USD', valuation_window_start: '2025-01-02', valuation_window_end: '2025-03-03', statement_window_start: null, statement_window_end: null, statement_window_count: 0,
          },
        },
        {
          bucket: 'investor_economics_proof',
          status: 'withheld' as const,
          blocks_admission: true,
          provenance_buckets: ['portfolio_proof_admission_governor_v1'],
          blocking_reasons: ['missing_investor_economics_proof_bucket', 'portfolio_verified_total_return_withheld'],
          scope: {
            account_id: 'U8516450', base_currency: 'USD', history_source: 'synthetic_snapshot_history', valuation_window_start: '2025-01-02', valuation_window_end: '2025-03-03', valuation_date_count: 2, statement_window_start: null, statement_window_end: null, statement_window_count: 0,
          },
        },
      ],
    },
    evidence: {
      opening_state_basis: {
        status: 'disqualified' as const,
        positive_evidence: ['broker_ledger_entries_available'],
        negative_evidence: ['opening_state_derived_from_current_snapshot'],
        disqualifiers: ['synthetic_snapshot_opening_state'],
        hard_disqualifiers: ['synthetic_snapshot_opening_state'],
        witnesses: [
          {
            label: 'opening_cash_state',
            status: 'unknown_inferred',
            evidence: ['synthetic_snapshot_history_has_no_broker_opening_cash_state'],
            counts: {},
          },
          {
            label: 'opening_positions_state',
            status: 'unknown_inferred',
            evidence: ['opening_positions_derived_from_current_snapshot'],
            counts: {},
          },
        ],
      },
      valuation_basis: {
        status: 'disqualified' as const,
        positive_evidence: ['valuation_dates_available', 'position_price_histories_loaded'],
        negative_evidence: ['vendor_raw_price_used_for_valuation', 'valuation_path_is_synthetic_snapshot_history'],
        disqualifiers: ['raw_price_used_for_valuation', 'synthetic_snapshot_history'],
        hard_disqualifiers: ['raw_price_used_for_valuation', 'synthetic_snapshot_history'],
        witnesses: [],
      },
      cash_flow_basis: {
        status: 'disqualified' as const,
        positive_evidence: ['broker_ledger_entries_available'],
        negative_evidence: ['synthetic_snapshot_history_has_no_external_flow_replay'],
        disqualifiers: ['synthetic_snapshot_history'],
        hard_disqualifiers: ['synthetic_snapshot_history'],
        witnesses: [
          {
            label: 'cash_flow_classification',
            status: 'not_observed',
            evidence: ['no_broker_proven_external_capital_flow_entries_observed'],
            counts: { external_capital_flow: 0 },
          },
          {
            label: 'internal_trading_flow_classification',
            status: 'not_observed',
            evidence: ['no_internal_trading_cash_flows_observed'],
            counts: { internal_trading_flow: 0 },
          },
          {
            label: 'broker_explicit_income_expense_classification',
            status: 'not_observed',
            evidence: ['no_broker_explicit_income_or_expense_cash_flows_observed'],
            counts: {
              broker_explicit_dividend: 0,
              broker_explicit_interest: 0,
              broker_explicit_fee: 0,
              broker_explicit_tax: 0,
            },
          },
          {
            label: 'unknown_cash_flow_classification',
            status: 'none_observed',
            evidence: ['no_unknown_cash_flow_entries_observed'],
            counts: { unknown: 0 },
          },
        ],
      },
      fx_basis: {
        status: 'supported' as const,
        positive_evidence: ['all_observed_statement_currencies_match_base_currency'],
        negative_evidence: [],
        disqualifiers: [],
        hard_disqualifiers: [],
        witnesses: [],
      },
      corporate_action_basis: {
        status: 'disqualified' as const,
        policy: {
          scope: 'broker_scope_unproven' as const,
          cash_dividend_coverage_status: 'cash_dividend_coverage_unproven' as const,
          cash_dividend_observation_status: 'cash_dividend_observation_unproven' as const,
          non_dividend_status: 'non_dividend_corporate_actions_unproven_and_disqualifying' as const,
          scope_start_date: null,
          scope_end_date: null,
          statement_window_count: 0,
        },
        positive_evidence: [],
        negative_evidence: ['corporate_action_proof_not_available'],
        disqualifiers: ['corporate_action_proof_missing'],
        hard_disqualifiers: ['corporate_action_proof_missing'],
        witnesses: [],
      },
      terminal_reconciliation_basis: {
        status: 'supported' as const,
        positive_evidence: ['terminal_force_reconciliation_not_present'],
        negative_evidence: [],
        disqualifiers: [],
        hard_disqualifiers: [],
        witnesses: [],
      },
      calendar_coverage_basis: {
        status: 'disqualified' as const,
        positive_evidence: ['valuation_window_dates_available', 'valuation_dates_are_sorted_and_unique'],
        negative_evidence: ['valuation_calendar_is_derived_from_benchmark_history'],
        disqualifiers: ['calendar_coverage_not_broker_proven'],
        hard_disqualifiers: ['calendar_coverage_not_broker_proven'],
        witnesses: [],
      },
      investor_economics_proof: {
        ...createProofBucketFixture({
          status: 'unavailable',
          negative_evidence: ['portfolio_verified_total_return_withheld'],
          disqualifiers: ['missing_investor_economics_proof_bucket', 'portfolio_verified_total_return_withheld'],
        }),
        claim_id: 'portfolio_investor_economics_proof_v1',
        claim: 'Investor-economics-grade exact-slice proof for portfolio returns.',
        decision: 'withheld',
        preparation_status: 'exact_slice_prerequisites_incomplete',
        required_inputs: [
          'return_basis_metadata',
          'capital_boundary_proof',
          'valuation_basis_separation',
          'boundary_hardening',
          'opening_state_admission',
          'fx_proof',
          'corporate_action_proof',
        ],
        blocking_reasons: ['missing_investor_economics_proof_bucket', 'portfolio_verified_total_return_withheld'],
        missing_proof_buckets: withheldMissingProofBuckets,
        scope_mismatches: ['corporate_action_scope_unproven_for_portfolio_slice', 'statement_window_scope_unproven_for_portfolio_slice'],
        scope: withheldScope,
      },
    },
  }
}

export function createDashboardHistoryRunMetadataFixture(status: 'default' | 'unavailable' = 'default'): DashboardHistoryRunMetadata {
  const investorEconomicsPartialUnlock: DashboardHistoryInvestorEconomicsPartialUnlock = {
    mode: 'allowlisted_exact_slice_scalars_only',
    exact_slice_scalar_allowlist: [
      {
        field: 'range_metrics[*].summary.time_weighted_return_pct',
        unlock_condition: 'identical_admitted_exact_slice_only',
        runtime_enabled: true,
      },
      {
        field: 'range_metrics[*].summary.benchmark_return_pct',
        unlock_condition: 'identical_admitted_exact_slice_with_independently_verified_benchmark_total_return_only',
        runtime_enabled: true,
      },
      {
        field: 'range_metrics[*].summary.excess_return_pct',
        unlock_condition: 'identical_admitted_exact_slice_pair_only',
        runtime_enabled: false,
      },
    ],
    client_derivation_rule: 'server_side_scalar_only_no_daily_series_subtraction_equivalence',
    withheld_families: [
      'benchmark_relative_series',
      'benchmark_relative_path_derived_outputs',
      'drawdown_family',
      'rebucketed_window_summaries',
      'rewindowed_range_summaries',
      'diagnostics_benchmark_relative_outputs',
      'replay_benchmark_relative_outputs',
      'strategy_lab_benchmark_relative_outputs',
    ],
  }

  if (status === 'unavailable') {
    return {
      history_id: 'dashboard_history_engine_v1',
      methodology_id: 'dashboard_history_methodology_v1',
      source_status: {
        performance_history: 'unavailable',
        monthly_returns: 'unavailable',
        benchmark_history: 'unavailable',
      },
      section_trust: {
        portfolio_path: 'unavailable',
        benchmark_path: 'unavailable',
        monthly_returns_path: 'unavailable',
      },
      return_basis_contract: {
        portfolio_path: 'unavailable',
        benchmark_path: 'unavailable',
      },
      return_basis_evidence: {
        portfolio_path: createUnavailableReturnBasisEvidence(['missing_history_rows']),
        benchmark_path: createUnavailableReturnBasisEvidence(['missing_history_rows']),
      },
      portfolio_proof: createPortfolioProofFixture('unavailable'),
      investor_economics_status: {
        status: 'withheld',
        reason: 'withheld_unverified_total_return_equivalence',
      },
      investor_economics_partial_unlock: investorEconomicsPartialUnlock,
      reproducibility: {
        input_imported_at: '2026-04-10T00:00:00Z',
        snapshot_as_of_date: null,
        history_start_date: null,
        history_end_date: null,
        benchmark_symbol: 'SPY',
        dataset_version: 'market_data_service_v1',
      },
    }
  }

  return {
    history_id: 'dashboard_history_engine_v1',
    methodology_id: 'dashboard_history_methodology_v1',
    source_status: {
      performance_history: 'live',
      monthly_returns: 'live',
      benchmark_history: 'live_market_data_unverified_return_basis',
    },
    section_trust: {
      portfolio_path: 'imported_replay',
      benchmark_path: 'degraded_unverified_return_basis',
      monthly_returns_path: 'imported_replay',
    },
    return_basis_contract: {
      portfolio_path: 'unavailable',
      benchmark_path: 'price_return_only',
    },
    return_basis_evidence: {
      portfolio_path: {
        verification_status: 'unverified',
        economic_basis: 'price_return_only',
        construction_method: 'raw_close',
        disqualifiers: ['missing_adjusted_close_series', 'missing_total_return_reconstruction'],
        fallbacks_used: [],
        source_price_field: 'price',
      },
      benchmark_path: {
        verification_status: 'unverified',
        economic_basis: 'price_return_only',
        construction_method: 'raw_close',
        disqualifiers: ['missing_adjusted_close_series', 'missing_total_return_reconstruction'],
        fallbacks_used: [],
        source_price_field: 'price',
      },
    },
    portfolio_proof: createPortfolioProofFixture(),
    investor_economics_status: {
      status: 'withheld',
      reason: 'withheld_unverified_total_return_equivalence',
    },
    investor_economics_partial_unlock: investorEconomicsPartialUnlock,
    reproducibility: {
      input_imported_at: '2026-04-10T00:00:00Z',
      snapshot_as_of_date: null,
      history_start_date: '2025-01-02',
      history_end_date: '2025-03-03',
      benchmark_symbol: 'SPY',
      dataset_version: 'market_data_service_v1',
    },
  }
}

export function createDiagnosticsRunMetadataFixture(): DiagnosticsRunMetadata {
  return {
    diagnostics_id: 'diagnostics_engine_v1',
    methodology_id: 'historical_regression_v1',
    price_basis: 'close',
    source_status: {
      portfolio_history: 'synthetic_snapshot_history',
      benchmark_history: 'live_market_data_unverified_return_basis',
      factor_history: 'live_market_data_unverified_return_basis',
    },
    section_trust: {
      benchmark_relative_path: 'degraded_unverified_return_basis',
      factor_model_path: 'degraded_unverified_return_basis',
      risk_contribution_path: 'degraded_unverified_return_basis',
    },
    return_basis_evidence: {
      portfolio_history: {
        verification_status: 'unverified',
        economic_basis: 'price_return_only',
        construction_method: 'synthetic_snapshot_history',
        disqualifiers: ['synthetic_snapshot_history', 'missing_total_return_reconstruction', 'missing_dividend_coverage_proof'],
        fallbacks_used: ['synthetic_snapshot_history'],
        source_price_field: 'price',
      },
      benchmark_history: {
        verification_status: 'unverified',
        economic_basis: 'price_return_only',
        construction_method: 'raw_close',
        disqualifiers: ['missing_adjusted_close_series', 'missing_total_return_reconstruction'],
        fallbacks_used: [],
        source_price_field: 'price',
      },
      factor_history: {
        verification_status: 'unverified',
        economic_basis: 'price_return_only',
        construction_method: 'raw_close',
        disqualifiers: ['missing_adjusted_close_series', 'missing_total_return_reconstruction'],
        fallbacks_used: [],
        source_price_field: 'price',
      },
    },
    portfolio_proof: createPortfolioProofFixture(),
    investor_economics_status: {
      status: 'withheld',
      reason: 'withheld_unverified_total_return_equivalence',
    },
    factor_model_parameters: {
      rolling_windows_days: [20, 60, 252],
      current_reliability_window_days: 60,
      minimum_window_observations: { '20': 25, '60': 75, '252': 275 },
      collinearity_warning_threshold: 0.85,
      orthogonalization_basis: 'factor_proxy_definition_order',
      ridge_lambda: 1e-5,
    },
    reproducibility: {
      input_imported_at: '2026-04-10T00:00:00Z',
      snapshot_as_of_date: null,
      history_start_date: null,
      history_end_date: null,
      dataset_version: 'market_data_service_v1',
    },
    confidence: 'low',
  }
}

function cloneMutable<T>(value: unknown): T {
  return JSON.parse(JSON.stringify(value)) as T
}

const ib2026MutableDashboardFixture = cloneMutable<DashboardGoldenFixture>(ib2026ImportedDashboardGoldenFixture)
const ff2026MutableDashboardFixture = cloneMutable<DashboardGoldenFixture>(ff2026ImportedDashboardGoldenFixture)

function createImportedBenchmarkFixture() {
  return { symbol: 'SPY', start_price: 100, end_price: 105, return_pct: null, return_basis_contract: 'price_return_only' as const }
}

function createImportedSnapshotFixture() {
  return {
    statement: {
      importer: 'interactive_brokers' as const,
      account_id: 'U8516450',
      base_currency: 'USD',
      statement_period: '2025-01-01 - 2025-12-31',
      page_count: 25,
    },
    statements: [
      {
        importer: 'interactive_brokers' as const,
        account_id: 'U8516450',
        base_currency: 'USD',
        statement_period: '2025-01-01 - 2025-12-31',
        page_count: 25,
        source_path: 'C:\\docs\\IB2025.pdf',
        detected_format: 'pdf',
        imported_at: '2026-04-10T00:00:00Z',
      },
    ],
    statement_totals: null,
    positions: [
      { symbol: 'AAPL', quantity: 10, market_value: 10000, currency: 'USD' },
      { symbol: 'MSFT', quantity: 8, market_value: 8000, currency: 'USD' },
    ],
    ledger_entries: [],
    instruments: [],
    cash_balances: [{ currency: 'USD', ending_cash: 1000 }],
  }
}

function createImportedOverviewFixture() {
  return {
    total_market_value: 50000,
    total_unrealized_pnl: 5000,
    positions_count: 10,
    ledger_entries_count: 100,
    top_positions: [
      { symbol: 'AAPL', market_value: 10000, weight: 0.2, unrealized_pnl: 1200 },
      { symbol: 'MSFT', market_value: 8000, weight: 0.16, unrealized_pnl: 900 },
    ],
    sector_allocation: [
      { sector: 'Technology', market_value: 18000, weight: 0.36 },
      { sector: 'Financials', market_value: 12000, weight: 0.24 },
    ],
    sector_position_breakdown: {
      Technology: [
        { symbol: 'AAPL', market_value: 10000, weight: 0.2 },
        { symbol: 'MSFT', market_value: 8000, weight: 0.16 },
      ],
      Financials: [{ symbol: 'JPM', market_value: 12000, weight: 0.24 }],
    },
    cash_by_currency: { USD: 1000 },
  }
}

function createImportedHistoryContextFixture(): ImportedHistoryContext {
  return {
    benchmark_symbol: 'SPY',
    statement_period: '2025-01-01 - 2025-12-31',
    imported_at: '2026-04-10T00:00:00Z',
    importer: 'interactive_brokers',
    source_file_names: ['IB2025.pdf'],
    history_start_date: '2025-01-02',
    history_end_date: '2025-03-03',
  }
}

function createImportedVolatilityRegimeFixture() {
  return {
    methodology: 'Rolling volatility metrics computed from cash-flow-neutral daily portfolio returns and aligned benchmark returns; drawdown is computed from a compounded return index.',
    assumptions: {
      return_basis: 'time_weighted_daily_return',
      cash_flow_timing: 'external_cash_flow_applied_before_end_of_day_measurement',
      drawdown_basis: 'compounded_return_index',
      benchmark_basis: 'aligned_daily_price_return',
      downside_mar: 0,
      annualization_days: 252,
    },
    rolling_series: [
      {
        date: '2025-02-03',
        portfolio_return: null,
        benchmark_return: null,
        active_return: null,
        realized_vol_20d: null,
        realized_vol_60d: null,
        realized_vol_252d: null,
        downside_vol_20d: null,
        downside_vol_60d: null,
        downside_vol_252d: null,
        benchmark_vol_20d: null,
        benchmark_vol_60d: null,
        benchmark_vol_252d: null,
        tracking_error_20d: null,
        tracking_error_60d: null,
        tracking_error_252d: null,
        drawdown_pct: 0,
        wealth_index: 100,
      },
      {
        date: '2025-03-03',
        portfolio_return: 0.01,
        benchmark_return: 0.004,
        active_return: 0.006,
        realized_vol_20d: 18.4,
        realized_vol_60d: null,
        realized_vol_252d: null,
        downside_vol_20d: null,
        downside_vol_60d: 10.1,
        downside_vol_252d: null,
        benchmark_vol_20d: 12.3,
        benchmark_vol_60d: null,
        benchmark_vol_252d: null,
        tracking_error_20d: 7.2,
        tracking_error_60d: null,
        tracking_error_252d: null,
        drawdown_pct: -4.2,
        wealth_index: 101,
      },
    ],
    snapshot: {
      realized_vol_20d: 18.4,
      realized_vol_60d: null,
      realized_vol_252d: null,
      downside_vol_20d: null,
      downside_vol_60d: 10.1,
      downside_vol_252d: null,
      benchmark_vol_20d: 12.3,
      benchmark_vol_60d: null,
      benchmark_vol_252d: null,
      tracking_error_20d: 7.2,
      tracking_error_60d: null,
      tracking_error_252d: null,
      current_drawdown_pct: -4.2,
      max_drawdown_pct: -8.9,
      vol_ratio_20_60: null,
      vol_ratio_20_252: null,
      current_20d_vol_percentile: 0.78,
    },
    regime: { label: 'normal', confidence: 'medium' },
  }
}

function createImportedFactorRegistryFixture() {
  return [
    { key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', target_exposure: 'US large-cap broad market / S&P 500', primary_mapping: { provider: 'iShares', fund_name: 'iShares Core S&P 500 UCITS ETF', isin: null, example_tickers: ['CSPX', 'SXR8'], asset_exposure: 'S&P 500', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: 'Best institutional UCITS mapping for broad US market beta', match_summary: { score_pct: 89, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.95, historical_similarity: null, structure_fit: 1, implementation_fit: 0.82 } } }, alternative_mappings: [{ provider: 'Vanguard', fund_name: 'Vanguard S&P 500 UCITS ETF', isin: null, example_tickers: ['VUAA'], asset_exposure: 'S&P 500', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: null, match_summary: { score_pct: 89, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.95, historical_similarity: null, structure_fit: 1, implementation_fit: 0.82 } } }], ucits_examples: ['CSPX', 'SXR8', 'VUAA'], mapping_quality: 'high', default_enabled: true, orthogonalization_order: 1, description: 'Broad US equity beta.' },
    { key: 'growth', label: 'Growth', category: 'style', us_proxy: 'QQQ', target_exposure: 'Nasdaq-100 / US mega-cap growth', primary_mapping: { provider: 'Invesco', fund_name: 'Invesco EQQQ Nasdaq-100 UCITS ETF', isin: null, example_tickers: ['EQQQ'], asset_exposure: 'Nasdaq-100', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'distributing', mapping_quality: 'high', notes: null, match_summary: { score_pct: 82, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'degraded', hard_cap_reason: null, components: { exposure_match: 0.94, historical_similarity: null, structure_fit: 0.9, implementation_fit: 0.78 } } }, alternative_mappings: [{ provider: 'iShares', fund_name: 'iShares Nasdaq 100 UCITS ETF', isin: null, example_tickers: ['CNDX'], asset_exposure: 'Nasdaq-100', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: null, match_summary: { score_pct: 84, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.94, historical_similarity: null, structure_fit: 0.98, implementation_fit: 0.78 } } }], ucits_examples: ['EQQQ', 'CNDX'], mapping_quality: 'high', default_enabled: true, orthogonalization_order: 2, description: 'Mega-cap growth and tech tilt.' },
  ]
}

function createImportedStatisticalFactorModelFixture() {
  return {
    status: 'partial',
    benchmark_symbol: 'SPY',
    windows: [
      { window_days: 20, observations: 60, start_date: '2025-01-02', end_date: '2025-03-03', status: 'ok' },
      { window_days: 60, observations: 60, start_date: '2025-01-02', end_date: '2025-03-03', status: 'partial' },
      { window_days: 252, observations: 60, start_date: '2025-01-02', end_date: '2025-03-03', status: 'insufficient_history' },
    ],
    rolling_loadings_20d: [{ date: '2025-03-03', market: 1.1, growth: 0.35, value: 0.04, small_cap: 0.03, technology: 0.22, financials: 0.1, health_care: 0.05, energy: 0.01, industrials: 0.02, rates_ief: -0.04, rates_tlt: -0.02, credit: 0.01, commodities: 0.01, alpha: 0.0002, r_squared: 0.67, residual_vol: 5.1 }],
    rolling_loadings_60d: [{ date: '2025-03-03', market: 1.08, growth: 0.31, value: 0.03, small_cap: 0.02, technology: 0.2, financials: 0.09, health_care: 0.06, energy: 0.01, industrials: 0.02, rates_ief: -0.03, rates_tlt: -0.02, credit: 0.01, commodities: 0.01, alpha: 0.0002, r_squared: 0.66, residual_vol: 5.2 }],
    rolling_loadings_252d: [{ date: '2025-03-03', market: null, growth: null, value: null, small_cap: null, technology: null, financials: null, health_care: null, energy: null, industrials: null, rates_ief: null, rates_tlt: null, credit: null, commodities: null, alpha: null, r_squared: null, residual_vol: null }],
    current_factor_snapshot: [
      { key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 1.08, target_exposure: 'US large-cap broad market / S&P 500', primary_mapping: { provider: 'iShares', fund_name: 'iShares Core S&P 500 UCITS ETF', isin: null, example_tickers: ['CSPX', 'SXR8'], asset_exposure: 'S&P 500', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: 'Best institutional UCITS mapping for broad US market beta', match_summary: { score_pct: 89, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.95, historical_similarity: null, structure_fit: 1, implementation_fit: 0.82 } } }, alternative_mappings: [{ provider: 'Vanguard', fund_name: 'Vanguard S&P 500 UCITS ETF', isin: null, example_tickers: ['VUAA'], asset_exposure: 'S&P 500', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: null, match_summary: { score_pct: 89, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.95, historical_similarity: null, structure_fit: 1, implementation_fit: 0.82 } } }], ucits_examples: ['CSPX', 'SXR8', 'VUAA'], mapping_quality: 'high', description: 'Broad US equity beta.' },
      { key: 'growth', label: 'Growth', category: 'style', us_proxy: 'QQQ', latest_loading: 0.31, target_exposure: 'Nasdaq-100 / US mega-cap growth', primary_mapping: { provider: 'Invesco', fund_name: 'Invesco EQQQ Nasdaq-100 UCITS ETF', isin: null, example_tickers: ['EQQQ'], asset_exposure: 'Nasdaq-100', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'distributing', mapping_quality: 'high', notes: null, match_summary: { score_pct: 82, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'degraded', hard_cap_reason: null, components: { exposure_match: 0.94, historical_similarity: null, structure_fit: 0.9, implementation_fit: 0.78 } } }, alternative_mappings: [{ provider: 'iShares', fund_name: 'iShares Nasdaq 100 UCITS ETF', isin: null, example_tickers: ['CNDX'], asset_exposure: 'Nasdaq-100', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: null, match_summary: { score_pct: 84, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.94, historical_similarity: null, structure_fit: 0.98, implementation_fit: 0.78 } } }], ucits_examples: ['EQQQ', 'CNDX'], mapping_quality: 'high', description: 'Mega-cap growth and tech tilt.' },
    ],
    collinearity_diagnostics: [
      { window_days: 20, threshold: 0.85, high_collinearity_pairs: [], note: 'No high-collinearity pairs detected.' },
      { window_days: 60, threshold: 0.85, high_collinearity_pairs: [], note: 'No high-collinearity pairs detected.' },
      { window_days: 252, threshold: 0.85, high_collinearity_pairs: [], note: 'No high-collinearity pairs detected.' },
    ],
    insufficient_history: [{ window_days: 252, required_observations: 275, available_observations: 60, missing_factors: [] }],
  }
}

function createImportedDiagnosticsFixture(snapshot: ReturnType<typeof createImportedSnapshotFixture>): DiagnosticsEngineResponse {
  const drawdownSummary = {
    current_drawdown_pct: -4.2,
    max_drawdown_pct: -8.9,
  }
  const volatilitySummary = {
    portfolio_volatility_pct: 18.2,
    benchmark_volatility_pct: 12.4,
    downside_volatility_pct: 10.1,
    tracking_error_pct: 7.2,
  }
  const riskConcentrationSummary = {
    top_1_factor_risk_share: null,
    top_3_factor_risk_share: null,
    top_1_position_risk_share: null,
    top_5_position_risk_share: null,
    factor_hhi: null,
    position_hhi: null,
  }

  return {
    snapshot,
    provenance: {
      snapshot_basis: 'snapshot_request' as const,
      historical_basis: 'market_data_history' as const,
      history_truth_class: 'synthetic_history_derived' as const,
      price_basis: 'close' as const,
      note: 'Historical diagnostics are derived from synthetic snapshot-history states built from the current snapshot plus external market data. Benchmark and factor return histories remain unverified for adjusted-close or total-return equivalence in this diagnostics slice.',
    },
    availability: {
      historical_sections_available: true,
      history_context_required: true,
      note: null,
      status: 'ok',
    },
    run_metadata: {
      ...createDiagnosticsRunMetadataFixture(),
      confidence: 'medium',
    },
    drawdown_summary: drawdownSummary,
    volatility_summary: volatilitySummary,
    risk_concentration_summary: riskConcentrationSummary,
    risk_summary: {
      benchmark_symbol: 'SPY',
      methodology: 'historical regression vs SPY daily returns',
      start_date: '2025-01-02',
      end_date: '2025-03-03',
      observations: 2,
      portfolio_beta: 1.1,
      portfolio_correlation: 0.8,
      r_squared: 0.64,
      portfolio_volatility_pct: 18.2,
      benchmark_volatility_pct: 12.4,
    },
    rolling_risk: [
      { date: '2025-02-03', beta_20d: null, correlation_20d: null, beta_60d: null, correlation_60d: null, beta_252d: null, correlation_252d: null },
      { date: '2025-03-03', beta_20d: 1.05, correlation_20d: 0.78, beta_60d: null, correlation_60d: null, beta_252d: null, correlation_252d: null },
    ],
    relative_risk: {
      benchmark_symbol: 'SPY',
      tracking_error_pct: 7.2,
      active_return_pct: null,
      information_ratio: null,
    },
    volatility_regime: createImportedVolatilityRegimeFixture(),
    factor_exposures: [
      { factor: 'Market', exposure: 1.1, description: 'Historical broad-market beta versus SPY.', basis: 'historical_benchmark_relative' },
      { factor: 'SPY Overlap', exposure: 0.55, description: 'Look-through share of the portfolio that overlaps SPY constituents when benchmark holdings are available.', basis: 'benchmark_holdings_required' },
      { factor: 'Growth Tilt', exposure: 0.42, description: 'Technology and related growth sleeves.', basis: 'current_state' },
      { factor: 'Technology Tilt', exposure: 0.4, description: 'Look-through allocation to technology equity and technology ETF exposure.', basis: 'current_state' },
      { factor: 'Consumer Discretionary Tilt', exposure: 0.12, description: 'Look-through allocation to consumer discretionary equity and retail-cyclical exposure.', basis: 'current_state' },
      { factor: 'Consumer Staples Tilt', exposure: 0.08, description: 'Look-through allocation to defensive consumer staples exposure.', basis: 'current_state' },
      { factor: 'Health Care Tilt', exposure: 0.06, description: 'Look-through allocation to health care and biotechnology exposure.', basis: 'current_state' },
      { factor: 'Utilities Tilt', exposure: 0.04, description: 'Look-through allocation to utilities and regulated-infrastructure exposure.', basis: 'current_state' },
    ],
    factor_shift_diagnostics: { methodology: 'm', snapshots: [], largest_positive_shifts_20d: [], largest_negative_shifts_20d: [], largest_absolute_shifts_20d: [], largest_absolute_shifts_60d: [] },
    risk_contribution_breakdown: {
      methodology: 'm',
      window_days: 60,
      observation_count: 60,
      status: 'ok',
      factor_contributions: [],
      factor_total_variance: null,
      specific_variance: null,
      total_variance: null,
      factor_risk_share_total: null,
      specific_risk_share: null,
      residual_volatility: null,
      position_contributions: [],
      concentration: { top_1_factor_risk_share: null, top_3_factor_risk_share: null, top_1_position_risk_share: null, top_5_position_risk_share: null, factor_hhi: null, position_hhi: null },
    },
    model_reliability: { window_days: 60, observation_count: 60, r_squared: 0.66, residual_volatility: 5.2, collinearity_pair_count: 0, max_abs_factor_correlation: null, factor_count_used: 12, missing_factor_count: 0, status: 'partial', confidence: 'medium', stability_score: 0.91 },
    factor_registry: createImportedFactorRegistryFixture(),
    factor_methodology: 'Orthogonalized rolling ridge factor model using US ETF proxies for market, style, sector, and macro exposures; UCITS symbols are shown separately as EU execution examples.',
    statistical_factor_model: createImportedStatisticalFactorModelFixture(),
    stress_scenarios: [{ name: 'Broad Market Selloff', estimated_return_pct: -8.5, description: 'Risk-off equity drawdown.' }],
  }
}

function createImportedExposureFixture(snapshot: ReturnType<typeof createImportedSnapshotFixture>, overview: ReturnType<typeof createImportedOverviewFixture>): ExposureEngineResponse {
  return {
    snapshot,
    provenance: {
      snapshot_basis: 'snapshot_request',
      historical_basis: 'current_state_only',
      price_basis: 'not_applicable',
      note: 'Exposure is a current-state engine view built from the submitted snapshot and look-through resolution inputs. Historical diagnostics are separate.',
    },
    run_metadata: {
      engine_id: 'exposure_engine_v1',
      methodology_id: 'exposure_current_state_methodology_v1',
      price_basis: 'not_applicable',
      source_status: {
        lookthrough_resolution: 'live',
        benchmark_holdings: 'verified',
      },
      confidence: 'low',
      reproducibility: {
        input_imported_at: '2026-04-10T00:00:00Z',
        snapshot_as_of_date: null,
        benchmark_symbol: 'SPY',
        dataset_version: 'market_data_service_v1',
      },
    },
    diagnostics_run_metadata: createImportedDiagnosticsFixture(snapshot).run_metadata,
    overview,
    lookthrough: {
      portfolio_market_value: 50000,
      covered_market_value: 50000,
      coverage_ratio: 1,
      etf_resolution: { VUAA: 'SPY' },
      uncovered_positions: [],
      top_constituents: [
        { symbol: 'AAPL', name: 'Apple', effective_market_value: 12000, portfolio_weight: 0.24, sources: [{ source_symbol: 'AAPL', source_market_value: 10000, source_weight: 1, resolved_via: 'AAPL' }] },
        { symbol: 'MSFT', name: 'Microsoft', effective_market_value: 9000, portfolio_weight: 0.18, sources: [{ source_symbol: 'MSFT', source_market_value: 8000, source_weight: 1, resolved_via: 'MSFT' }] },
      ],
    },
    lookthrough_sector_exposure: [
      { sector: 'Technology', market_value: 20000, weight: 0.4 },
      { sector: 'Health Care', market_value: 10000, weight: 0.2 },
    ],
    market_overlap: {
      benchmark_symbol: 'SPY',
      overlap_weight: 0.28,
      active_share: 0.62,
      portfolio_in_benchmark_weight: 0.55,
      benchmark_covered_weight: 1,
      top_overweights: [
        { symbol: 'AAPL', name: 'Apple', portfolio_weight: 0.24, benchmark_weight: 0.07, active_weight: 0.17 },
        { symbol: 'MSFT', name: 'Microsoft', portfolio_weight: 0.18, benchmark_weight: 0.06, active_weight: 0.12 },
      ],
      top_underweights: [
        { symbol: 'AMZN', name: 'Amazon', portfolio_weight: 0.01, benchmark_weight: 0.04, active_weight: -0.03 },
        { symbol: 'GOOG', name: 'Alphabet', portfolio_weight: 0.02, benchmark_weight: 0.05, active_weight: -0.03 },
      ],
    },
    current_state_concentration: {
      top_positions: [
        { name: 'AAPL', market_value: 10000, weight: 0.2 },
        { name: 'MSFT', market_value: 8000, weight: 0.16 },
        { name: 'JPM', market_value: 12000, weight: 0.24 },
      ],
      top_sectors: [
        { name: 'Technology', market_value: 18000, weight: 0.36 },
        { name: 'Financials', market_value: 12000, weight: 0.24 },
      ],
      top_1_position_weight: 0.24,
      top_3_position_weight: 0.6,
      top_5_position_weight: 0.6,
      top_sector_weight: 0.36,
      top_3_sector_weight: 0.6,
      position_hhi: 0.1232,
      sector_hhi: 0.1872,
      effective_holdings: 8.12,
    },
    availability: {
      lookthrough_status: 'live',
      lookthrough_confidence: 'high',
      benchmark_overlap_status: 'live',
      benchmark_overlap_confidence: 'high',
      note: null,
    },
  }
}

function createImportedDashboardSeriesFixture() {
  return {
    performance_series: [
      { date: '2025-01-02', portfolio_value: 10000, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
      { date: '2025-02-03', portfolio_value: 11000, benchmark_price: 102, portfolio_return_pct: 0, benchmark_return_pct: null },
      { date: '2025-03-03', portfolio_value: 12000, benchmark_price: 105, portfolio_return_pct: 0, benchmark_return_pct: null },
    ],
    daily_states: [
      { date: '2025-01-02', total_market_value: 9000, total_portfolio_value: 10000, external_cash_flow: 0, cash: { USD: 1000 }, positions: [] },
      { date: '2025-02-03', total_market_value: 10000, total_portfolio_value: 11000, external_cash_flow: 1000, cash: { USD: 1000 }, positions: [] },
      { date: '2025-03-03', total_market_value: 11000, total_portfolio_value: 12000, external_cash_flow: 0, cash: { USD: 1000 }, positions: [] },
    ],
  }
}

function createImportedDashboardRangeMetricsFixture() {
  return {
    '1M': {
      summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: null, excess_return_pct: null },
      max_drawdown_pct: 0,
      monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
      monthly_returns_reliable: true,
    },
    '3M': {
      summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: null, excess_return_pct: null },
      max_drawdown_pct: 0,
      monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
      monthly_returns_reliable: true,
    },
    YTD: {
      summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: null, excess_return_pct: null },
      max_drawdown_pct: 0,
      monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
      monthly_returns_reliable: true,
    },
    '1Y': {
      summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: null, excess_return_pct: null },
      max_drawdown_pct: 0,
      monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
      monthly_returns_reliable: true,
    },
    All: {
      summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: null, excess_return_pct: null },
      max_drawdown_pct: 0,
      monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
      monthly_returns_reliable: true,
    },
  }
}

export function createImportedFixtureParts() {
  const snapshot = createImportedSnapshotFixture()
  const overview = createImportedOverviewFixture()
  const diagnostics = createImportedDiagnosticsFixture(snapshot)

  return {
    snapshot,
    overview,
    diagnostics,
    exposure: createImportedExposureFixture(snapshot, overview),
    history_context: createImportedHistoryContextFixture(),
  }
}

export function createImportedBootstrapResponseFixture(): ImportedBootstrapResponse {
  const fixture = createImportedFixtureParts()
  return {
    snapshot: fixture.snapshot,
    overview: fixture.overview,
    risk_summary: fixture.diagnostics.risk_summary,
    history_context: fixture.history_context,
  }
}

export function createExposureEngineFixture(): ExposureEngineResponse {
  return createImportedFixtureParts().exposure
}

export function createDiagnosticsEngineFixture(): DiagnosticsEngineResponse {
  return createImportedFixtureParts().diagnostics
}

export function createImportedDashboardHistoryFixture() {
  const fixture = createImportedDashboardFixture()
  return {
    performance_series: fixture.performance_series,
    daily_states: fixture.daily_states,
    source_status: fixture.source_status,
    run_metadata: fixture.run_metadata,
    benchmark: { symbol: 'SPY', start_price: 100, end_price: 105, return_pct: null, return_basis_contract: 'price_return_only' },
  }
}

export function createImportedDashboardFixture(): ImportedDashboardSource {
  const fixture = createImportedFixtureParts()
  return {
    snapshot: fixture.snapshot,
    overview: fixture.overview,
    performance_series: [
      { date: '2025-01-02', portfolio_value: 10000, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
      { date: '2025-02-03', portfolio_value: 11000, benchmark_price: 102, portfolio_return_pct: 0, benchmark_return_pct: null },
      { date: '2025-03-03', portfolio_value: 12000, benchmark_price: 105, portfolio_return_pct: 0, benchmark_return_pct: null },
    ],
    daily_states: [
      { date: '2025-01-02', total_market_value: 9000, total_portfolio_value: 10000, external_cash_flow: 0, cash: { USD: 1000 }, positions: [] },
      { date: '2025-02-03', total_market_value: 10000, total_portfolio_value: 11000, external_cash_flow: 1000, cash: { USD: 1000 }, positions: [] },
      { date: '2025-03-03', total_market_value: 11000, total_portfolio_value: 12000, external_cash_flow: 0, cash: { USD: 1000 }, positions: [] },
    ],
    source_status: { performance_history: 'live', monthly_returns: 'live' },
    run_metadata: createDashboardHistoryRunMetadataFixture(),
    range_metrics: {
      '1M': {
        summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: null, excess_return_pct: null },
        max_drawdown_pct: null,
        monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
        monthly_returns_reliable: true,
      },
      '3M': {
        summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: null, excess_return_pct: null },
        max_drawdown_pct: null,
        monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
        monthly_returns_reliable: true,
      },
      YTD: {
        summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: null, excess_return_pct: null },
        max_drawdown_pct: null,
        monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
        monthly_returns_reliable: true,
      },
      '1Y': {
        summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: null, excess_return_pct: null },
        max_drawdown_pct: null,
        monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
        monthly_returns_reliable: true,
      },
      All: {
        summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: null, excess_return_pct: null },
        max_drawdown_pct: null,
        monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
        monthly_returns_reliable: true,
      },
    },
  }
}

export function createIb2026ImportedDashboardFixture(): ImportedDashboardSource {
  return cloneMutable(ib2026MutableDashboardFixture)
}

export function createFf2026ImportedDashboardFixture(): ImportedDashboardSource {
  return cloneMutable(ff2026MutableDashboardFixture)
}

export function createIb2026ExposureEngineFixture(): ExposureEngineResponse {
  return {
    ...createExposureEngineFixture(),
    snapshot: cloneMutable(ib2026MutableDashboardFixture.snapshot),
    overview: cloneMutable(ib2026MutableDashboardFixture.overview),
  }
}

export function createIb2026DiagnosticsEngineFixture(): DiagnosticsEngineResponse {
  return {
    ...createDiagnosticsEngineFixture(),
    snapshot: cloneMutable(ib2026MutableDashboardFixture.snapshot),
    provenance: {
      snapshot_basis: 'imported_snapshot',
      historical_basis: 'imported_portfolio_history',
      history_truth_class: 'imported_history_equivalent',
      price_basis: 'close',
      note: 'Historical diagnostics are derived from imported portfolio history replay plus external benchmark and factor market data. Benchmark and factor return histories remain unverified for adjusted-close or total-return equivalence in this diagnostics slice.',
    },
    run_metadata: {
      ...createDiagnosticsEngineFixture().run_metadata,
      source_status: {
        portfolio_history: 'imported_replay',
        benchmark_history: 'live_market_data_verified_adjusted_close',
        factor_history: 'live_market_data_verified_adjusted_close',
      },
      section_trust: {
        benchmark_relative_path: 'verified_adjusted_close',
        factor_model_path: 'verified_adjusted_close',
        risk_contribution_path: 'verified_adjusted_close',
      },
      return_basis_evidence: {
        portfolio_history: {
          verification_status: 'unverified',
          economic_basis: 'unavailable',
          construction_method: 'unknown',
          disqualifiers: ['missing_portfolio_return_basis_proof'],
          fallbacks_used: [],
          source_price_field: null,
        },
        benchmark_history: {
          verification_status: 'proxy',
          economic_basis: 'adjusted_close_proxy',
          construction_method: 'vendor_adjusted_close',
          disqualifiers: ['missing_dividend_coverage_proof', 'missing_vendor_scope_proof', 'adjusted_close_is_not_verified_total_return'],
          fallbacks_used: [],
          source_price_field: 'adjClose',
        },
        factor_history: {
          verification_status: 'proxy',
          economic_basis: 'adjusted_close_proxy',
          construction_method: 'vendor_adjusted_close',
          disqualifiers: ['missing_dividend_coverage_proof', 'missing_vendor_scope_proof', 'adjusted_close_is_not_verified_total_return'],
          fallbacks_used: [],
          source_price_field: 'adjClose',
        },
      },
      confidence: 'low',
    },
    risk_summary: cloneMutable(ib2026MutableDashboardFixture.risk_summary),
  }
}

export function createFf2026ExposureEngineFixture(): ExposureEngineResponse {
  return {
    ...createExposureEngineFixture(),
    snapshot: cloneMutable(ff2026MutableDashboardFixture.snapshot),
    overview: cloneMutable(ff2026MutableDashboardFixture.overview),
  }
}

export function createFf2026DiagnosticsEngineFixture(): DiagnosticsEngineResponse {
  return {
    ...createDiagnosticsEngineFixture(),
    snapshot: cloneMutable(ff2026MutableDashboardFixture.snapshot),
    provenance: {
      snapshot_basis: 'imported_snapshot',
      historical_basis: 'imported_portfolio_history',
      history_truth_class: 'imported_history_equivalent',
      price_basis: 'close',
      note: 'Historical diagnostics are derived from imported portfolio history replay plus external benchmark and factor market data. Benchmark and factor return histories remain unverified for adjusted-close or total-return equivalence in this diagnostics slice.',
    },
    run_metadata: {
      ...createDiagnosticsEngineFixture().run_metadata,
      source_status: {
        portfolio_history: 'imported_replay',
        benchmark_history: 'live_market_data_verified_adjusted_close',
        factor_history: 'live_market_data_verified_adjusted_close',
      },
      section_trust: {
        benchmark_relative_path: 'verified_adjusted_close',
        factor_model_path: 'verified_adjusted_close',
        risk_contribution_path: 'verified_adjusted_close',
      },
      return_basis_evidence: {
        portfolio_history: {
          verification_status: 'unverified',
          economic_basis: 'unavailable',
          construction_method: 'unknown',
          disqualifiers: ['missing_portfolio_return_basis_proof'],
          fallbacks_used: [],
          source_price_field: null,
        },
        benchmark_history: {
          verification_status: 'proxy',
          economic_basis: 'adjusted_close_proxy',
          construction_method: 'vendor_adjusted_close',
          disqualifiers: ['missing_dividend_coverage_proof', 'missing_vendor_scope_proof', 'adjusted_close_is_not_verified_total_return'],
          fallbacks_used: [],
          source_price_field: 'adjClose',
        },
        factor_history: {
          verification_status: 'proxy',
          economic_basis: 'adjusted_close_proxy',
          construction_method: 'vendor_adjusted_close',
          disqualifiers: ['missing_dividend_coverage_proof', 'missing_vendor_scope_proof', 'adjusted_close_is_not_verified_total_return'],
          fallbacks_used: [],
          source_price_field: 'adjClose',
        },
      },
      confidence: 'high',
    },
    risk_summary: cloneMutable(ff2026MutableDashboardFixture.risk_summary),
  }
}

export function createImportedBaselineFixture(): ImportedBaselineSource {
  const fixture = createImportedDashboardFixture()
  return {
    snapshot: fixture.snapshot,
    overview: fixture.overview,
  }
}

export function createDiagnosticsFixture(): DiagnosticsEngineResponse {
  return {
    snapshot: {
      statement: { importer: 'interactive_brokers', account_id: 'U1', base_currency: 'USD', statement_period: '2025', page_count: 1 },
      statements: [{ importer: 'interactive_brokers', account_id: 'U1', base_currency: 'USD', statement_period: '2025', page_count: 1, source_path: 'C:\\docs\\IB2025.pdf', detected_format: 'pdf', imported_at: '2026-04-10T00:00:00Z' }],
      positions: [],
      ledger_entries: [],
      instruments: [],
      cash_balances: [],
    },
    provenance: {
      snapshot_basis: 'snapshot_request',
      historical_basis: 'market_data_history',
      history_truth_class: 'synthetic_history_derived',
      price_basis: 'close',
      note: 'Historical diagnostics are derived from synthetic snapshot-history states built from the current snapshot plus external market data. Benchmark and factor return histories remain unverified for adjusted-close or total-return equivalence in this diagnostics slice.',
    },
    run_metadata: createDiagnosticsRunMetadataFixture(),
    drawdown_summary: { current_drawdown_pct: null, max_drawdown_pct: null },
    volatility_summary: {
      portfolio_volatility_pct: 18.2,
      benchmark_volatility_pct: 12.4,
      downside_volatility_pct: 10.1,
      tracking_error_pct: 7.2,
    },
    risk_concentration_summary: {
      top_1_factor_risk_share: 0.52,
      top_3_factor_risk_share: 0.52,
      top_1_position_risk_share: 0.55,
      top_5_position_risk_share: 1,
      factor_hhi: 0.27,
      position_hhi: 0.51,
    },
    risk_summary: { benchmark_symbol: 'SPY', methodology: 'm', start_date: null, end_date: null, observations: 0, portfolio_beta: null, portfolio_correlation: null, r_squared: null, portfolio_volatility_pct: null, benchmark_volatility_pct: null },
    rolling_risk: [],
    relative_risk: { benchmark_symbol: 'SPY', tracking_error_pct: null, active_return_pct: null, information_ratio: null },
    volatility_regime: { methodology: 'm', assumptions: { return_basis: 'time_weighted_daily_return', cash_flow_timing: 'external_cash_flow_applied_before_end_of_day_measurement', drawdown_basis: 'compounded_return_index', benchmark_basis: 'aligned_daily_price_return', downside_mar: 0, annualization_days: 252 }, rolling_series: [], snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: null, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: null, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: null, current_drawdown_pct: null, max_drawdown_pct: null, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null }, regime: { label: 'normal', confidence: 'low' } },
    factor_exposures: [
      { factor: 'Market', exposure: null, description: 'Historical broad-market beta versus SPY.', basis: 'historical_benchmark_relative' },
      { factor: 'SPY Overlap', exposure: null, description: 'Look-through share of the portfolio that overlaps SPY constituents when benchmark holdings are available.', basis: 'benchmark_holdings_required' },
      { factor: 'Growth Tilt', exposure: 0.42, description: 'Technology, communication services, and consumer discretionary sleeve weight.', basis: 'current_state' },
      { factor: 'Technology Tilt', exposure: 0.4, description: 'Look-through allocation to technology equity and technology ETF exposure.', basis: 'current_state' },
      { factor: 'Consumer Discretionary Tilt', exposure: 0.12, description: 'Look-through allocation to consumer discretionary equity and retail-cyclical exposure.', basis: 'current_state' },
      { factor: 'Consumer Staples Tilt', exposure: 0.08, description: 'Look-through allocation to defensive consumer staples exposure.', basis: 'current_state' },
      { factor: 'Health Care Tilt', exposure: 0.06, description: 'Look-through allocation to health care and biotechnology exposure.', basis: 'current_state' },
      { factor: 'Utilities Tilt', exposure: 0.04, description: 'Look-through allocation to utilities and regulated-infrastructure exposure.', basis: 'current_state' },
    ],
    factor_shift_diagnostics: { methodology: 'm', snapshots: [{ key: 'market', label: 'Market', us_proxy: 'SPY', category: 'market', current_loading_20d: 1.1, current_loading_60d: 1.0, current_loading_252d: null, change_20d: 0.3, change_60d: null, abs_change_20d: 0.3, abs_change_60d: null, stability_gap_20d_60d: 0.1, stability_gap_60d_252d: null, available_windows_count: 2, shift_flag_20d: true, shift_flag_60d: false, stability_flag: false, collinearity_flag: false, volatility_flag: true, confidence: 'medium' }], largest_positive_shifts_20d: [{ key: 'market', label: 'Market', us_proxy: 'SPY', current_loading: 1.1, change_value: 0.3, absolute_change: 0.3 }], largest_negative_shifts_20d: [], largest_absolute_shifts_20d: [{ key: 'market', label: 'Market', us_proxy: 'SPY', current_loading: 1.1, change_value: 0.3, absolute_change: 0.3 }], largest_absolute_shifts_60d: [] },
    risk_contribution_breakdown: { methodology: 'm', window_days: 60, observation_count: 60, status: 'ok', factor_contributions: [{ key: 'market', label: 'Market', us_proxy: 'SPY', loading: 1.1, factor_volatility: 12.4, variance_contribution: 0.0123, risk_share: 0.52 }], factor_total_variance: 0.0123, specific_variance: 0.0031, total_variance: 0.0154, factor_risk_share_total: 0.7987, specific_risk_share: 0.2013, residual_volatility: 8.4, position_contributions: [{ symbol: 'AAPL', weight: 0.5, volatility: 20.2, marginal_contribution: 0.0123, component_contribution: 0.0061, risk_share: 0.55 }], concentration: { top_1_factor_risk_share: 0.52, top_3_factor_risk_share: 0.52, top_1_position_risk_share: 0.55, top_5_position_risk_share: 1, factor_hhi: 0.27, position_hhi: 0.51 } },
    model_reliability: { window_days: 60, observation_count: 60, r_squared: 0.66, residual_volatility: 8.4, collinearity_pair_count: 1, max_abs_factor_correlation: 0.89, factor_count_used: 5, missing_factor_count: 7, status: 'ok', confidence: 'medium', stability_score: 0.87 },
    factor_registry: [],
    factor_methodology: null,
    statistical_factor_model: { status: 'partial', benchmark_symbol: 'SPY', windows: [], collinearity_diagnostics: [], current_factor_snapshot: [], insufficient_history: [], rolling_loadings_20d: [], rolling_loadings_60d: [], rolling_loadings_252d: [] },
    stress_scenarios: [],
    availability: { historical_sections_available: true, history_context_required: true, note: null, status: 'ok' },
  }
}
