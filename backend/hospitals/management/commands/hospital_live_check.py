"""Check hospital search against the REAL NMC and Kakao APIs (run by a person, never in CI).

    python manage.py hospital_live_check              # region + NMC counts for sample places
    python manage.py hospital_live_check --record     # also save responses to tests/fixtures/recorded/
    python manage.py hospital_live_check --measure 20 # latency: cache miss once, then N cache hits

Keys come from the environment (DATA_GO_KR_SERVICE_KEY, KAKAO_REST_API_KEY) and are never printed
or saved. Sample points are fixed public places, not user locations. Uses about 20 NMC + 25 Kakao
calls without --measure.
"""

from __future__ import annotations

import os
import statistics
import time
from pathlib import Path

from django.core.cache import cache
from django.core.management.base import BaseCommand

from hospitals import departments, http, kakao, nmc, service

# (label, lat, lng): fixed public places
PLACES = [
    ("gangnam_station", 37.4979, 127.0276),
    ("suwon_jangan_gu_office", 37.3039, 127.0101),  # 두 단어 시군구 확인용
    ("seongnam_pangyo_station", 37.3948, 127.1112),  # 두 단어 시군구 확인용
    ("sejong_city_hall", 36.4800, 127.2890),  # 시군구 없는 시도
    ("jeju_city_hall", 33.4996, 126.5312),
]
RECORD_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "recorded"


class Command(BaseCommand):
    help = (
        "Live check of NMC + Kakao for hospital search (T21). Needs real keys in the environment."
    )

    def add_arguments(self, parser):
        parser.add_argument("--record", action="store_true", help="save raw responses as fixtures")
        parser.add_argument("--measure", type=int, default=0, help="number of cache-hit runs")

    def handle(self, *args, **opts):
        for name in ("DATA_GO_KR_SERVICE_KEY", "KAKAO_REST_API_KEY"):
            ok = bool(os.environ.get(name, "").strip())
            self.stdout.write(f"{name}: {'set' if ok else 'MISSING'}")
            if not ok:
                return
        if opts["record"]:
            RECORD_DIR.mkdir(parents=True, exist_ok=True)
            self._wrap_http_for_recording()

        self.stdout.write("\n[1] region + NMC count (내과 D001)")
        for label, lat, lng in PLACES:
            self._check_place(label, lat, lng)

        if opts["measure"]:
            self._measure(opts["measure"])

    def _wrap_http_for_recording(self):
        real_get = http.get
        self._current = "misc"

        def recording_get(url, params, headers=None, timeout=http.DEFAULT_TIMEOUT):
            body = real_get(url, params, headers=headers, timeout=timeout)
            kind = (
                "kakao"
                if "kakao" in url
                else f"nmc_q1-{params.get('Q1', 'none')}_p{params.get('pageNo')}"
            )
            ext = "json" if "kakao" in url else "xml"
            (RECORD_DIR / f"{self._current}__{kind.replace(' ', '_')}.{ext}").write_bytes(body)
            return body

        http.get = recording_get

    def _check_place(self, label, lat, lng):
        self._current = label
        try:
            region = kakao.region_of(lat, lng)
        except http.SourceUnavailable as e:
            self.stdout.write(f"  {label}: kakao FAILED ({e.reason})")
            return
        if region is None:
            self.stdout.write(f"  {label}: no region")
            return
        line = f"  {label}: sido={region['sido']!r} sigungu={region['sigungu']!r}"
        candidates = [region["sigungu"]]
        if region["sigungu"] and " " in region["sigungu"]:
            candidates.append(region["sigungu"].split()[0])
        for q1 in candidates:
            try:
                n = len(nmc.fetch_region(region["sido"], q1, "D001"))
                line += f" | Q1={q1!r} -> {n}건"
            except http.SourceUnavailable as e:
                line += f" | Q1={q1!r} -> FAILED ({e.reason})"
        self.stdout.write(line)

    def _measure(self, runs):
        label, lat, lng = PLACES[0]
        q = service.Query(lat=lat, lng=lng, department=departments.lookup("01"), open_now=True)
        cache.clear()
        t0 = time.perf_counter()
        body = service.search(q)
        miss = (time.perf_counter() - t0) * 1000
        hits = []
        for _ in range(runs):
            t0 = time.perf_counter()
            service.search(q)
            hits.append((time.perf_counter() - t0) * 1000)
        p95 = statistics.quantiles(hits, n=20)[-1] if len(hits) >= 2 else hits[0]
        self.stdout.write(
            f"\n[2] latency at {label} (내과, 지금 진료 중), result total={body['total']}"
        )
        self.stdout.write(f"  cache miss: {miss:.0f} ms (Kakao + every NMC page)")
        self.stdout.write(
            f"  cache hit x{runs}: p50 {statistics.median(hits):.0f} ms, p95 {p95:.0f} ms "
            "(Kakao call each time, NMC from cache)"
        )
        for h in body["items"][:5]:
            self.stdout.write(
                f"    {h['distance_m']:>5} m  {h['name']}  open_now={h['is_open_now']}"
            )
