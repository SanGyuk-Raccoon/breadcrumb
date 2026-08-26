# ADR: Planning-time ADR finder and implementation reconciliation

- Schema Version: 1
- Status: accepted
- Work Issue: #13
- Supersedes: none
- Superseded By: none

## Summary

Planning 완료 직전에 결정론적 corpus projection과 read-only semantic subagent로 관련 ADR을
전체 검색하고, implementation은 확정된 ADR 계획만 실제 변경과 대조한다.

## Context

경로와 keyword만 사용하는 script는 이름이 달라졌거나 의미적으로만 연결된 결정을 놓칠 수
있다. 반대로 모든 코드 편집 시점마다 전체 ADR을 다시 검색하면 불필요한 호출과 context
소비가 늘고 구현 중 planning으로 되돌아갈 가능성이 커진다. 검색 시점, subagent 입력·출력과
전체 coverage를 고정해야 정확성과 비용을 함께 관리할 수 있다.

## Affected Areas

- Components: planning completion gate, ADR corpus projection, deterministic signal ranking, semantic finder subagent, implementation reconciliation
- Paths: .breadcrumb/adr/**, plugins/breadcrumb/scripts/**, plugins/breadcrumb/skills/breadcrumb/**, plugins/breadcrumb/scripts/tests/**
- Resources: work issue planning narrative, Git base commit, corpus digest, isolated Codex subagent context
- Behaviors: Planned Change Scope capture, full-corpus semantic review, evidence return, disposition selection, drift detection, planning reopen

## Decision

Planning은 goal·요약·제안 결정과 예상 component, path, resource, behavior를
`Planned Change Scope`로 먼저 기록한다. 완료 직전에 finder는 work issue identity, 이
planning 정보, base commit과 T3 corpus digest만 compact JSON input으로 받는다.

Local `adr --base <commit> --finder-input-json <json>` projection은 path·component·resource·
behavior·Work Issue·lifecycle 신호로 모든 ADR의 compact projection을 결정론적으로 정렬한다.
이 명령과 전체 candidate 검토는 격리된 read-only subagent context에서 실행한다. 신호가
일치하지 않는 ADR도 배제하지 않으며, 관련 후보의 전문만 추가로 읽고 candidate의 content
SHA-256과 일치하는지 확인한다. Main context는 본문 없는 index와 최종 관련 결과만 받는다.

Finder는 `ok|blocked|incomplete`, digest, 전체·검토 수, 관련 ADR의 path·content hash·status·
구조화된 관계·section 근거, 계획 제약, 불확실성과 권장 disposition만 main context로
반환한다. Finder가
disposition을 확정하지 않으며 main planning과 사용자가
`not-required|reuse|create|supersede|deprecate` 및 필요한 초안을 결정한다. Invalid corpus,
base·digest mismatch 또는 불완전 coverage는 planning 완료를 차단한다.

구현은 코드와 테스트를 먼저 완성한 뒤 issue에 계획된 ADR과 실제 diff·behavior를 경량
대조하고 같은 PR에 ADR을 반영한다. 계획된 신규 ADR과 lifecycle edit 자체는 corpus drift가
아니다. 계획 시 기존 corpus baseline 또는 material한 결정·범위가 달라졌거나 새 장기 결정이
발견된 경우에만 planning을 다시 열어 전체 검색을 반복한다.

## Consequences

결정론적 검증만 사용할 때보다 token과 subagent 호출 비용은 늘지만 의미적 누락 가능성과
main context 오염을 줄이고 coverage를 감사할 수 있다. ADR 수가 커지면 compact projection도
context 한계에 닿을 수 있다. v1은 persistent index나 저장소별 custom agent 파일 없이
Breadcrumb skill의 격리된 read-only subagent 실행을 사용한다.

## Review Triggers

관련 ADR false negative가 발견되거나, corpus 규모가 compact full coverage의 context 한계를
넘거나, Codex subagent 계약이 바뀌거나, 반복 검색 비용 때문에 검증 가능한 persistent
index가 필요해질 때 재검토한다.
