import type { Day, OpeningHours } from './types'

export const DAY_LABELS: Record<Day, string> = {
  mon: '월',
  tue: '화',
  wed: '수',
  thu: '목',
  fri: '금',
  sat: '토',
  sun: '일',
  holiday: '공휴일',
}

export function formatDistance(meters: number): string {
  if (meters < 1000) return `${meters}m`
  const km = meters / 1000
  return Number.isInteger(km) ? `${km}km` : `${km.toFixed(1)}km`
}

export function formatHours(h: OpeningHours): string {
  const close = h.crosses_midnight ? `다음날 ${h.close}` : h.close
  return `${DAY_LABELS[h.day]} ${h.open}~${close}`
}

/** HH:MM in Korea time, whatever offset the server used. */
export function formatTime(iso: string): string {
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(iso))
}

export type BadgeTone = 'open' | 'closed' | 'unknown'

export function openBadge(isOpen: boolean | null): { label: string; tone: BadgeTone } {
  if (isOpen === null) return { label: '시간 정보 없음', tone: 'unknown' }
  return isOpen ? { label: '진료 중', tone: 'open' } : { label: '진료 종료', tone: 'closed' }
}
