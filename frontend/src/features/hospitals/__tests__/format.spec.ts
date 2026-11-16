import { describe, expect, it } from 'vitest'

import { formatDistance, formatHours, formatTime, openBadge } from '../format'

describe('format', () => {
  it('formats distance in m below 1 km and km above', () => {
    expect(formatDistance(216)).toBe('216m')
    expect(formatDistance(999)).toBe('999m')
    expect(formatDistance(1453)).toBe('1.5km')
    expect(formatDistance(3000)).toBe('3km')
  })

  it('formats one day of hours, marking past-midnight closing', () => {
    expect(formatHours({ day: 'mon', open: '09:30', close: '18:30', crosses_midnight: false })).toBe(
      '월 09:30~18:30',
    )
    expect(formatHours({ day: 'fri', open: '19:00', close: '02:00', crosses_midnight: true })).toBe(
      '금 19:00~다음날 02:00',
    )
    expect(formatHours({ day: 'holiday', open: '13:00', close: '18:00', crosses_midnight: false })).toBe(
      '공휴일 13:00~18:00',
    )
  })

  it('shows evaluated_at as Korea time HH:MM', () => {
    expect(formatTime('2026-11-13T12:00:10+09:00')).toBe('12:00')
    expect(formatTime('2026-11-13T03:05:00Z')).toBe('12:05')
  })

  it('labels open state, unknown when hours are missing', () => {
    expect(openBadge(true)).toEqual({ label: '진료 중', tone: 'open' })
    expect(openBadge(false)).toEqual({ label: '진료 종료', tone: 'closed' })
    expect(openBadge(null)).toEqual({ label: '시간 정보 없음', tone: 'unknown' })
  })
})
