# Verification

## Unit Tests

Python 코드, 템플릿 계약 또는 Breadcrumb 동작을 변경한 경우 전체 단위 테스트를 실행한다. 저장소 루트에서 Python 3.11 이상으로 실행한다.

```sh
python3.12 -m unittest discover -s plugins/breadcrumb/scripts/tests -v
```

## Template Validation

Breadcrumb 템플릿이나 템플릿 검증·상태 계약을 변경한 경우, 저장소에서 선택되는 모든 템플릿의 구조를 검증한다.

```sh
python3.12 plugins/breadcrumb/scripts/validate_breadcrumb_templates.py all
```
