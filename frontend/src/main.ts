import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'

// MSW mock (contract examples) in development unless VITE_USE_MOCK=false. T30 turns it off.
async function enableMocking() {
  if (!import.meta.env.DEV || import.meta.env.VITE_USE_MOCK === 'false') return
  const { worker } = await import('./mocks/browser')
  await worker.start({ onUnhandledFrame: 'bypass' })
}

enableMocking().then(() => {
  createApp(App).use(createPinia()).mount('#app')
})
