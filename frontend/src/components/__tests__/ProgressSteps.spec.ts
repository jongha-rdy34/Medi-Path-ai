import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ProgressSteps from '../ProgressSteps.vue'

describe('ProgressSteps', () => {
  it('marks the current step and announces it', () => {
    const w = mount(ProgressSteps, { props: { step: 'analyze' } })

    const items = w.findAll('li')
    expect(items.map((li) => li.text())).toEqual(['증상 정리 중', '질환 분석 중', '결과'])
    expect(w.find('[aria-current="step"]').text()).toBe('질환 분석 중')
    expect(w.attributes('aria-live')).toBe('polite')
  })
})
