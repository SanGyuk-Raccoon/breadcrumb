# ADR: Repository-local ADR as the canonical decision source

- Schema Version: 1
- Status: accepted
- Work Issue: #13
- Supersedes: none
- Superseded By: none

## Summary

장기 기술 결정의 canonical source를 Git으로 추적되는 `.breadcrumb/adr/*.md`로 두고, 관련
코드와 같은 PR에서 반영해 default branch merge를 효력 발생 시점으로 삼는다.

## Context

Breadcrumb의 work issue, implementation comment와 closing PR은 계획·구현·검증 문맥을
보존하지만, 리팩터링과 squash merge 이후에도 코드 가까이에서 장기 결정을 찾을
repository-local 원장은 제공하지 않는다. 병합 후 GitHub Actions, AI와 self-hosted runner를
사용하면 소비 저장소마다 인증·권한·순서·재시도 운영이 필요하다. 현재 주요 사용 형태는
1인 개발이며 ADR과 코드를 같은 PR에서 원자적으로 관리할 수 있다.

## Affected Areas

- Components: ADR template, corpus validator and projection, lifecycle handling, Breadcrumb workflow documentation
- Paths: .breadcrumb/adr/**, plugins/breadcrumb/templates/**, plugins/breadcrumb/scripts/**, plugins/breadcrumb/skills/breadcrumb/**, README.md
- Resources: Git repository, GitHub work issue and closing pull request history
- Behaviors: optional ADR adoption, creation, supersession, deprecation, validation, merge-time activation, historical lookup

## Decision

ADR은 `.breadcrumb/adr/<work-issue-number>-<decision-slug>.md`의 고정 filename과 schema-1
Markdown을 사용한다. 디렉터리 부재는 정상이며 첫 ADR이 필요할 때만 만든다. 상태는
`accepted`, `superseded`, `deprecated`만 영구 기록하고 feature branch의 파일은 merge 전
제안으로 해석한다.

관련 구현과 ADR은 같은 branch와 PR에 포함하며 default branch merge 후 별도 생성·동기화
작업을 실행하지 않는다. 결정 의미가 바뀌면 기존 `Decision`을 덮어쓰지 않고 새 ADR을
만들며, supersession은 기존·신규 파일을 같은 PR에서 양방향으로 연결한다. 대체 없이
종료되는 결정은 삭제하지 않고 `deprecated`로 보존한다.

Breadcrumb의 local `adr` projection은 regular UTF-8 Markdown, 고정 metadata와 heading,
filename과 Work Issue 일치, repository-local lifecycle graph와 선택적 base diff 전이를
기계 검증한다. GitHub Issue나 Discussion은 향후 필요할 때 local ADR에서 생성되는 opt-in
projection으로만 다룬다.

## Consequences

코드, 결정과 Git 이력이 같은 clone과 PR에 남아 별도 runner, AI API와 병합 후 순서 제어가
필요 없다. 반면 저장소에 문서 footprint와 schema 유지 비용이 생기고, invalid corpus는
관련 workflow 진행을 차단할 수 있다. 중앙 검색과 여러 저장소를 아우르는 graph는 v1에서
제공하지 않는다.

## Review Triggers

여러 저장소의 중앙 검색이 실제로 필요해지거나, 동시 PR의 ADR 충돌이 빈번해지거나, 고정
schema가 필요한 관계를 표현하지 못하거나, GitHub projection 또는 자동화 운영의 효용이
repository-local 비용을 넘어설 때 재검토한다.
