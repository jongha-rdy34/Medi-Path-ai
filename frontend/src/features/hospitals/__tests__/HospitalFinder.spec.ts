import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import HospitalFinder from '../HospitalFinder.vue'
import type { LatLng, MapView } from '../kakaoMap'
import type { Hospital, HospitalSearchResponse } from '../types'

type FetchFn = (url: string) => Promise<{ ok: boolean; status: number; json: () => Promise<unknown> }>

// --- fakes ---------------------------------------------------------------------------------
const fakeMap = vi.hoisted(() => ({
  setCenter: vi.fn<(p: LatLng) => void>(),
  setRange: vi.fn<(p: LatLng, radius: number) => void>(),
  setHospitals: vi.fn<(items: Hospital[], onSelect: (id: string) => void) => void>(),
  focus: vi.fn<(id: string) => void>(),
  clickHandler: null as null | ((p: LatLng) => void),
  onMapClick(cb: (p: LatLng) => void) {
    this.clickHandler = cb
  },
  destroy: vi.fn<() => void>(),
}))
const mapState = vi.hoisted(() => ({ fail: false }))

vi.mock('../kakaoMap', () => ({
  createMapView: vi.fn<() => Promise<MapView>>(async () => {
    if (mapState.fail) throw new Error('VITE_KAKAO_MAP_JS_KEY가 설정되지 않았어요.')
    return fakeMap
  }),
}))

function response(over: Partial<HospitalSearchResponse> = {}): HospitalSearchResponse {
  return {
    total: 2,
    region: { sido: '서울특별시', sigungu: '서초구' },
    department: { code: '01', name: '내과', filter_applied: true, message: null },
    evaluated_at: '2026-11-13T12:00:10+09:00',
    notice: '진료시간은 바뀔 수 있으니 방문 전에 전화로 확인하세요. 응급 상황이면 119에 연락하세요.',
    items: [
      {
        hospital_id: 'A1',
        name: '케이내과의원',
        type: '의원',
        address: '서울특별시 서초구 강남대로 415',
        phone: '02-593-7582',
        location: { lat: 37.4995, lng: 127.0263 },
        distance_m: 216,
        department: '01',
        opening_hours: [
          { day: 'mon', open: '09:30', close: '18:30', crosses_midnight: false },
          { day: 'sat', open: '10:00', close: '14:00', crosses_midnight: false },
        ],
        is_open_now: true,
        has_night_hours: false,
        has_weekend_hours: true,
        has_emergency_room: null,
      },
      {
        hospital_id: 'A2',
        name: '심야내과의원',
        type: '의원',
        address: '서울특별시 강남구 예시로 2',
        phone: null,
        location: { lat: 37.5021, lng: 127.0352 },
        distance_m: 1453,
        department: '01',
        opening_hours: [{ day: 'fri', open: '19:00', close: '02:00', crosses_midnight: true }],
        is_open_now: false,
        has_night_hours: true,
        has_weekend_hours: false,
        has_emergency_room: null,
      },
    ],
    ...over,
  }
}

let fetchMock: ReturnType<typeof vi.fn<FetchFn>>
function replyWith(body: unknown, status = 200) {
  fetchMock.mockResolvedValue({ ok: status < 400, status, json: async () => body })
}

const GANGNAM = { coords: { latitude: 37.4979, longitude: 127.0276 } }
function geolocation(result: 'ok' | 'denied' | 'missing') {
  const getCurrentPosition = vi.fn<(ok: PositionCallback, err: PositionErrorCallback) => void>((ok, err) => {
    if (result === 'ok') ok(GANGNAM as GeolocationPosition)
    else err({ code: 1, PERMISSION_DENIED: 1 } as GeolocationPositionError)
  })
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value: result === 'missing' ? undefined : { getCurrentPosition },
  })
  return getCurrentPosition
}

function lastQuery(): URLSearchParams {
  const calls = fetchMock.mock.calls
  const url = String(calls[calls.length - 1]?.[0])
  return new URL(url, 'http://test').searchParams
}

async function mountFinder(department = '01') {
  const w = mount(HospitalFinder, { props: { department } })
  await flushPromises()
  return w
}

beforeEach(() => {
  fetchMock = vi.fn<FetchFn>()
  vi.stubGlobal('fetch', fetchMock)
  replyWith(response())
  mapState.fail = false
  fakeMap.clickHandler = null
  vi.clearAllMocks()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

// --- tests -----------------------------------------------------------------------------------
describe('HospitalFinder', () => {
  it('keeps the slot markers the result screen and e2e rely on', async () => {
    geolocation('ok')
    const w = await mountFinder('11')

    const root = w.find('[data-test="hospital-finder"]')
    expect(root.exists()).toBe(true)
    expect(root.attributes('data-department')).toBe('11')
    expect((w.find('select[name="department"]').element as HTMLSelectElement).value).toBe('11')
  })

  it('searches around the browser location with the recommended department', async () => {
    geolocation('ok')
    const w = await mountFinder()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const q = lastQuery()
    expect(String(fetchMock.mock.calls[0]?.[0])).toMatch(/^\/api\/hospitals\?/)
    expect(q.get('lat')).toBe('37.4979')
    expect(q.get('lng')).toBe('127.0276')
    expect(q.get('department')).toBe('01')
    expect(q.get('radius')).toBe('3000')
    expect(q.has('open_now')).toBe(false)

    const items = w.findAll('[data-test="hospital"]')
    expect(items).toHaveLength(2)
    expect(items[0]?.text()).toContain('케이내과의원')
    expect(items[0]?.text()).toContain('216m')
    expect(items[0]?.text()).toContain('진료 중')
    expect(items[1]?.text()).toContain('1.5km')
    expect(items[1]?.text()).toContain('야간')
    expect(fakeMap.setHospitals).toHaveBeenCalled()
  })

  it('shows the notice, region, total and evaluation time above the list', async () => {
    geolocation('ok')
    const w = await mountFinder()

    expect(w.find('[data-test="notice"]').text()).toContain('119')
    const meta = w.find('[data-test="search-meta"]').text()
    expect(meta).toContain('서초구 주변 3km')
    expect(meta).toContain('12:00 기준')
    expect(meta).toContain('2곳')
  })

  it('shows phone links and weekly hours, past-midnight hours marked', async () => {
    geolocation('ok')
    const w = await mountFinder()
    const [first, second] = w.findAll('[data-test="hospital"]')

    expect(first?.find('a[href="tel:02-593-7582"]').exists()).toBe(true)
    expect(first?.text()).toContain('월 09:30~18:30')
    expect(second?.text()).toContain('금 19:00~다음날 02:00')
  })

  it.each([
    ['open_now', 'open-now'],
    ['night', 'night'],
    ['weekend', 'weekend'],
  ])('searches again with %s when its toggle is turned on', async (param, testId) => {
    geolocation('ok')
    const w = await mountFinder()

    await w.find(`[data-test="toggle-${testId}"]`).setValue(true)
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(lastQuery().get(param)).toBe('true')
  })

  it('lets the user change the department and radius', async () => {
    geolocation('ok')
    const w = await mountFinder()

    await w.find('select[name="department"]').setValue('11')
    await flushPromises()
    expect(lastQuery().get('department')).toBe('11')

    await w.find('select[name="radius"]').setValue('5000')
    await flushPromises()
    expect(lastQuery().get('radius')).toBe('5000')
  })

  it('follows a new recommended department from the parent', async () => {
    geolocation('ok')
    const w = await mountFinder()

    await w.setProps({ department: '12' })
    await flushPromises()

    expect(lastQuery().get('department')).toBe('12')
  })

  it('without location permission: explains, does not search, then searches where the map is clicked', async () => {
    geolocation('denied')
    const w = await mountFinder()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(w.find('[data-test="location-message"]').text()).toContain('지도를 눌러')

    fakeMap.clickHandler?.({ lat: 37.5, lng: 127.03 })
    await flushPromises()

    expect(lastQuery().get('lat')).toBe('37.5')
    expect(w.find('[data-test="location-message"]').text()).toContain('지도에서 고른 위치')
  })

  it('works as a list when the map cannot load (no Kakao key)', async () => {
    mapState.fail = true
    geolocation('ok')
    const w = await mountFinder()

    const mapError = w.find('[data-test="map-error"]').text()
    expect(mapError).toContain('지도를 불러오지 못했어요')
    expect(mapError).not.toContain('VITE_') // no developer settings shown to users
    expect(w.findAll('[data-test="hospital"]')).toHaveLength(2)
  })

  it('without permission and without a map, asks to allow location instead of clicking the map', async () => {
    mapState.fail = true
    geolocation('denied')
    const w = await mountFinder()

    const msg = w.find('[data-test="location-message"]').text()
    expect(msg).not.toContain('지도를 눌러')
    expect(msg).toContain('위치 권한을 허용')
  })

  it('shows the department message when the department filter could not be applied', async () => {
    geolocation('ok')
    replyWith(
      response({
        department: {
          code: '00',
          name: '일반의',
          filter_applied: false,
          message: '일반의는 병원 정보에서 진료과로 구분되지 않아 근처 병원 전체를 보여 드려요.',
        },
      }),
    )
    const w = await mountFinder('00')

    expect(w.find('[data-test="department-message"]').text()).toContain('근처 병원 전체')
  })

  it('says so when nothing matches', async () => {
    geolocation('ok')
    replyWith(response({ total: 0, items: [] }))
    const w = await mountFinder()

    expect(w.find('[data-test="empty"]').text()).toContain('조건에 맞는 병원이 없어요')
  })

  it.each([
    [422, { code: 'out_of_service_area', message: '이 위치에서는 병원을 찾을 수 없습니다.' }, '이 위치에서는'],
    [503, { code: 'hospital_source_unavailable', message: '병원 정보를 잠시 불러올 수 없습니다.' }, '잠시'],
  ])('shows the server message on %i', async (status, body, text) => {
    geolocation('ok')
    replyWith(body, status)
    const w = await mountFinder()

    expect(w.find('[data-test="search-error"]').text()).toContain(text)
    expect(w.findAll('[data-test="hospital"]')).toHaveLength(0)
  })

  it('focuses the marker when a list item is clicked', async () => {
    geolocation('ok')
    const w = await mountFinder()

    await w.findAll('[data-test="hospital"]')[1]?.trigger('click')

    expect(fakeMap.focus).toHaveBeenCalledWith('A2')
  })

  it('does not keep the location anywhere', async () => {
    geolocation('ok')
    await mountFinder()

    expect(JSON.stringify({ ...localStorage })).not.toContain('37.4979')
    expect(JSON.stringify({ ...sessionStorage })).not.toContain('37.4979')
  })
})
