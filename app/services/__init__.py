"""Application service layer modules."""

from app.services.auth import (
    AuthenticationError,
    authenticate_account,
    to_account_context,
)
from app.services.grading_extraction import (
    CustomerDayCandidate,
    CustomerDayTranscript,
    TranscriptMessage,
    assemble_customer_day_transcript,
    build_customer_day_candidates_stmt,
    build_customer_day_messages_stmt,
    canonical_identity_type_expr,
    canonical_identity_value_expr,
    gst_grade_date_expr,
    list_customer_day_candidates,
    resolve_canonical_identity,
)
from app.services.grading_parser import (
    GradingParseFailure,
    ParsedGradingResult,
    parse_grading_output,
)
from app.services.grading_pipeline import (
    GradeCustomerDayFailure,
    GradeCustomerDayFailureCode,
    GradeCustomerDayResult,
    GradeCustomerDaySuccess,
    GradingPipelineDependencies,
    build_grading_pipeline_dependencies,
    grade_customer_day,
)
from app.services.grading_prompt import PromptBundle, build_grading_prompt
from app.services.grading_provider import (
    GradingProviderError,
    GradingProviderRequest,
    build_grading_provider,
)
from app.services.grading_persistence import upsert_customer_day_grade

__all__ = [
    "AuthenticationError",
    "CustomerDayCandidate",
    "CustomerDayTranscript",
    "GradeCustomerDayFailure",
    "GradeCustomerDayFailureCode",
    "GradeCustomerDayResult",
    "GradeCustomerDaySuccess",
    "GradingParseFailure",
    "GradingPipelineDependencies",
    "GradingProviderError",
    "GradingProviderRequest",
    "ParsedGradingResult",
    "PromptBundle",
    "TranscriptMessage",
    "assemble_customer_day_transcript",
    "authenticate_account",
    "build_customer_day_candidates_stmt",
    "build_grading_pipeline_dependencies",
    "build_customer_day_messages_stmt",
    "build_grading_prompt",
    "build_grading_provider",
    "canonical_identity_type_expr",
    "canonical_identity_value_expr",
    "grade_customer_day",
    "gst_grade_date_expr",
    "list_customer_day_candidates",
    "parse_grading_output",
    "resolve_canonical_identity",
    "to_account_context",
    "upsert_customer_day_grade",
]
