# GitHub 저장소 설정 절차

저장소: **https://github.com/jongha-rdy34/Medi-Path-ai** (public, 소유자 `@jongha-rdy34`)

public 저장소라서 GitHub Free에서도 브랜치 보호(룰셋)와 CODEOWNERS를 쓸 수 있습니다.
명령 예시는 [GitHub CLI(`gh`)](https://cli.github.com/) 기준입니다. 먼저 `gh auth login`으로 로그인하세요.
API 본문 필드는 GitHub REST API 명세(github/rest-api-description)에서 확인했습니다.

> **public 저장소 주의**: Kaggle·AI Hub 원본 데이터(`data/raw/`), `.env`, API 키는 절대 커밋하지 않습니다. `.gitignore`가 막고 있고, 5단계의 push protection이 한 번 더 막습니다.

---

## 1단계. 원격 연결과 push

저장소 루트(`SPEC.md`가 있는 폴더)에서 실행합니다.

```bash
git remote add origin https://github.com/jongha-rdy34/Medi-Path-ai.git
```

```bash
git push -u origin main
```

원격에 이미 커밋이 있으면(README 등) 덮어쓰지 말고 합친 뒤 push합니다.

```bash
git pull --rebase origin main
```

## 2단계. 팀원을 collaborator로 초대 · 완료(`ley-21`, 2026-11-11)

```bash
gh api -X PUT repos/jongha-rdy34/Medi-Path-ai/collaborators/<팀원_ID> -f permission=push
```

팀원은 메일 또는 https://github.com/notifications 에서 초대를 수락합니다.

## 3단계. CODEOWNERS 트랙 담당자 채우기

`.github/CODEOWNERS`의 기본 담당자는 `@jongha-rdy34`입니다. A/B 배정이 정해지면 자리표시자 `@A_GITHUB_ID`, `@B_GITHUB_ID`를 실제 아이디로 바꾸고 PR로 올립니다.

```bash
sed -i 's/@A_GITHUB_ID/@<A_ID>/g; s/@B_GITHUB_ID/@<B_ID>/g' .github/CODEOWNERS
```

(macOS는 `sed -i ''`를 씁니다.)

## 4단계. `main` 룰셋 (PR 필수, 승인 0명, `ci-ok` 필수)

**운영 방식(2026-11-11)**: 에이전트는 브랜치만 push하고 보고합니다. 사용자가 변경을 확인한 뒤 PR을 만들어 머지합니다(`AGENTS.md` 3절).
두 명 팀이라 본인 PR을 스스로 승인할 수 없으므로 **필수 승인 수는 0**으로 두고, 사용자 확인이 리뷰 역할을 합니다. 직접 push, 강제 push, 삭제는 룰셋이 막습니다.

웹: **Settings → Rules → Rulesets → New ruleset → New branch ruleset**
- Ruleset name `main-protection`, Enforcement status **Active**
- Target branches: **Include default branch**
- [x] Restrict deletions
- [x] Block force pushes
- [x] Require a pull request before merging → Required approvals **0**
- [x] Require status checks to pass → **Add checks** → `ci-ok`
- Bypass list는 비워 둡니다(소유자도 규칙을 따름)

같은 설정을 CLI로 할 때(`POST /repos/{owner}/{repo}/rulesets`):

```bash
gh api -X POST repos/jongha-rdy34/Medi-Path-ai/rulesets --input - <<'JSON'
{
  "name": "main-protection",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [{ "context": "ci-ok" }]
      }
    }
  ]
}
JSON
```

### 왜 `ci-ok` 하나만 필수인가
CI(`.github/workflows/ci.yml`)는 바뀐 경로의 잡만 실행하고, 마지막 `ci-ok` 잡이 결과를 모읍니다.
경로별 잡을 필수로 등록하면, 그 경로를 안 건드린 PR이 "대기 중"으로 막힐 수 있습니다.
`ci-ok`는 CI가 한 번 실행된 뒤에야 웹 설정 화면의 검색 목록에 나타납니다.

## 5단계. Secret scanning과 push protection 켜기

웹: **Settings → Advanced Security**(또는 Code security) → **Secret Protection**과 **Push protection**을 Enable

CLI(`PATCH /repos/{owner}/{repo}`의 `security_and_analysis`):

```bash
gh api -X PATCH repos/jongha-rdy34/Medi-Path-ai --input - <<'JSON'
{
  "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" }
  }
}
JSON
```

## 6단계. 라벨(모듈 ID)

이슈 1개 = 태스크 1개로 등록하고 모듈 ID 라벨을 답니다(SPEC 7절).

```bash
for m in api-contract platform data-foundation triage-model llm-assistant hospital-search backend-api web-frontend data-pipeline; do gh label create "$m" --repo jongha-rdy34/Medi-Path-ai --force; done
```

## 7단계. agent-skills 플러그인 (두 사람 모두)

저장소의 `.claude/settings.json`에 마켓플레이스와 플러그인이 등록돼 있습니다. clone한 폴더에서 Claude Code를 열고 **폴더 신뢰(trust)** 를 수락한 뒤:

```
/plugin marketplace add addyosmani/agent-skills
/plugin install agent-skills@addy-agent-skills
```

(`enabledPlugins`는 켜기만 하고 설치는 하지 않으므로 각자 한 번 설치해야 합니다. 출처: https://code.claude.com/docs/en/settings-reference.md `enabledPlugins`)

## 8단계. 룰셋 검증 (4단계 설정 후)

1. **직접 push가 거부되는지**: 아무 커밋이나 `main`에 바로 push해 봅니다.

```bash
git checkout main && git commit --allow-empty -m "chore: ruleset check" && git push origin main
```

**기대 결과**: `GH013: Repository rule violations found` 등으로 거부됩니다. 확인 후 로컬 커밋을 되돌립니다.

```bash
git reset --hard origin/main
```

2. **`ci-ok` 전에는 머지가 막히는지**: 아무 브랜치로 PR을 만들고, CI가 끝나기 전에 머지를 시도합니다.

```bash
gh pr merge <PR 번호> --merge
```

**기대 결과**: 필수 상태 체크 대기로 거절됩니다. CI가 통과한 뒤에는 승인 없이 머지됩니다(필수 승인 0).
