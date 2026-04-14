import React from 'react'
import { vi } from 'vitest'

vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts')

  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => {
      if (!React.isValidElement(children)) {
        return <>{children}</>
      }

      return React.cloneElement(children as React.ReactElement<{ width?: number; height?: number }>, {
        width: 960,
        height: 320,
      })
    },
  }
})
