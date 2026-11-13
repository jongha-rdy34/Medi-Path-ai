# hospitals 테스트 fixture

- `nmc_*.xml`: 국립중앙의료원 `getHsptlMdcncListInfoInqire` 응답 **모양**을 활용가이드(서비스 버전 1.1) 예제에서 그대로 따서 만든 합성 데이터입니다. 기관명·주소·전화번호는 가짜입니다.
- `kakao_*.json`: Kakao `coord2regioncode` 응답 모양(개발 가이드 예제). `kakao_bundang.json`은 가이드 예제의 두 단어 시군구(`성남시 분당구`)입니다.
- `recorded/`: 2026-11-12 `hospital_live_check --record`로 실제 API에서 녹화한 응답을 줄인 것입니다(키·사용자 좌표 없음, 고정된 공공장소 좌표만). NMC는 공개된 기관 정보입니다.
  - `nmc_seoul_seocho_D001.xml`: 서초구 내과 290건 중 앞 40건(`totalCount`를 40으로 수정)
  - `nmc_gyeonggi_suwon_D001.xml`: 수원시 내과 506건 중 12건(18:30~18:30 기관 2곳 포함, `totalCount` 수정)
  - `kakao_*.json`: 강남역(→ 서초구), 수원 장안구청(두 단어 시군구), 춘천시청(강원특별자치도) 원본
