# hospitals 테스트 fixture

- `nmc_*.xml`: 국립중앙의료원 `getHsptlMdcncListInfoInqire` 응답 **모양**을 활용가이드(서비스 버전 1.1) 예제에서 그대로 따서 만든 합성 데이터입니다. 기관명·주소·전화번호는 가짜입니다.
- `kakao_*.json`: Kakao `coord2regioncode` 응답 모양(개발 가이드 예제). `kakao_bundang.json`은 가이드 예제의 두 단어 시군구(`성남시 분당구`)입니다.
- `recorded/`: `python manage.py hospital_live_check --record`로 실제 API에서 녹화한 응답을 두는 곳입니다(키·사용자 좌표 없음, 고정된 공공장소 좌표만). 녹화 전에는 비어 있습니다.
