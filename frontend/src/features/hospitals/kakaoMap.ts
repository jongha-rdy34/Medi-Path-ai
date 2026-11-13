// Kakao Maps JavaScript SDK wrapper (ported from prototypes/kakao-hospital-search/public/index.html).
// Docs: https://apis.map.kakao.com/web/guide/ (sdk.js?appkey=...&autoload=false, then kakao.maps.load)
// The JavaScript key is visible to browsers; it is protected by the site domains registered in the
// Kakao Developers console (http://localhost:5173 for development).

import type { Hospital } from './types'

export interface LatLng {
  lat: number
  lng: number
}

export interface MapView {
  setCenter(p: LatLng): void
  setRange(p: LatLng, radius: number): void
  setHospitals(items: Hospital[], onSelect: (id: string) => void): void
  focus(id: string): void
  onMapClick(cb: (p: LatLng) => void): void
  destroy(): void
}

// Minimal typings for the parts of the SDK used here.
interface KLatLng {
  getLat(): number
  getLng(): number
}
interface KOverlay {
  setMap(map: KMap | null): void
}
interface KMap {
  setCenter(p: KLatLng): void
  panTo(p: KLatLng): void
  relayout(): void
}
interface KCircle extends KOverlay {
  setPosition(p: KLatLng): void
  setRadius(r: number): void
}
interface KInfoWindow {
  setContent(c: HTMLElement): void
  open(map: KMap, marker: KOverlay): void
  close(): void
}
interface KakaoMaps {
  load(cb: () => void): void
  LatLng: new (lat: number, lng: number) => KLatLng
  Map: new (el: HTMLElement, opts: { center: KLatLng; level: number }) => KMap
  Marker: new (opts: { map: KMap; position: KLatLng; title?: string }) => KOverlay
  Circle: new (opts: Record<string, unknown>) => KCircle
  InfoWindow: new (opts: { zIndex: number }) => KInfoWindow
  event: {
    addListener(target: unknown, type: string, cb: (e: { latLng: KLatLng }) => void): void
  }
}
declare global {
  interface Window {
    kakao?: { maps: KakaoMaps }
  }
}

let loading: Promise<KakaoMaps> | null = null

function loadSdk(key: string): Promise<KakaoMaps> {
  if (window.kakao?.maps) {
    const maps = window.kakao.maps
    return new Promise((resolve) => maps.load(() => resolve(maps)))
  }
  loading ??= new Promise<KakaoMaps>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(key)}&autoload=false`
    script.async = true
    script.onload = () => {
      const maps = window.kakao?.maps
      if (!maps) return reject(new Error('카카오 지도 SDK를 읽지 못했어요.'))
      maps.load(() => resolve(maps))
    }
    script.onerror = () => {
      loading = null
      reject(new Error('카카오 지도 SDK를 불러오지 못했어요. 키와 등록된 도메인을 확인하세요.'))
    }
    document.head.appendChild(script)
  })
  return loading
}

function infoContent(h: Hospital): HTMLElement {
  // Text nodes only (no HTML strings), so names from the API cannot inject markup.
  const box = document.createElement('div')
  box.style.cssText = 'padding:6px 8px;font-size:12px;white-space:nowrap'
  const name = document.createElement('strong')
  name.textContent = h.name
  box.append(name)
  if (h.phone) box.append(document.createElement('br'), h.phone)
  return box
}

export async function createMapView(
  el: HTMLElement,
  center: LatLng,
  key: string | undefined = import.meta.env.VITE_KAKAO_MAP_JS_KEY,
): Promise<MapView> {
  if (!key) throw new Error('VITE_KAKAO_MAP_JS_KEY가 설정되지 않았어요.')
  const k = await loadSdk(key)
  const at = (p: LatLng) => new k.LatLng(p.lat, p.lng)

  const map = new k.Map(el, { center: at(center), level: 5 })
  const blue = { strokeColor: '#1a73e8', fillColor: '#1a73e8' }
  const me = new k.Circle({ ...blue, center: at(center), radius: 15, strokeWeight: 3, fillOpacity: 0.6, map })
  const range = new k.Circle({
    ...blue,
    center: at(center),
    radius: 3000,
    strokeWeight: 1,
    strokeOpacity: 0.5,
    fillOpacity: 0.05,
    map,
  })
  const info = new k.InfoWindow({ zIndex: 1 })
  let markers = new Map<string, { marker: KOverlay; hospital: Hospital }>()

  return {
    setCenter(p) {
      me.setPosition(at(p))
      map.setCenter(at(p))
    },
    setRange(p, radius) {
      range.setPosition(at(p))
      range.setRadius(radius)
    },
    setHospitals(items, onSelect) {
      info.close()
      markers.forEach(({ marker }) => marker.setMap(null))
      markers = new Map()
      for (const h of items) {
        const marker = new k.Marker({ map, position: at(h.location), title: h.name })
        k.event.addListener(marker, 'click', () => onSelect(h.hospital_id))
        markers.set(h.hospital_id, { marker, hospital: h })
      }
    },
    focus(id) {
      const found = markers.get(id)
      if (!found) return
      info.setContent(infoContent(found.hospital))
      info.open(map, found.marker)
      map.panTo(at(found.hospital.location))
    },
    onMapClick(cb) {
      k.event.addListener(map, 'click', (e) => cb({ lat: e.latLng.getLat(), lng: e.latLng.getLng() }))
    },
    destroy() {
      info.close()
      markers.forEach(({ marker }) => marker.setMap(null))
      markers.clear()
    },
  }
}
