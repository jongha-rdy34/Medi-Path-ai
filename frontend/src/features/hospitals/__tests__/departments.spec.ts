import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { DEPARTMENTS, departmentName } from '../departments'

// Vitest runs from frontend/ (vitest.config.ts root).
const CSV = resolve(process.cwd(), '../data/mappings/departments.csv')

describe('departments', () => {
  it('matches data/mappings/departments.csv (code, name_ko)', () => {
    const rows = readFileSync(CSV, 'utf-8')
      .replace(/\r/g, '')
      .trim()
      .split('\n')
      .slice(1)
      .map((line) => line.split(','))
      .map(([code, name]) => ({ code, name }))

    expect(DEPARTMENTS).toEqual(rows)
  })

  it('looks up names and falls back to the code', () => {
    expect(departmentName('01')).toBe('내과')
    expect(departmentName('ZZ')).toBe('ZZ')
  })
})
