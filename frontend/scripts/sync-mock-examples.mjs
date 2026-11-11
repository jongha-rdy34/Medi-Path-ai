// Extract the response examples from contracts/openapi.yaml into src/mocks/examples.json.
// The MSW mock serves these verbatim (plan.md: contract-first, Mock uses the examples).
// Run: npm run mocks:sync   — a vitest test fails if the JSON drifts from the contract.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from 'yaml'

const here = dirname(fileURLToPath(import.meta.url))
export const CONTRACT = resolve(here, '../../contracts/openapi.yaml')
export const OUT = resolve(here, '../src/mocks/examples.json')

export function extractExamples(contractText) {
  const paths = parse(contractText).paths
  const json = (op, status) => op.responses[status].content['application/json']
  const msg = json(paths['/api/triage/sessions/{session_id}/messages'].post, '200').examples
  const result = json(paths['/api/triage/sessions/{session_id}/result'].get, '200').examples
  return {
    session: json(paths['/api/triage/sessions'].post, '201').example,
    message: { needsMoreInfo: msg.needsMoreInfo.value, resultReady: msg.resultReady.value, emergency: msg.emergency.value },
    result: { normal: result.normal.value, emergency: result.emergency.value },
    resultNotReady: json(paths['/api/triage/sessions/{session_id}/result'].get, '409').example,
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const examples = extractExamples(readFileSync(CONTRACT, 'utf8'))
  writeFileSync(OUT, JSON.stringify(examples, null, 2) + '\n')
  console.log(`wrote ${OUT}`)
}
