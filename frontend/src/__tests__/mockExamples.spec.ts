import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { CONTRACT, extractExamples } from '../../scripts/sync-mock-examples.mjs'
import examples from '../mocks/examples.json'

describe('mock examples', () => {
  it('match contracts/openapi.yaml (run `npm run mocks:sync` if this fails)', () => {
    expect(examples).toEqual(extractExamples(readFileSync(CONTRACT, 'utf8')))
  })
})
