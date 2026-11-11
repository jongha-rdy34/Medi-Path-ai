import { describe, it, expect } from 'vitest'

import { mount } from '@vue/test-utils'
import App from '../App.vue'

describe('App', () => {
  it('renders the service title', () => {
    const wrapper = mount(App)
    expect(wrapper.find('h1').text()).toBe('MediPath')
    expect(wrapper.text()).toContain('증상에서 진료까지, 더 나은 의료 선택의 시작')
  })
})
