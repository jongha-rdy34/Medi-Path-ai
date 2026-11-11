import { describe, it, expect } from 'vitest'

import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import App from '../App.vue'

describe('App', () => {
  it('renders the service title, the symptom input and the medical notice', () => {
    const wrapper = mount(App, { global: { plugins: [createPinia()] } })
    expect(wrapper.find('h1').text()).toBe('MediPath')
    expect(wrapper.text()).toContain('증상에서 진료까지, 더 나은 의료 선택의 시작')
    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.find('[data-test="disclaimer"]').text()).toContain('의학적 진단이 아니며')
  })
})
