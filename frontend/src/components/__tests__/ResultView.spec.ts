import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { TriageResult } from '../../api/types'
import examples from '../../mocks/examples.json'
import EmergencyBanner from '../EmergencyBanner.vue'
import ResultView from '../ResultView.vue'

const normal = examples.result.normal as TriageResult
const emergency = examples.result.emergency as TriageResult

describe('ResultView', () => {
  it('shows top-3 probabilities, the department and the disclaimer', () => {
    const w = mount(ResultView, { props: { result: normal } })

    expect(w.findAll('[data-test="prediction"]')).toHaveLength(3)
    expect(w.text()).toContain('위장염')
    expect(w.text()).toContain('52%')
    expect(w.text()).toContain('내과')
    expect(w.find('[data-test="disclaimer"]').text()).toContain('의학적 진단이 아니며')
  })

  it('passes the recommended department code to the hospital finder slot', () => {
    const w = mount(ResultView, { props: { result: normal } })

    expect(w.find('[data-test="hospital-finder"]').attributes('data-department')).toBe('01')
  })

  it('puts the emergency banner above everything else', () => {
    const w = mount(ResultView, { props: { result: emergency } })

    const html = w.html()
    expect(html.indexOf('data-test="emergency-banner"')).toBeLessThan(html.indexOf('data-test="prediction"'))
  })
})

describe('EmergencyBanner', () => {
  it('links to 119 and lists the reasons', () => {
    const w = mount(EmergencyBanner, { props: { notice: emergency.emergency_notice! } })

    expect(w.find('a[href="tel:119"]').exists()).toBe(true)
    expect(w.text()).toContain('가슴 통증과 호흡곤란')
  })
})
