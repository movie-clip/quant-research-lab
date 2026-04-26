import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ReplacementRankingReview } from './ReplacementRankingReview'

describe('ReplacementRankingReview', () => {
  it('renders saved ranking review details, warnings, and exclusions', () => {
    render(
      <ReplacementRankingReview
        artifact={{
          kind: 'intent_bound_seeded_etf_replacement_ranking',
          source: 'etf_ranking',
          workspaceId: 'workspace-1',
          draftId: 'draft-1',
          baseNodeId: 'node-1',
          selectedAt: '2026-04-15T00:00:00Z',
          baseSymbol: 'VUAA',
          candidateSymbol: 'IUFS',
          candidateRank: 1,
          rankingId: 'etf_ranking_engine_v1',
          methodologyId: 'etf_ranking_methodology_v1',
          rankingBasisDate: '2026-04-15',
          openHandoff: {
            handoff_kind: 'ranking_artifact_open_handoff_v1',
            artifact_kind: 'etf_ranking',
            artifact_id: 'etf_ranking_artifact_sector_1',
            schema_version: 'etf_ranking_artifact_v1',
          },
          benchmarkSymbol: 'SPY',
          lookbackMonths: 6,
          peerGroup: 'Sector UCITS ETF',
          confidence: 'medium',
          holdingsSupport: 'mixed',
          requestUniverse: ['VUAA', 'IUFS', 'IUHC'],
          evaluatedUniverse: ['IUFS', 'IUHC'],
          warnings: ['Implementation-fit support is not complete across the ranked universe.'],
          excludedSymbols: [{ symbol: 'VDST', reason: 'instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF' }],
          selectedCandidate: {
            symbol: 'IUFS',
            rank: 1,
            compositeScore: 0.8123,
            instrument: {
              name: 'iShares S&P 500 Financials Sector UCITS ETF',
              assetClass: 'etf',
              sector: 'Financials',
              category: 'Sector UCITS ETF',
              currency: 'USD',
            },
          },
          topCandidate: {
            symbol: 'IUFS',
            rank: 1,
            compositeScore: 0.8123,
            instrument: {
              name: 'iShares S&P 500 Financials Sector UCITS ETF',
              assetClass: 'etf',
              sector: 'Financials',
              category: 'Sector UCITS ETF',
              currency: 'USD',
            },
          },
          runnerUpCandidate: {
            symbol: 'IUHC',
            rank: 2,
            compositeScore: 0.7345,
            instrument: {
              name: 'iShares S&P 500 Health Care Sector UCITS ETF',
              assetClass: 'etf',
              sector: 'Health Care',
              category: 'Sector UCITS ETF',
              currency: 'USD',
            },
          },
        }}
      />, 
    )

    expect(screen.getByText('Ranked Review')).toBeTruthy()
    expect(screen.getByText('This review saves deterministic ranking context for the ETF you explicitly chose. It supports selection only; replay still validates whether that choice improves the portfolio.')).toBeTruthy()
    expect(screen.getByText('VUAA')).toBeTruthy()
    expect(screen.getAllByText('IUFS').length).toBeGreaterThan(0)
    expect(screen.getByText('IUHC')).toBeTruthy()
    expect(screen.getByText('0.8123')).toBeTruthy()
    expect(screen.getByText('Chosen Candidate')).toBeTruthy()
    expect(screen.getByText('Total Score')).toBeTruthy()
    expect(screen.getByText('Highest-Ranked Eligible')).toBeTruthy()
    expect(screen.getByText('Next Eligible')).toBeTruthy()
    expect(screen.getByText('Top Factor Contributions')).toBeTruthy()
    expect(screen.getByText('Factor-level contribution rows are not persisted in the local ranking review artifact.')).toBeTruthy()
    expect(screen.getByText('Ranking Status')).toBeTruthy()
    expect(screen.getByText('Backend ranking completed with warnings or exclusions. Review the saved details before replay.')).toBeTruthy()
    expect(screen.getByText('This is saved ranking review context only. No holdings change has been applied, no candidate is adopted automatically, and no hypothetical replay has been run from this artifact alone.')).toBeTruthy()
    expect(screen.getByText('If you still want to test this explicit user choice, create replacement intent first and use hypothetical replay as the validation step.')).toBeTruthy()
    expect(screen.getByText('Implementation-fit support is not complete across the ranked universe.')).toBeTruthy()
    expect(screen.getByText('VDST')).toBeTruthy()
    expect(screen.getByText('instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF')).toBeTruthy()
  })
})
