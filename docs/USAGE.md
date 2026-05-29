# Codex Token Saver 사용 설명서

## 핵심 원칙

Codex가 모든 원문을 읽지 않게 합니다. 대신 `cts`가 원문을 SQLite에 저장하고, Codex에는 핵심 facts와 `ctx://capture/<id>` 포인터만 줍니다. 정확한 라인, 전체 로그, 긴 파일이 필요할 때만 `cts get <id>`로 복원합니다.

## 명령

### 터미널 출력 압축

```powershell
python -m pytest -vv | cts filter --capture --command "python -m pytest -vv"
```

Codex 컨텍스트에는 실패 파일, assert, summary만 들어갑니다. 전체 출력은 `.codex-token-saver/context.sqlite`에 저장됩니다.

### 코드 컨텍스트 pack

```powershell
cts pack --query "payment retry timeout" --root .
```

전체 repo 대신 관련 심볼, 경로, line, `ctx://` 원문 ref를 출력합니다.

### 원문 복원

```powershell
cts search "retry timeout"
cts get 3 --preview
cts get 3
```

### Ghost token 스캔

```powershell
cts scan --root .
```

큰 `AGENTS.md`, lockfile, 오래된 docs처럼 Codex 시작 컨텍스트를 낭비하는 파일을 찾습니다.

### 요구사항 watchdog

```powershell
cts watchdog --run-tests
```

문서, 설치기, Codex skill, A/B 수치, 케이스별 절약 floor, 자동 테스트를 gate로 평가합니다.
현재 기준은 전체 94% 이상 절약, git status 50% 이상, pytest 실패 출력 85% 이상, symbol pack 95% 이상, anchor recall 100%입니다.
스킬 번들의 `agents/requirement-watchdog.md`는 이 기준을 감시하는 서브에이전트 지침입니다.

요구사항이 만족될 때까지 반복 점검하려면:

```powershell
cts watchdog --run-tests --until-pass --max-runs 5
```

### Codex PostToolUse hook 설치

기존 Agents-Token-Saver의 자동 Token Vault 아이디어를 `cts`에 통합했습니다. 큰 Codex 도구 출력은 자동으로 SQLite에 저장하고, 모델 컨텍스트에는 common secret-shaped 값을 redaction한 compact summary와 `ctx://capture/<id>`만 전달합니다.

```powershell
cts install-hook
```

설치기는 `hooks.json`에 hook을 등록하고 Codex가 자동 실행할 수 있도록 matching trusted hash를 `hooks.json` state와 `config.toml`에 기록합니다. 기존 설정 파일이 있으면 `*.bak-codex-token-saver-*` 백업을 남깁니다.

hook JSON을 직접 테스트하려면:

```powershell
Get-Content post-tool-use.json | cts hook post-tool-use --threshold-bytes 1000
```
