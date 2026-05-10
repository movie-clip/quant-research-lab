export type DenseInsightMarker = 'trusted' | 'partial' | 'degraded' | 'stale' | 'withheld' | 'unavailable'

export type DenseInsightStripItem = {
  title: string
  headline: string
  facts: string[]
  marker: DenseInsightMarker
}

type DenseInsightStripProps = {
  ariaLabel: string
  items: DenseInsightStripItem[]
  heading?: string
  subheading?: string
  className?: string
}

export function DenseInsightStrip({ ariaLabel, items, heading, subheading, className }: DenseInsightStripProps) {
  return (
    <section className={className ? `dense-insight-strip-shell ${className}` : 'dense-insight-strip-shell'} aria-label={ariaLabel}>
      {heading ? (
        <div className="section-header-inline dense-insight-strip-header panel-section-heading">
          <div className="panel-section-title-block">
            <p className="panel-label">{heading}</p>
            {subheading ? <h3>{subheading}</h3> : null}
          </div>
        </div>
      ) : null}
      <div className="dense-insight-strip-grid">
        {items.map((item) => (
          <article className="summary-card dense-insight-card" key={`${item.title}-${item.headline}`}>
            <div className="section-header-inline dense-insight-card-header">
              <div className="panel-section-title-block">
                <p className="panel-label">{item.title}</p>
              </div>
              <span className={`dashboard-snapshot-status dashboard-snapshot-status-${item.marker}`}>{item.marker}</span>
            </div>
            <p className="summary-value dense-insight-headline">{item.headline}</p>
            <div className="dense-insight-facts">
              {item.facts.slice(0, 2).map((fact) => <p className="helper" key={`${item.title}-${fact}`}>{fact}</p>)}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
