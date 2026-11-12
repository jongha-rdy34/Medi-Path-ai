"""Check hospital search against the REAL NMC and Kakao APIs (run by a person, never in CI).

    python manage.py hospital_live_check --env-file ../.env               # region + NMC counts
    python manage.py hospital_live_check --env-file ../.env --record      # + save responses
    python manage.py hospital_live_check --env-file ../.env --measure 20  # + latency (miss, N hits)

Keys come from the environment (DATA_GO_KR_SERVICE_KEY, KAKAO_REST_API_KEY) and are never printed
or saved. Sample points are fixed public places, not user locations. Uses about 20 NMC + 25 Kakao
calls without --measure. --env-file reads KEY=VALUE lines (works the same on Windows and macOS/Linux).
"""

from __future__ import annotations

import os
import statistics
import time
from pathlib import Path
from typing import ClassVar

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from hospitals import departments, http, kakao, nmc, service

# (label, lat, lng): fixed public places
PLACES = [
    ("gangnam_station", 37.4979, 127.0276),
    ("suwon_jangan_gu_office", 37.3039, 127.0101),  # 두 단어 시군구 확인용
    ("seongnam_pangyo_station", 37.3948, 127.1112),  # 두 단어 시군구 확인용
    ("sejong_city_hall", 36.4800, 127.2890),  # 시군구 없는 시도
    ("jeju_city_hall", 33.4996, 126.5312),
    ("chuncheon_city_hall", 37.8813, 127.7298),  # 강원특별자치도 vs 강원도 (review on #13)
    ("jeonju_city_hall", 35.8242, 127.1480),  # 전북특별자치도 vs 전라북도 (review on #13)
]
# Renamed provinces: Kakao gives the new name; NMC Q0 may only know the old one.
OLD_SIDO_NAMES = {"강원특별자치도": "강원도", "전북특별자치도": "전라북도"}
RECORD_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "recorded"


class Command(BaseCommand):
    help = (
        "Live check of NMC + Kakao for hospital search (T21). Needs real keys in the environment."
    )

    def add_arguments(self, parser):
        parser.add_argument("--record", action="store_true", help="save raw responses as fixtures")
        parser.add_argument("--measure", type=int, default=0, help="number of cache-hit runs")
        parser.add_argument("--env-file", help="read keys from this .env file (never printed)")

    requires_system_checks: ClassVar[list] = []  # no database needed

    def _load_env_file(self, path):
        if not Path(path).is_file():
            raise CommandError(f".env 파일을 찾을 수 없습니다: {Path(path).resolve()}")
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip().removeprefix("export ").strip()
            value = value.strip().strip('"').strip("'")
            if name and value and not os.environ.get(name):
                os.environ[name] = value

    def handle(self, *args, **opts):
        if opts["env_file"]:
            self._load_env_file(opts["env_file"])
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
        sidos = [region["sido"]]
        if region["sido"] in OLD_SIDO_NAMES:
            sidos.append(OLD_SIDO_NAMES[region["sido"]])
        sigungus = [region["sigungu"]]
        if region["sigungu"] and " " in region["sigungu"]:
            sigungus.append(region["sigungu"].split()[0])
        self.stdout.write(line)
        for q0 in sidos:
            for q1 in sigungus:
                try:
                    items = nmc.fetch_region(q0, q1, "D001")
                except http.SourceUnavailable as e:
                    self.stdout.write(f"      Q0={q0!r} Q1={q1!r} -> FAILED ({e.reason})")
                    continue
                same = sum(
                    1
                    for it in items
                    for d in range(1, 9)
                    if it.get(f"dutyTime{d}s")
                    and it.get(f"dutyTime{d}s") == it.get(f"dutyTime{d}c")
                )
                self.stdout.write(
                    f"      Q0={q0!r} Q1={q1!r} -> {len(items)}건 (open==close 요일 {same}개)"
                )

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
