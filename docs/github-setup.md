# GitHub 저장소 설정 절차 (사람이 할 일)

로컬 저장소는 이미 커밋이 쌓여 있습니다. 아래 순서대로 **A**가 GitHub 저장소를 만들고 연결합니다.
명령 예시는 [GitHub CLI(`gh`)](https://cli.github.com/) 기준입니다. 먼저 `gh auth login`으로 로그인하세요.

아래에서 `<OWNER>`는 A의 GitHub 아이디(또는 조직 이름), `<B_ID>`는 B의 GitHub 아이디입니다.

---

## 0단계. 먼저 정할 것: 공개 저장소 vs 비공개 저장소

GitHub 공식 문서 기준, **GitHub Free 계정의 비공개 저장소에서는 브랜치 보호와 CODEOWNERS가 동작하지 않습니다.**

> Protected branches are available in public repositories with GitHub Free and GitHub Free for organizations.
> Protected branches are also available in public and private repositories with GitHub Pro, GitHub Team, ...
> (출처: github/docs `data/reusables/gated-features/protected-branches.md`, CODEOWNERS도 같은 조건)

T00 검증("리뷰 없이는 머지가 막히는지")을 통과하려면 다음 중 하나를 고르세요.

| 선택 | 비용 | 메모 |
|---|---|---|
| **A. 공개 저장소** | 무료 | 포트폴리오라 어차피 공개할 예정이면 가장 간단합니다. 키와 원본 데이터는 원래 커밋하지 않으므로 공개해도 안전해야 합니다. |
| B. 비공개 + A 계정을 GitHub Pro로 | 유료, 또는 학생이면 GitHub Student Developer Pack으로 무료 | 개인 계정 저장소에만 적용됩니다. |
| C. 비공개 + 보호 규칙 없이 운영 | 무료 | 규칙을 사람이 지켜야 합니다. T00 검증은 미통과로 남습니다. |

---

## 1단계. 저장소 생성과 push

저장소 루트(`SPEC.md`가 있는 폴더)에서 실행합니다.

```bash
gh repo create <OWNER>/symptom-care --public --source . --remote origin --push
```

비공개로 만들려면 `--public` 대신 `--private`을 씁니다. `gh` 없이 할 때는 웹에서 **빈 저장소**(README, .gitignore 없이)를 만든 뒤:

```bash
git remote add origin https://github.com/<OWNER>/symptom-care.git
```

```bash
git push -u origin main
```

## 2단계. B를 collaborator로 초대

```bash
gh api -X PUT repos/<OWNER>/symptom-care/collaborators/<B_ID> -f permission=push
```

B는 메일 또는 https://github.com/notifications 에서 초대를 수락합니다.

## 3단계. CODEOWNERS 아이디 바꾸기

`.github/CODEOWNERS`의 자리표시자 `@A_GITHUB_ID`, `@B_GITHUB_ID`를 실제 아이디로 바꿉니다.
이 변경도 PR로 올립니다(4단계 이후라면 브랜치 보호가 적용됩니다).

```bash
sed -i 's/@A_GITHUB_ID/@<A_ID>/g; s/@B_GITHUB_ID/@<B_ID>/g' .github/CODEOWNERS
```

(macOS는 `sed -i ''`를 씁니다.)

## 4단계. `main` 브랜치 보호

웹: **Settings → Branches → Add branch protection rule**, Branch name pattern `main`
- [x] Require a pull request before merging → Required approvals **1**
- [x] Dismiss stale pull request approvals when new commits are pushed
- [x] Require review from Code Owners (선택. CODEOWNERS 아이디를 바꾼 뒤에 켜세요)
- [x] Require status checks to pass before merging → 체크 이름은 아래 "필수 상태 체크" 참고
- [x] Do not allow bypassing the above settings (관리자인 A도 규칙을 따르게 합니다)
- [ ] Allow force pushes / Allow deletions: 끔

같은 설정을 CLI로 할 때(본문 필드는 GitHub REST API 명세 `PUT /repos/{owner}/{repo}/branches/{branch}/protection` 기준):

```bash
gh api -X PUT repos/<OWNER>/symptom-care/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["ci-ok"] },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

### 필수 상태 체크
CI(`.github/workflows/ci.yml`)는 바뀐 경로의 잡만 실행하고, 마지막에 **`ci-ok`** 잡 하나로 결과를 모읍니다.
그래서 필수 체크에는 `ci-ok` 하나만 등록합니다. 경로별 잡을 필수로 등록하면, 그 경로를 안 건드린 PR이 "대기 중"으로 막힐 수 있습니다.
`ci-ok`는 CI가 한 번 실행된 뒤에야 웹 설정 화면의 검색 목록에 나타납니다.

## 5단계. 라벨(모듈 ID)

이슈 1개 = 태스크 1개로 등록하고 모듈 ID 라벨을 답니다(SPEC 7절).

```bash
for m in api-contract platform data-foundation triage-model llm-assistant hospital-search backend-api web-frontend data-pipeline; do gh label create "$m" --repo <OWNER>/symptom-care --force; done
```

## 6단계. agent-skills 플러그인 (두 사람 모두)

저장소의 `.claude/settings.json`에 마켓플레이스와 플러그인이 등록돼 있습니다. clone한 폴더에서 Claude Code를 열고 **폴더 신뢰(trust)** 를 수락한 뒤:

```
/plugin marketplace add addyosmani/agent-skills
/plugin install agent-skills@addy-agent-skills
```

(`enabledPlugins`는 켜기만 하고 설치는 하지 않으므로 각자 한 번 설치해야 합니다. 출처: https://code.claude.com/docs/en/settings-reference.md `enabledPlugins`)

## 7단계. T00 검증 (B가 수행)

```bash
git clone https://github.com/<OWNER>/symptom-care.git
```

```bash
cd symptom-care && git checkout -b chore/platform/T00-protection-test && echo "test" > docs/protection-test.md && git add docs/protection-test.md && git commit -m "chore: test branch protection" && git push -u origin chore/platform/T00-protection-test
```

```bash
gh pr create --title "chore: branch protection test" --body "T00 verification" --base main
```

```bash
gh pr merge --merge
```

**기대 결과**: 리뷰 승인 전에는 마지막 명령이 거절됩니다(“review required” / “base branch policy prohibits the merge”). 그 화면을 캡처해 두고, PR은 머지하지 말고 닫습니다.

```bash
gh pr close --delete-branch
```
