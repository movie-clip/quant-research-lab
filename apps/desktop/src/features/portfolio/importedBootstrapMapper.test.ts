import { describe, expect, it } from 'vitest'

import { createImportedBootstrapResponseFixture } from '../../test/portfolioFixtures'
import { projectImportedBootstrap } from './importedBootstrapMapper'

describe('projectImportedBootstrap', () => {
  it('threads import admission summary into workspace projection', () => {
    const bootstrap = createImportedBootstrapResponseFixture()

    const projected = projectImportedBootstrap(bootstrap)

    expect(projected.workspace.admission_summary).toEqual(bootstrap.admission_summary)
    expect(projected.workspace.admission_summary?.schema_version).toBe('import_admission_summary_v1')
  })
})
