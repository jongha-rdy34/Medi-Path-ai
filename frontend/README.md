# frontend (web-frontend)

Vue 3 + Vite + TypeScript. `create-vue@3.24.0`로 생성했습니다(`--ts --vitest --eslint --bare`).

```bash
npm ci            # 의존성 설치(lockfile 그대로)
npm run dev       # 개발 서버 http://localhost:5173
npm run test      # Vitest 1회 실행
npm run check:lint  # oxlint + eslint (수정 없이 검사만, CI용)
npm run lint      # 자동 수정까지
npm run build     # 타입 검사 + 빌드
```

## 참고: lockfile 갱신
Node 22에 들어 있는 npm 10.9.x는 이 의존성 조합에서 `npm install` 중 피어 의존성 해석 오류
(`Cannot read properties of null (reading 'edgesOut')`)가 납니다. 의존성을 추가하거나 바꿀 때는 npm 11로 lockfile을 갱신하세요.
`npm ci`는 npm 10에서도 정상 동작합니다.

```bash
npx -y npm@11.6.2 install <패키지>
```
