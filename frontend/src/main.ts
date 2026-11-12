import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'

// The real API is the default (T30). VITE_USE_MOCK=true serves the contract examples with MSW
// in development, e.g. to work on screens without the backend.
async function enableMocking() {
  if (!import.meta.env.DEV || import.meta.env.VITE_USE_MOCK !== 'true') return
  const { worker } = await import('./mocks/browser')
  await worker.start({ onUnhandledFrame: 'bypass' })
}

enableMocking().then(() => {
  createApp(App).use(createPinia()).mount('#app')
})
