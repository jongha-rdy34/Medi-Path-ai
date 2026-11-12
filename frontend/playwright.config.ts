// E2E: the real frontend against the Django backend with stub AI clients
// (backend/config/e2e_settings.py). Docs: playwright.dev "Web server" (webServer).
// Run: npm run e2e   (needs the backend's Python deps; set E2E_PYTHON to that interpreter)
import { defineConfig, devices } from '@playwright/test'

const python = process.env.E2E_PYTHON ?? 'python'
const BACKEND = 'http://127.0.0.1:8100'
const FRONTEND = 'http://127.0.0.1:5174'

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: FRONTEND, ...devices['iPhone SE'], browserName: 'chromium', trace: 'off' },
  webServer: [
    {
      name: 'backend',
      cwd: '../backend',
      command: `${python} manage.py migrate --noinput && ${python} manage.py runserver 127.0.0.1:8100 --noreload`,
      url: `${BACKEND}/api/health`,
      env: { DJANGO_SETTINGS_MODULE: 'config.e2e_settings' },
      reuseExistingServer: !process.env.CI,
    },
    {
      name: 'frontend',
      command: 'npx vite --host 127.0.0.1 --port 5174 --strictPort',
      url: FRONTEND,
      env: { VITE_API_PROXY: BACKEND },
      reuseExistingServer: !process.env.CI,
    },
  ],
})
