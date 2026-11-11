import 'dotenv/config';
import express from 'express';
import { XMLParser } from 'fast-xml-parser';

const KEY = process.env.DATA_GO_KR_SERVICE_KEY;
const PORT = process.env.PORT || 3000;
const BASE = 'https://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire';

// ── 조건 기준값 (서비스 정책에 맞게 조정) ─────────────────────────
const NIGHT_CUTOFF = 2000;   // 평일 중 하루라도 20:00 이후까지 진료하면 "야간 진료"
const CACHE_TTL = 6 * 60 * 60 * 1000; // 공공데이터는 저장 가능 → 시군구 단위 6시간 캐시

const parser = new XMLParser({ parseTagValue: false }); // "0900" 같은 값이 숫자로 바뀌지 않게
const cache = new Map();

// ── 공공데이터 API: 시군구(+진료과목) 전체를 페이지 돌며 수집 ──────────
async function fetchDistrict(sido, sigungu, dept) {
  const key = [sido, sigungu, dept].join('|');
  const hit = cache.get(key);
  if (hit && Date.now() - hit.at < CACHE_TTL) return hit.items;

  const all = [];
  let page = 1;
  let total = Infinity;
  while (all.length < total) {
    const params = new URLSearchParams({ serviceKey: KEY, pageNo: page, numOfRows: 1000 });
    if (sido) params.set('Q0', sido);
    if (sigungu) params.set('Q1', sigungu);
    if (dept) params.set('QD', dept);

    const xml = await (await fetch(`${BASE}?${params}`)).text();
    const j = parser.parse(xml);
    const r = j.response;
    if (!r) {
      // 인증키 오류 등은 <OpenAPI_ServiceResponse> 형태로 옴
      const msg = j.OpenAPI_ServiceResponse?.cmmMsgHeader?.returnAuthMsg || xml.slice(0, 200);
      throw new Error(`공공데이터 API 오류: ${msg}`);
    }
    if (!/^0+$/.test(String(r.header?.resultCode))) {
      throw new Error(`공공데이터 API 오류: ${r.header?.resultCode} ${r.header?.resultMsg}`);
    }
    total = Number(r.body?.totalCount || 0);
    let items = r.body?.items?.item ?? [];
    if (!Array.isArray(items)) items = [items];
    if (!items.length) break;
    all.push(...items);
    page++;
  }
  cache.set(key, { at: Date.now(), items: all });
  return all;
}

// "수원시 장안구"처럼 2단어 시군구가 0건이면 "수원시"로 한 번 더
async function fetchRegion(sido, sigungu, dept) {
  let items = await fetchDistrict(sido, sigungu, dept);
  if (!items.length && sigungu?.includes(' ')) {
    items = await fetchDistrict(sido, sigungu.split(' ')[0], dept);
  }
  return items;
}

// ── 시간 계산 (서버 시간대와 무관하게 한국 시간 기준) ────────────────
export function nowKST(date = new Date()) {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Seoul', weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(date).map(x => [x.type, x.value])
  );
  const day = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 }[p.weekday];
  return { day, hhmm: Number(p.hour) * 100 + Number(p.minute) };
}

const hours = (h, d) => {
  const s = h[`dutyTime${d}s`], c = h[`dutyTime${d}c`];
  return s && c ? { s: Number(s), c: Number(c) } : null;
};

export function isOpenAt(h, day, hhmm) {
  const t = hours(h, day);
  if (t) {
    if (t.c > t.s && hhmm >= t.s && hhmm < t.c) return true;
    if (t.c <= t.s && hhmm >= t.s) return true; // 자정 넘어가는 심야 진료
  }
  const prev = hours(h, day === 1 ? 7 : day - 1); // 전날 심야진료가 새벽까지 이어지는 경우
  return !!(prev && prev.c <= prev.s && hhmm < prev.c);
}

export function isNight(h) {
  return [1, 2, 3, 4, 5].some(d => {
    const t = hours(h, d);
    return t && (t.c >= NIGHT_CUTOFF || t.c <= t.s);
  });
}

const fmt = n => `${String(n).padStart(4, '0').slice(0, 2)}:${String(n).padStart(4, '0').slice(2)}`;
const DAY = ['', '월', '화', '수', '목', '금', '토', '일', '공휴일'];

function distanceM(lat1, lng1, lat2, lng2) {
  const R = 6371000, rad = Math.PI / 180;
  const a = Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lng2 - lng1) * rad) / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(a)));
}

// ── API ────────────────────────────────────────────────────────
const app = express();
app.use(express.static('public'));

app.get('/api/hospitals', async (req, res) => {
  try {
    const q = req.query;
    const lat = Number(q.lat), lng = Number(q.lng);
    const radius = Math.min(Number(q.radius) || 2000, 10000);
    const dept = q.dept || '';
    if (!lat || !lng || !q.sido) return res.status(400).json({ error: 'lat, lng, sido 필요' });

    const raw = await fetchRegion(q.sido, q.sigungu, dept);
    const { day, hhmm } = nowKST();

    let list = raw
      .filter(h => h.wgs84Lat && h.wgs84Lon)
      .map(h => {
        const t = hours(h, day);
        return {
          id: h.hpid,
          name: h.dutyName,
          type: h.dutyDivNam,
          addr: h.dutyAddr,
          tel: h.dutyTel1,
          lat: Number(h.wgs84Lat),
          lng: Number(h.wgs84Lon),
          distance: distanceM(lat, lng, Number(h.wgs84Lat), Number(h.wgs84Lon)),
          openNow: isOpenAt(h, day, hhmm),
          today: t ? `${fmt(t.s)}~${fmt(t.c)}` : '휴진',
          night: isNight(h),
          sat: !!hours(h, 6),
          sun: !!hours(h, 7),
          weekly: [1, 2, 3, 4, 5, 6, 7, 8].map(d => {
            const w = hours(h, d);
            return `${DAY[d]} ${w ? `${fmt(w.s)}~${fmt(w.c)}` : '휴진'}`;
          }),
        };
      })
      .filter(h => h.distance <= radius);

    if (q.openNow === '1') list = list.filter(h => h.openNow);
    if (q.night === '1') list = list.filter(h => h.night);
    if (q.weekend === '1') list = list.filter(h => h.sat || h.sun);

    list.sort((a, b) => a.distance - b.distance);
    res.json({ count: list.length, items: list.slice(0, 100) });
  } catch (e) {
    console.error(e);
    res.status(502).json({ error: e.message });
  }
});

if (process.argv[1]?.endsWith('server.js')) {
  if (!KEY) console.warn('⚠ .env 에 DATA_GO_KR_SERVICE_KEY 가 없습니다.');
  app.listen(PORT, () => console.log(`http://localhost:${PORT}`));
}
export { app, cache };
