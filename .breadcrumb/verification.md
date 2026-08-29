# Verification

## Unit Tests

Python 코드, 고정 템플릿 계약 또는 Breadcrumb 동작을 변경한 경우 전체 단위 테스트를 실행한다. 저장소 루트에서 Python 3.11 이상으로 실행한다.

```sh
python3.12 -m unittest discover -s plugins/breadcrumb/scripts/tests -v
```

## Skill And Plugin Validation

`init`, `read`, `issue`, `adr`, `implement`, `pr`, `report` 스킬을 각각 skill-creator의
`quick_validate.py`로 검증하고, 전체 플러그인을 plugin-creator의 `validate_plugin.py`로
검증한다. 현재 Codex 설치에서 각 creator skill의 실제 경로를 먼저 확인하고 실행한다.

공개 projection entrypoint와 artifact renderer를 변경한 경우 각 스크립트가 하나의 기능과
허용된 인자만 제공하는지, JSON 오류 계약과 고정 artifact schema를 유지하는지도 전체 단위
테스트로 확인한다.
