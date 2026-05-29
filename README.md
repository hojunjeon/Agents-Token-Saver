# Codex Token Saver

Codex용 토큰 절약 키트입니다. 원문은 SQLite에 보관하고, Codex 컨텍스트에는 압축된 핵심 사실과 `ctx://capture/<id>` 참조만 넣습니다. 목표는 출력/도구/코드 탐색 토큰을 줄이되, 필요할 때 원문을 즉시 복원해 정확도를 잃지 않는 것입니다.

## One-click Windows install

[![One-click Windows install](https://img.shields.io/badge/One--click%20Windows%20install-install.bat-blue)](install.bat)

Windows에서 이 폴더를 받은 뒤 `install.bat`을 더블클릭하세요. 설치기는 다음을 수행합니다.

- `cts` 명령을 `%USERPROFILE%\.codex\bin\cts.cmd`에 생성
- Codex skill을 `%USERPROFILE%\.codex\skills\codex-token-saver`에 복사
- `%USERPROFILE%\.codex\hooks.json`와 `config.toml`에 신뢰된 `PostToolUse` hook state 생성
- 벤치마크 fixture와 문서를 `%LOCALAPPDATA%\CodexTokenSaver`에 복사

새 터미널에서 `cts`가 안 보이면 `%USERPROFILE%\.codex\bin`을 PATH에 추가하세요.

다른 Windows PC로 옮길 때는 `dist/codex-token-saver-windows.zip`을 풀고 그 안의 `install.bat`을 더블클릭하면 됩니다.

## 빠른 사용

```powershell
cts pack --query "reject expired token" --root .
python -m pytest -vv | cts filter --capture --command "python -m pytest -vv"
cts search "expired token"
cts get 1 --preview
cts scan --root .
cts ab-test --fixtures benchmarks/fixtures --markdown docs/AB_TEST_RESULTS.md
cts watchdog --run-tests
```

프로젝트에 Codex용 라우팅 파일을 넣고 싶으면:

```powershell
cts init --root .
```

생성되는 `AGENTS.md`는 짧게 유지됩니다. 긴 설명은 docs로 보내고, Codex는 `cts pack`과 `ctx://` 참조를 통해 필요한 것만 가져옵니다.

## 기능

- **Caveman-style concise replies for Codex**: 짧게 답하되 경로, 명령, 오류, 검증 증거는 보존
- **RTK-style terminal compaction**: pytest/git/status/log류 출력에서 실패 사실만 추출
- **Context Mode-style sandbox**: 원문은 SQLite에 저장하고 컨텍스트에는 참조만 표시
- **Code Review Graph/Token Savior-style symbol packs**: 전체 파일 대신 관련 심볼과 원문 ref 제공
- **Token Optimizer-style watchdog**: 요구사항, 설치물, A/B 수치, 문서, 테스트를 한 번에 검사
- **Windows Codex PostToolUse hook**: 큰 도구 출력은 자동으로 SQLite에 보관하고 secret-shaped 값을 redaction한 compact context만 Codex에 전달하며, 설치 시 Codex trust state를 함께 기록
- **Codex skill packaging**: `%USERPROFILE%\.codex\skills`에서 바로 감지되는 skill 포함
- **Requirement watchdog subagent**: `skill/codex-token-saver/agents/requirement-watchdog.md`가 절약률과 recall gate를 반복 감시

## A/B 요약

현재 fixture 기준 watchdog gate는 `94%+` 전체 절약, 케이스별 절약 floor, `100%` anchor recall입니다. 현재 A/B는 원본 2008 토큰을 111 토큰으로 줄여 `94.5%` 절약합니다. 재생성:

```powershell
python -m codex_token_saver ab-test --fixtures benchmarks/fixtures --markdown docs/AB_TEST_RESULTS.md --json docs/ab-test-results.json
```

자세한 결과는 `docs/AB_TEST_RESULTS.md`를 보세요.
최적화 반복 평가표는 `docs/EVALUATION_MATRIX.md`에 남겨져 있습니다.

## 기존 Agents-Token-Saver 기능 반영

이전 GitHub 저장소의 핵심 장점은 Windows Codex Desktop `PostToolUse` Token Vault hook과 hook trust state 자동 등록이었습니다. 이 기능은 Python `cts hook post-tool-use`와 `cts install-hook`으로 포팅했습니다. 기존 `/상태` quota 표시 기능은 토큰 절약 기능이 아니라 상태 조회 기능이므로 이번 replacement의 핵심 범위에서는 제외했습니다.
