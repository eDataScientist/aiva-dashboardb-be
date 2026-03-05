from __future__ import annotations

from typing import Final


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
