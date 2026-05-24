# Agents Token Saver

에이전트 코딩 환경에서 큰 터미널 출력, 테스트 로그, 검색 결과가 컨텍스트를 잡아먹는 문제를 줄이기 위한 토큰 절약 도구 모음입니다.

이 저장소의 주 기능은 **Windows Codex Desktop용 Token Vault hook**입니다. 도구 실행 결과 원문은 로컬 파일로 보존하고, 모델 컨텍스트에는 오류, 요약, 앞/뒤 일부, 원문 경로만 넣어 토큰 사용량을 크게 줄입니다. 작은 출력은 건드리지 않습니다.

첨부된 3개 재설치 패키지도 함께 보존되어 있습니다.

- `integrations/imported/openclaw-tokenjuice-vault-reinstall`: OpenClaw TokenJuice vault 패치
- `integrations/imported/hermes-token-vault-reinstall`: Hermes `token-vault` 플러그인
- `integrations/imported/omx-token-vault-reinstall`: 기존 OMX/Codex token-vault hook 패키지

원본 `.tar.gz` 파일은 `archives/`에 들어 있습니다.

## 왜 필요한가

에이전트가 토큰을 많이 쓰는 지점은 보통 최종 답변이 아니라 **도구 출력**입니다. 예를 들어:

- 실패한 테스트 로그
- `rg` 같은 repo-wide 검색 결과
- 긴 빌드 로그
- 큰 JSON 출력
- 반복적인 터미널 출력

모델은 전체 원문이 아니라 “어디가 실패했는지, 앞/뒤 맥락이 무엇인지, 원문을 다시 볼 수 있는 위치가 어디인지”만 필요한 경우가 많습니다.

Agents Token Saver는 이 흐름으로 동작합니다.

1. 도구는 평소처럼 실행됩니다.
2. `PostToolUse` hook이 큰 출력만 감지합니다.
3. 원본 출력 전체를 로컬 vault에 저장합니다.
4. 모델에는 압축 요약과 원문 파일 경로만 전달합니다.
5. 모델이 vault artifact를 직접 읽는 경우에는 재압축하지 않습니다.
6. 작은 출력은 원문 그대로 둡니다.

## 핵심 기능

### Windows Codex Desktop Token Vault

관련 파일:

- `src/token-vault-core.mjs`
- `src/codex-token-vault-hook.mjs`
- `scripts/install-token-vault.ps1`
- `tools/benchmark.mjs`

기본 동작:

- 기본 압축 기준: `12,000` bytes 이상
- 기본 요약 길이: `4,000` chars
- vault 위치: `%USERPROFILE%\.omx\token-vault-codex`
- 원문 artifact 위치: `%USERPROFILE%\.omx\token-vault-codex\artifacts\<id>.json`
- `node:sqlite` 사용 가능 시 SQLite 인덱스 사용, 아니면 JSONL fallback
- summary에서 흔한 secret 형태 필드 redaction
  - authorization
  - token
  - secret
  - password
  - API key
  - cookie
  - signature
  - private key
- hook 오류가 나도 Codex 실행은 막지 않는 fail-open 설계

## Codex Desktop `/status` / `/상태` 주의사항

Codex Desktop의 공식 `/status`는 앱 내장 slash command입니다. 이 명령은 일반 프롬프트나 `UserPromptSubmit` hook보다 먼저 처리됩니다.

따라서 Token Vault의 핵심 기능인 `PostToolUse` 압축 hook은 `/status` 또는 `/상태` 입력을 직접 막는 구조가 아닙니다.

중요한 구분:

- `PostToolUse` Token Vault hook: 도구 실행 결과가 나온 뒤 큰 출력을 압축합니다.
- `/status`: Codex Desktop/CLI의 내장 slash command입니다.
- `/상태`: Codex/OMX 설정에 따라 별도 alias처럼 동작할 수 있지만, Codex Desktop이 사용자 정의 slash command를 안정적으로 등록해 주는 공개 API는 확인되지 않았습니다.

이 저장소는 **토큰 절약 기능 저장소**입니다. 로컬 Desktop의 `/상태` alias 문제는 Codex/OMX 로컬 설정 문제일 수 있으며, Token Vault 자체와 분리해서 봐야 합니다.

## 설치

PowerShell에서 실행합니다.

```powershell
git clone https://github.com/hojunjeon/Agents-Token-Saver.git
cd Agents-Token-Saver
npm test
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-token-vault.ps1
```

설치 후 Codex Desktop 또는 Codex 세션을 새로 시작해야 hook 설정이 반영됩니다.

설치 스크립트가 하는 일:

- `src/codex-token-vault-hook.mjs`와 core 파일을 `%USERPROFILE%\.omx\token-vault-codex\bin`으로 복사
- `%USERPROFILE%\.codex\hooks\codex-token-vault-windows-shim.ps1` 생성
- `%USERPROFILE%\.codex\hooks.json`의 `PostToolUse` 앞쪽에 Token Vault hook 추가
- 기존 OMX hook은 유지
- `hooks.json`, `config.toml` 백업 생성

## 설정

환경 변수로 조정할 수 있습니다.

```powershell
$env:CODEX_TOKEN_VAULT = "1"                 # 0/false/no/off 이면 비활성화
$env:CODEX_TOKEN_VAULT_THRESHOLD = "12000"   # 이 byte 이상이면 압축
$env:CODEX_TOKEN_VAULT_MAX_CHARS = "4000"    # 요약 최대 길이
$env:CODEX_TOKEN_VAULT_DIR = "$HOME\.omx\token-vault-codex"
```

## 제거

`%USERPROFILE%\.codex\hooks.json`에서 Token Vault `PostToolUse` 항목을 제거한 뒤 아래 파일을 삭제합니다.

```powershell
Remove-Item -Force "$HOME\.codex\hooks\codex-token-vault-windows-shim.ps1"
Remove-Item -Recurse -Force "$HOME\.omx\token-vault-codex"
```

설치 전 백업 파일은 다음 형식으로 생성됩니다.

```text
%USERPROFILE%\.codex\hooks.json.bak-token-vault-*
%USERPROFILE%\.codex\config.toml.bak-token-vault-trust-*
```

## 성능 평가

로컬 Windows Codex Desktop 작업공간에서 측정했습니다.

```powershell
npm run benchmark
```

| 시나리오 | 적용 전 | 적용 후 | 절감률 | Hook 시간 |
| --- | ---: | ---: | ---: | ---: |
| 실패가 포함된 큰 테스트 로그 | 241,022 bytes | 4,200 bytes | 98.3% | 36.00 ms |
| repo-wide 검색 출력 | 167,219 bytes | 5,942 bytes | 96.4% | 16.34 ms |
| 작은 명령 출력 | 17 bytes | 17 bytes | 0% | 0.04 ms |

해석:

- 큰 출력은 96-98% 수준으로 줄었습니다.
- 작은 출력은 압축하지 않아 정보 손실이 없습니다.
- 원문은 로컬 vault에 남기 때문에 필요하면 다시 읽을 수 있습니다.

## 검증

```powershell
npm test
npm run benchmark
node --check .\src\codex-token-vault-hook.mjs
node --check .\src\token-vault-core.mjs
```

현재 검증 상태:

- `npm test`: 11개 통과
- `npm run benchmark`: 큰 synthetic output에서 96.4-98.3% 절감
- Windows vault shim: Codex `PostToolUse` compact output 정상 생성
- small output passthrough 확인
- vault artifact 재압축 방지 확인
- secret-shaped field redaction 확인

## 포함된 외부/이식 패키지

### OpenClaw TokenJuice Vault

경로:

```text
integrations/imported/openclaw-tokenjuice-vault-reinstall
```

설치:

```bash
cd integrations/imported/openclaw-tokenjuice-vault-reinstall
./install.sh
```

효과:

- 큰 OpenClaw shell/tool 결과를 `~/.openclaw/token-vault/artifacts/`에 저장
- 컨텍스트에는 compact summary 전달

### Hermes Token Vault

경로:

```text
integrations/imported/hermes-token-vault-reinstall
```

설치:

```bash
cd integrations/imported/hermes-token-vault-reinstall
./install.sh
```

효과:

- 큰 Hermes tool 결과를 `~/.hermes/token-vault/artifacts/`에 저장
- 컨텍스트에는 compact summary 전달

### 기존 OMX Token Vault 패키지

경로:

```text
integrations/imported/omx-token-vault-reinstall
```

설치:

```bash
cd integrations/imported/omx-token-vault-reinstall
./install.sh
```

효과:

- 큰 Codex/OMX tool 결과를 `~/.omx/token-vault/artifacts/`에 저장
- 컨텍스트에는 compact summary 전달

주의:

- 이 imported 패키지는 Unix 경로(`/usr/bin/node` 등)를 기준으로 만들어졌습니다.
- Windows Codex Desktop에서는 저장소 루트의 `scripts/install-token-vault.ps1`을 쓰는 것을 권장합니다.

## 보안 주의사항

compact summary에서는 흔한 secret 형태를 redaction하지만, 원본 출력 전체는 로컬 vault에 저장됩니다.

민감한 값이 터미널에 출력된 경우:

1. 해당 artifact를 `%USERPROFILE%\.omx\token-vault-codex\artifacts`에서 삭제하세요.
2. 필요하면 vault 디렉터리 전체를 삭제하세요.
3. 이미 노출된 API key나 token은 폐기/재발급하세요.

## 저장소 구조

```text
src/                         Windows/Codex Token Vault 구현
scripts/                     Windows Codex Desktop 설치 스크립트
test/                        Node test runner 테스트
tools/                       benchmark 스크립트
integrations/imported/       OpenClaw, Hermes, OMX 이식 패키지
archives/                    원본 tar.gz 번들
```

## 참고한 아이디어

- [Caveman](https://github.com/juliusbrussee/caveman): 출력 스타일 압축
- [RTK](https://github.com/rtk-ai/rtk): 터미널 출력 필터링
- [Context Mode](https://github.com/mksglu/context-mode): 컨텍스트 밖 저장소 활용
- [Token Optimizer MCP](https://github.com/ooples/token-optimizer-mcp): MCP 캐싱/압축 패턴
