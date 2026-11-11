# CLAUDE.md

이 저장소의 에이전트 규칙은 `AGENTS.md` 한 곳에서 관리합니다(다른 에이전트 도구와 공유). 아래 줄이 그 파일을 불러옵니다.

@AGENTS.md

## Claude Code 전용
- agent-skills 플러그인은 `.claude/settings.json`에 등록돼 있습니다. 폴더를 신뢰(trust)한 뒤 `/plugin`에서 `agent-skills@addy-agent-skills`를 설치하세요.
- 작업 흐름: `incremental-implementation` → `test-driven-development` → `code-review-and-quality` → `git-workflow-and-versioning`. 외부 라이브러리 설정은 `source-driven-development`.
