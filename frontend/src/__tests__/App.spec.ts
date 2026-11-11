import { describe, it, expect } from 'vitest'

import { mount } from '@vue/test-utils'
import App from '../App.vue'

describe('App', () => {
  it('renders the service title', () => {
    const wrapper = mount(App)
    expect(wrapper.find('h1').text()).toBe('증상 기반 진료과·병원 안내')
  })
})
