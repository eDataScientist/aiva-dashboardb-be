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

INTENT_CODES: Final[tuple[str, ...]] = tuple(INTENT_CODE_TO_LABEL.keys())
INTENT_LABEL_TO_CODE: Final[dict[str, str]] = {
    label: code for code, label in INTENT_CODE_TO_LABEL.items()
}
