# PRD: Epic 12 — UI Polish & Design System

**Status:** Active
**Last updated:** 2026-05-28

---

## Problem

The Exposure tab gained four new feature cards across Epics 9 and 11
(DriftBenchmarkPanel + IndexedReturnChart, RollingCorrelationChart,
FactorAttributionCard, BenchmarkCorrelationTable). Each was built in
isolation, optimised for shipping the underlying analytic correctly, and as
a result the surface is visually inconsistent and not production-ready:

1. **No shared design tokens.** Each component hand-rolls hex colors
   (`'#5b87c5'`, `'#3cb79f'`, `'#94a3b8'`, ...), font sizes (`fontSize: 11`,
   `fontSize: 13`), spacings (`padding: '6px 12px'`, `marginBottom: 12`).
   The same "muted body text gray" appears as three different hex values
   across three files. Changing the theme would require editing every card.

2. **Text overlap and alignment on the rolling correlation chart.** The
   dual-axis layout (`<YAxis yAxisId="correlation">` left,
   `<YAxis yAxisId="beta">` right) collides with the rotated axis labels at
   narrow widths. Right-margin (`margin={{ right: 56 }}`) was picked
   empirically and breaks below ~700 px.

3. **Repeated, slightly-different window selectors.** A 20d/60d/252d (or
   1m/3m/6m/12m/since-import) button group appears in three components.
   Each implements its own DOM, ARIA, and active-state styling. They look
   similar but not identical.

4. **Empty / loading / error states are inconsistent.** Some use
   `.empty-state-panel.compact-empty-state`, some use an inline
   `<p className="helper">`, some use a custom flex container. The
   "Synthetic" trust badge is rendered three different ways across the four
   cards.

5. **Accessibility gaps.** Icon-only buttons miss `aria-label` in places;
   color is the sole encoder for correlation sign (positive=teal,
   negative=red) which fails color-blind users; chart text contrast hasn't
   been audited; no focus-visible styles on the custom buttons.

6. **No teachable pattern for new cards.** When the next analytic ships
   (whether by a human or an agent invoking `build-story`), the implementer
   has no shared primitives to lean on — they'll hand-roll inline styles
   again, perpetuating the inconsistency.

The product is functionally correct but does not look or behave like a
production research workbench. Before adding more analytics, we need a
real design system the next card can plug into.

---

## Goal

- Every visible color, spacing, and typography value used by the four
  Exposure cards is sourced from a single token file. No literal hex in
  component code.
- The cards share a small set of primitive components (`<CardShell>`,
  `<WindowSelector>`, `<TrustBadge>`, `<EmptyState>`, `<LoadingState>`,
  `<ErrorState>`, `<ChartShell>`) that enforce visual + behavioural
  consistency by construction.
- Text overlap, axis alignment, and tooltip positioning issues on the
  rolling correlation chart and similar surfaces are fixed.
- The surface meets a baseline accessibility bar: ARIA labels on icon-only
  controls, focus-visible styles, color-is-not-sole-encoder for semantic
  meaning, contrast ≥ WCAG AA for body text.
- A `ui-polish` skill exists that codifies the patterns above so any agent
  picking up the next analytics story produces a card matching the system.

---

## Non-goals

- **Not** redesigning the Concentration Pack section (still uses the older
  `.dashboard-summary` / `.concentration-pack-*` CSS classes). That can be
  migrated later if the patterns prove out.
- **Not** redesigning the Dashboard tab. Stable; out of scope for this epic.
- **Not** introducing a CSS-in-JS library (styled-components, emotion).
  Stay with inline styles + CSS variables + existing `app/styles.css`.
- **Not** introducing a component library (shadcn, MUI, Mantine). The
  primitive set we need is small (~6 components) and bespoke is fine.
- **Not** building a Storybook or component catalog UI. The primitives are
  documented in the contract doc + the skill, not in a separate dev app.
- **Not** changing any financial formula, schema, route, or trust class.
  Pure UI refactor + skill.
- **Not** adding new charts or analytics. Only polishing what exists.

---

## Story list

| Story | Title | Scope |
|---|---|---|
| US-12.1 | Design tokens + apply to the four Exposure cards | New `designTokens.ts` (or CSS variables in `styles.css`) for colors, spacing, typography; refactor the four cards to consume tokens; fix the rolling-correlation chart's text overlap and axis alignment in the same pass |
| US-12.2 | Primitive components (CardShell, WindowSelector, TrustBadge, EmptyState/LoadingState/ErrorState) + refactor cards | Build the 5–6 primitives; refactor the four cards to use them; remove the duplicated header/badge/selector code |
| US-12.3 | Accessibility + Recharts defaults (ChartShell wrapper) | ARIA labels, focus-visible, color-blind-safe encoding (icons/patterns supplement color); `<ChartShell>` wrapper that sets axis/grid/tooltip defaults so individual charts stop hand-rolling them; contrast audit |
| US-12.4 | `ui-polish` skill + Epic 12 close-out | Author `.claude/skills/ui-polish/SKILL.md` codifying the patterns from US-12.1–12.3; update `docs/contracts/ui-design-system.md` (new contract doc); roadmap slice log + epic close |

Stories must be built in order (12.1 → 12.2 → 12.3 → 12.4). 12.2 depends
on tokens from 12.1; 12.3's `<ChartShell>` depends on primitives from 12.2;
12.4's skill cites file paths that exist after 12.3.

---

## Success signals

- After US-12.1: `grep -E "#[0-9a-fA-F]{3,6}" apps/desktop/src/features/portfolio/{DriftBenchmarkPanel,IndexedReturnChart,RollingCorrelationChart,FactorAttributionCard,BenchmarkCorrelationTable}.tsx`
  returns no matches (or only matches in a sanctioned escape hatch list).
- After US-12.2: the literal string `"Synthetic"` appears in exactly one
  place in the codebase (`<TrustBadge type="synthetic" />`). Same for the
  window-selector button group.
- After US-12.3: the rolling correlation chart and benchmark correlation
  table both pass an axe-core (or equivalent) accessibility check with no
  errors at the AA level. ρ values can be distinguished without color
  (small icon or symbol prefix in the table).
- After US-12.4: a fresh `build-story` invocation on a new analytics card
  produces a component that uses `<CardShell>`, `<WindowSelector>`,
  `<TrustBadge>` and tokenised colors — without the agent re-reading any
  existing card.
- All 263 backend pytest stay green. Frontend vitest count grows
  (~+5 per story) but no regressions in existing tests.
- `npx tsc --noEmit` clean throughout.
- Manual visual check: chart no longer has text overlap or alignment issues
  at the default viewport width.

---

## Out of scope (named explicitly to bound the epic)

- Dashboard tab redesign
- Concentration Pack visual refactor
- New chart types or new analytics
- Theme switcher (dark/light/system) — tokens enable it but a switcher UI
  is its own story
- Mobile / responsive layout below 600 px
- Print stylesheet
- Localization / i18n
- Animations / transitions polish (everything stays `isAnimationActive={false}`)
