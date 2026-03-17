from __future__ import annotations

from typing import Final

GRADING_PROVIDER_MOCK: Final[str] = "mock"
GRADING_PROVIDER_OPENAI_COMPATIBLE: Final[str] = "openai_compatible"
GRADING_SUPPORTED_PROVIDERS: Final[tuple[str, ...]] = (
    GRADING_PROVIDER_MOCK,
    GRADING_PROVIDER_OPENAI_COMPATIBLE,
)
GRADING_BATCH_TIMEZONE: Final[str] = "Asia/Dubai"
GRADING_RUN_STALE_RECOVERY_ERROR_MESSAGE: Final[str] = (
    "Recovered stale grading run after scheduler timeout."
)
GRADING_RUN_TRIGGER_TYPES: Final[tuple[str, ...]] = ("scheduled", "manual")
GRADING_RUN_MODES: Final[tuple[str, ...]] = ("daily", "backfill", "rerun")
GRADING_RUN_STATUSES: Final[tuple[str, ...]] = (
    "queued",
    "running",
    "completed",
    "completed_with_failures",
    "failed",
)
GRADING_RUN_SUCCESSFUL_STATUSES: Final[frozenset[str]] = frozenset(
    {"completed", "completed_with_failures"}
)
GRADING_RUN_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {"completed", "completed_with_failures", "failed"}
)
GRADING_RUN_ITEM_STATUSES: Final[tuple[str, ...]] = (
    "success",
    "skipped_existing",
    "empty_transcript",
    "provider_error",
    "parse_error",
)
GRADING_RUN_ITEM_FAILURE_STATUSES: Final[frozenset[str]] = frozenset(
    {"empty_transcript", "provider_error", "parse_error"}
)
GRADING_DEFAULT_MODEL: Final[str] = "mock-grade-v1"
GRADING_DEFAULT_PROMPT_VERSION: Final[str] = "v1"
GRADING_METRICS_DEFAULT_WINDOW_DAYS: Final[int] = 30
DASHBOARD_DEFAULT_WINDOW_DAYS: Final[int] = 7
DASHBOARD_MAX_WINDOW_DAYS: Final[int] = 31
DASHBOARD_DEFAULT_WORST_PERFORMERS_LIMIT: Final[int] = 10
DASHBOARD_MAX_WORST_PERFORMERS_LIMIT: Final[int] = 50
MONITORING_DEFAULT_WINDOW_DAYS: Final[int] = 1
MONITORING_DEFAULT_PAGE_SIZE: Final[int] = 50
MONITORING_DEFAULT_RECENT_HISTORY_LIMIT: Final[int] = 30
MONITORING_ALLOWED_SORT_FIELDS: Final[tuple[str, ...]] = (
    "frustration_score",
    "accuracy_score",
)
MONITORING_ALLOWED_SORT_DIRECTIONS: Final[tuple[str, ...]] = ("asc", "desc")
DASHBOARD_HEATMAP_SCORE_BUCKETS: Final[tuple[tuple[str, int, int], ...]] = (
    ("1-4", 1, 4),
    ("5-7", 5, 7),
    ("8-10", 8, 10),
)
DASHBOARD_FRUSTRATION_HISTOGRAM_BUCKETS: Final[tuple[tuple[str, int, int], ...]] = (
    ("1-2", 1, 2),
    ("3-4", 3, 4),
    ("5-6", 5, 6),
    ("7-8", 7, 8),
    ("9-10", 9, 10),
)
DASHBOARD_ATTENTION_SIGNAL_THRESHOLDS: Final[dict[str, float]] = {
    "failure_escalation_rate_pct": 10.0,
    "dimension_average_low": 7.5,
}
DASHBOARD_STORY_CARD_SEVERITY_THRESHOLDS: Final[
    tuple[tuple[str, float], ...]
] = (
    ("critical", 10.0),
    ("warning", 5.0),
    ("info", 0.0),
)
GRADING_PROMPT_PACK_BASE_DIR: Final[str] = "app/prompt_assets/grading"
GRADING_PROMPT_SYSTEM_PROMPT_FILE: Final[str] = "system_prompt.md"
GRADING_PROMPT_DOMAIN_ORDER: Final[tuple[str, ...]] = (
    "ai_performance",
    "conversation_health",
    "user_signals",
    "escalation",
    "intent",
)
GRADING_PROMPT_DOMAIN_TO_TEMPLATE_FILE: Final[dict[str, str]] = {
    "ai_performance": "ai_performance_judge.md",
    "conversation_health": "conversation_health.md",
    "user_signals": "user-signals.md",
    "escalation": "escalation.md",
    "intent": "intent.md",
}
GRADING_PROMPT_DOMAIN_SYSTEM_PROMPT_KEYS: Final[frozenset[str]] = frozenset(
    {"ai_performance", "escalation"}
)
GRADING_PROMPT_REQUIRED_FILES: Final[tuple[str, ...]] = (
    GRADING_PROMPT_SYSTEM_PROMPT_FILE,
    *tuple(GRADING_PROMPT_DOMAIN_TO_TEMPLATE_FILE.values()),
)

AUTH_BEARER_SCHEME: Final[str] = "bearer"
AUTH_TOKEN_TYPE_ACCESS: Final[str] = "access"
AUTH_PASSWORD_HASH_SCHEME: Final[str] = "pbkdf2_sha256"
AUTH_PASSWORD_HASH_DIGEST: Final[str] = "sha256"
AUTH_PASSWORD_HASH_SALT_BYTES: Final[int] = 16
AUTH_PASSWORD_HASH_ITERATIONS: Final[int] = 390_000
AUTH_REQUIRED_TOKEN_CLAIMS: Final[tuple[str, ...]] = (
    "sub",
    "email",
    "role",
    "type",
    "iat",
    "exp",
)


HIGHLIGHT_CODE_TO_LABEL: Final[dict[str, str]] = {
    "frustration_high": "High Frustration",
    "escalation_failure": "Failed Escalation",
    "loop_detected": "Conversation Loop",
    "accuracy_low": "Low Accuracy",
    "unresolved_low_satisfaction": "Unresolved + Low Satisfaction",
    "user_irrelevancy": "Non-genuine Interaction",
}

HIGHLIGHT_CODES: Final[tuple[str, ...]] = tuple(HIGHLIGHT_CODE_TO_LABEL.keys())

GRADING_METRICS_SCORE_TO_COLUMN: Final[dict[str, str]] = {
    "relevancy": "relevancy_score",
    "accuracy": "accuracy_score",
    "completeness": "completeness_score",
    "clarity": "clarity_score",
    "tone": "tone_score",
    "repetition": "repetition_score",
    "satisfaction": "satisfaction_score",
    "frustration": "frustration_score",
}
GRADING_METRICS_SCORE_KEYS: Final[tuple[str, ...]] = tuple(
    GRADING_METRICS_SCORE_TO_COLUMN.keys()
)
GRADING_METRICS_OUTCOME_RATE_KEYS: Final[tuple[str, ...]] = (
    "resolution_rate_pct",
    "loop_detected_rate_pct",
    "non_genuine_rate_pct",
    "escalation_rate_pct",
    "escalation_failure_rate_pct",
)
GRADING_ESCALATION_TYPE_VALUES: Final[tuple[str, ...]] = (
    "Natural",
    "Failure",
    "None",
)

INTENT_CODE_TO_LABEL: Final[dict[str, str]] = {
    "policy_inquiry": "Policy Inquiry",
    "policy_purchase": "Policy Purchase",
    "policy_modification": "Policy Modification",
    "policy_cancellation": "Policy Cancellation",
    "claims_submission": "Claims Submission",
    "claims_follow_up": "Claims Follow-up",
    "claims_dispute": "Claims Dispute",
    "payment_inquiry": "Payment Inquiry",
    "payment_issue": "Payment Issue",
    "document_request": "Document Request",
    "account_profile_update": "Account / Profile Update",
    "general_inquiry": "General Inquiry",
    "complaint": "Complaint",
    "escalation_request": "Escalation Request",
    "wasteful": "Wasteful",
    "unknown": "Unknown",
}
INTENT_CODE_TO_CATEGORY: Final[dict[str, str]] = {
    "policy_inquiry": "Policy Related",
    "policy_purchase": "Policy Related",
    "policy_modification": "Policy Related",
    "policy_cancellation": "Policy Related",
    "claims_submission": "Claims Related",
    "claims_follow_up": "Claims Related",
    "claims_dispute": "Claims Related",
    "payment_inquiry": "Billing & Payments",
    "payment_issue": "Billing & Payments",
    "document_request": "Documents & Admin",
    "account_profile_update": "Documents & Admin",
    "general_inquiry": "Support & Complaints",
    "complaint": "Support & Complaints",
    "escalation_request": "Support & Complaints",
    "wasteful": "Non-genuine",
    "unknown": "System Fallback",
}
INTENT_CODES: Final[tuple[str, ...]] = tuple(INTENT_CODE_TO_LABEL.keys())
INTENT_CATEGORIES: Final[tuple[str, ...]] = tuple(
    dict.fromkeys(INTENT_CODE_TO_CATEGORY.values())
)
INTENT_LABEL_TO_CODE: Final[dict[str, str]] = {
    label: code for code, label in INTENT_CODE_TO_LABEL.items()
}
