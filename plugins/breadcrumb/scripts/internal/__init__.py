"""Shared contracts for Breadcrumb's deterministic read model."""

PROJECTION_VERSION = 1
WORK_SCHEMA_VERSION = 1
BREADCRUMB_LABEL = "breadcrumb"
WORK_STATUSES = ("backlog", "in-progress", "complete")
TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
