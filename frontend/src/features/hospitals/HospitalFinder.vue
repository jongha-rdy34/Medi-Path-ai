<script setup lang="ts">
// <HospitalFinder :department="권장 진료과 코드" /> (T21 PR 4, @ley-21).
// Self-contained: location, filters, GET /api/hospitals, list and Kakao map. Ported from
// prototypes/kakao-hospital-search/public/index.html. The location is kept only in memory for
// the current search (SPEC 6): never stored, never sent anywhere but our own API.
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, useTemplateRef, watch } from 'vue'

import { HospitalSearchError, searchHospitals } from './api'
import { DEPARTMENTS } from './departments'
import { formatDistance, formatHours, formatTime, openBadge } from './format'
import { createMapView, type LatLng, type MapView } from './kakaoMap'
import type { HospitalSearchResponse } from './types'

const props = defineProps<{ department: string }>()

const RADII = [1000, 3000, 5000, 10000]
const SEOUL_CITY_HALL: LatLng = { lat: 37.5665, lng: 126.978 } // map start only, never searched

const department = ref(props.department)
const radius = ref(3000)
const openNow = ref(false)
const night = ref(false)
const weekend = ref(false)

const location = shallowRef<LatLng | null>(null)
const locationSource = ref<'pending' | 'gps' | 'map' | 'failed'>('pending')
const locationError = ref('')
const mapError = ref('')

const result = shallowRef<HospitalSearchResponse | null>(null)
const loading = ref(false)
const searchError = ref('')
const selectedId = ref<string | null>(null)

const mapEl = useTemplateRef<HTMLElement>('mapEl')
let map: MapView | null = null
let inFlight: AbortController | null = null

const locationMessage = computed(() => {
  if (locationSource.value === 'pending') return '현재 위치를 확인하는 중이에요.'
  if (locationSource.value === 'map') return '지도에서 고른 위치 기준으로 찾았어요. 지도를 다시 눌러 바꿀 수 있어요.'
  if (locationSource.value === 'failed') {
    return mapError.value
      ? `${locationError.value} 브라우저에서 위치 권한을 허용한 뒤 '내 위치 다시 찾기'를 눌러 주세요.`
      : `${locationError.value} 지도를 눌러 위치를 정해 주세요.`
  }
  return ''
})

const searchMeta = computed(() => {
  const r = result.value
  if (!r) return ''
  const place = [r.region.sido, r.region.sigungu].filter(Boolean).join(' ')
  return `${place} 주변 ${formatDistance(radius.value)} · ${formatTime(r.evaluated_at)} 기준 · ${r.total}곳`
})

async function search() {
  const here = location.value
  if (!here) return
  inFlight?.abort()
  const controller = new AbortController()
  inFlight = controller
  loading.value = true
  searchError.value = ''
  try {
    const res = await searchHospitals(
      {
        lat: here.lat,
        lng: here.lng,
        department: department.value,
        radius: radius.value,
        open_now: openNow.value,
        night: night.value,
        weekend: weekend.value,
      },
      controller.signal,
    )
    result.value = res
    selectedId.value = null
    map?.setHospitals(res.items, select)
  } catch (e) {
    if ((e as Error).name === 'AbortError') return
    result.value = null
    map?.setHospitals([], select)
    searchError.value =
      e instanceof HospitalSearchError ? e.message : '병원 정보를 불러오지 못했어요. 잠시 후 다시 시도하세요.'
  } finally {
    if (inFlight === controller) loading.value = false
  }
}

function setLocation(p: LatLng, source: 'gps' | 'map') {
  location.value = p
  locationSource.value = source
  map?.setCenter(p)
  map?.setRange(p, radius.value)
  search()
}

const GEO_ERRORS: Record<number, string> = {
  1: '위치 권한이 거부되었어요.',
  2: '현재 위치를 알 수 없어요.',
  3: '위치를 확인하는 데 시간이 너무 오래 걸렸어요.',
}

function locate() {
  if (!navigator.geolocation) {
    locationSource.value = 'failed'
    locationError.value = '이 브라우저는 위치 확인을 지원하지 않아요.'
    return
  }
  locationSource.value = 'pending'
  navigator.geolocation.getCurrentPosition(
    (pos) => setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }, 'gps'),
    (err) => {
      locationSource.value = 'failed'
      locationError.value = GEO_ERRORS[err.code] ?? '현재 위치를 확인하지 못했어요.'
    },
    { timeout: 15000, maximumAge: 60000 },
  )
}

function select(id: string) {
  selectedId.value = id
  map?.focus(id)
}

watch(
  () => props.department,
  (code) => {
    department.value = code
  },
)
watch([department, openNow, night, weekend], search)
watch(radius, (r) => {
  if (location.value) map?.setRange(location.value, r)
  search()
})

onMounted(async () => {
  locate()
  if (!mapEl.value) return
  try {
    map = await createMapView(mapEl.value, location.value ?? SEOUL_CITY_HALL)
    map.onMapClick((p) => setLocation(p, 'map'))
    if (location.value) {
      map.setCenter(location.value)
      map.setRange(location.value, radius.value)
    }
    if (result.value) map.setHospitals(result.value.items, select)
  } catch (e) {
    console.warn('[HospitalFinder] map unavailable:', (e as Error).message) // for developers only
    mapError.value = '지도를 불러오지 못했어요. 목록은 그대로 볼 수 있어요.'
  }
})

onBeforeUnmount(() => {
  inFlight?.abort()
  map?.destroy()
})
</script>

<template>
  <section class="hospital-finder" data-test="hospital-finder" :data-department="props.department">
    <header class="head">
      <h3>주변 병원</h3>
      <button type="button" class="locate" @click="locate">내 위치 다시 찾기</button>
    </header>

    <div class="controls">
      <label>
        진료과
        <select v-model="department" name="department">
          <option v-for="d in DEPARTMENTS" :key="d.code" :value="d.code">{{ d.name }}</option>
        </select>
      </label>
      <label>
        반경
        <select v-model.number="radius" name="radius">
          <option v-for="r in RADII" :key="r" :value="r">{{ formatDistance(r) }}</option>
        </select>
      </label>
      <label><input v-model="openNow" type="checkbox" data-test="toggle-open-now" /> 지금 진료 중</label>
      <label><input v-model="night" type="checkbox" data-test="toggle-night" /> 야간 진료 (평일 20시 이후)</label>
      <label><input v-model="weekend" type="checkbox" data-test="toggle-weekend" /> 주말 진료</label>
    </div>

    <p v-if="locationMessage" class="status" data-test="location-message">{{ locationMessage }}</p>
    <p v-if="mapError" class="status warn" data-test="map-error">{{ mapError }}</p>

    <div class="body">
      <div ref="mapEl" class="map" data-test="map" />

      <div class="list">
        <template v-if="result">
          <p class="notice" data-test="notice">{{ result.notice }}</p>
          <p v-if="result.department.message" class="status" data-test="department-message">
            {{ result.department.message }}
          </p>
          <p class="meta" data-test="search-meta">{{ searchMeta }}</p>
        </template>
        <p v-if="loading" class="status">병원을 찾는 중이에요…</p>
        <p v-if="searchError" class="status warn" data-test="search-error">{{ searchError }}</p>
        <p v-if="result && !result.items.length && !loading" class="status" data-test="empty">
          조건에 맞는 병원이 없어요. 반경을 넓히거나 조건을 줄여 보세요.
        </p>

        <ul v-if="result && !searchError">
          <li
            v-for="h in result.items"
            :key="h.hospital_id"
            data-test="hospital"
            :class="{ selected: h.hospital_id === selectedId }"
            @click="select(h.hospital_id)"
          >
            <div class="name">{{ h.name }}</div>
            <div class="badges">
              <span :class="['badge', openBadge(h.is_open_now).tone]">{{ openBadge(h.is_open_now).label }}</span>
              <span v-if="h.has_night_hours" class="badge night">야간</span>
              <span v-if="h.has_weekend_hours" class="badge weekend">주말</span>
            </div>
            <div class="sub">{{ formatDistance(h.distance_m) }} · {{ h.type }}</div>
            <div class="sub">{{ h.address }}</div>
            <a v-if="h.phone" class="phone" :href="`tel:${h.phone}`" @click.stop>{{ h.phone }}</a>
            <details v-if="h.opening_hours.length" @click.stop>
              <summary>요일별 진료시간</summary>
              <ul class="hours">
                <li v-for="d in h.opening_hours" :key="d.day">{{ formatHours(d) }}</li>
              </ul>
            </details>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hospital-finder {
  border: 1px solid #ddd;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
h3 {
  margin: 0;
  font-size: 17px;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  font-size: 14px;
}
.status {
  margin: 0;
  font-size: 13px;
  color: #555;
}
.warn {
  color: #b00020;
}
.notice {
  margin: 0 0 4px;
  padding: 8px;
  border-radius: 8px;
  background: #fff8e1;
  font-size: 13px;
}
.meta {
  margin: 0 0 4px;
  font-size: 12px;
  color: #666;
}
.body {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}
@media (min-width: 720px) {
  .body {
    grid-template-columns: 3fr 2fr;
  }
}
.map {
  min-height: 320px;
  border-radius: 8px;
  background: #f2f2f2;
}
.list {
  max-height: 480px;
  overflow-y: auto;
}
.list > ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.list > ul > li {
  padding: 10px 4px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}
.list > ul > li.selected {
  background: #eef4ff;
}
.name {
  font-weight: 600;
}
.badges {
  margin: 2px 0;
}
.badge {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 8px;
  margin-right: 4px;
  color: #fff;
}
.open {
  background: #1e9e50;
}
.closed {
  background: #888;
}
.unknown {
  background: #bbb;
}
.night {
  background: #4b4bc8;
}
.weekend {
  background: #e08a00;
}
.sub {
  font-size: 12px;
  color: #666;
}
.phone {
  font-size: 12px;
}
details {
  font-size: 12px;
  margin-top: 4px;
}
.hours {
  margin: 4px 0 0;
  padding-left: 16px;
}
</style>
