from __future__ import annotations

from typing import Final

GRADING_PROVIDER_MOCK: Final[str] = "mock"
GRADING_PROVIDER_OPENAI_COMPATIBLE: Final[str] = "openai_compatible"
GRADING_SUPPORTED_PROVIDERS: Final[tuple[str, ...]] = (
    GRADING_PROVIDER_MOCK,
    GRADING_PROVIDER_OPENAI_COMPATIBLE,
)
GRADING_DEFAULT_MODEL: Final[str] = "mock-grade-v1"
GRADING_DEFAULT_PROMPT_VERSION: Final[str] = "v1"

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
