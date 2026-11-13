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

  it('replaces the hospital finder with 119 and the emergency-room finder in an emergency', () => {
    const w = mount(ResultView, { props: { result: emergency } })

    expect(w.find('[data-test="hospital-finder"]').exists()).toBe(false)
    expect(w.find('a[href="tel:119"]').exists()).toBe(true)
    expect(w.find('a[data-test="egen-link"]').attributes('href')).toMatch(/^https:\/\/www\.e-gen\.or\.kr/)
  })

  it('shows the note under a disease that is rare in Korea, and only there', () => {
    const rare: TriageResult = {
      ...normal,
      predictions: [
        { disease_id: 'hepatitis_a', disease_name_ko: 'A형 간염', probability: 0.32 },
        {
          disease_id: 'malaria',
          disease_name_ko: '말라리아',
          probability: 0.38,
          note: '국내에서는 드문 질환입니다. 최근 해외여행 이력이 있다면 의료진에게 꼭 알려 주세요.',
        },
        { disease_id: 'chicken_pox', disease_name_ko: '수두', probability: 0.08 },
      ],
    }
    const w = mount(ResultView, { props: { result: rare } })

    const notes = w.findAll('[data-test="prediction-note"]')
    expect(notes).toHaveLength(1)
    expect(notes[0]!.text()).toContain('해외여행')
    const items = w.findAll('[data-test="prediction"]')
    expect(items[1]!.find('[data-test="prediction-note"]').exists()).toBe(true)
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
