# Milestone 1 - Phase 4 Plan: ORM Query Rewrite

## Goals
- Rewrite 4 raw SQL analytics functions in `app/services/analytics.py` to use SQLAlchemy 2.0 ORM expressions.
- Eliminate the use of `sqlalchemy.text()` for these queries to improve maintainability and type safety.
- Ensure the replaced queries produce identical results and JSON structures as the raw SQL versions.
- Remove leftover dead code related to raw SQL string building.

## Target Functions
1. `get_analytics_summary`
2. `get_message_volume_trend`
3. `get_top_intents`
4. `get_peak_hours`

## Tasks Breakdown
All Phase 4 tasks are sequential Gate tasks as they modify the same service file.

| Task ID | Title | Type | Dependencies | Output |
|---|---|---|---|---|
| P1.4.1 | Rewrite `get_analytics_summary` to ORM | API | `P1.3.10` | Updated summary endpoint |
| P1.4.2 | Rewrite `get_message_volume_trend` to ORM | API | `P1.3.10` | Updated volume endpoint |
| P1.4.3 | Rewrite `get_top_intents` to ORM | API | `P1.3.10` | Updated intents endpoint |
| P1.4.4 | Rewrite `get_peak_hours` to ORM + Python zero-fill | API | `P1.3.10` | Updated peak hours endpoint |
| P1.4.5 | Remove dead raw-SQL helpers (`_channel_sql_clause`, etc.) | API | `P1.4.1-4` | Cleaned up file |
| P1.4.6 | QA - Spot-check endpoints return same results | QA | `P1.4.5` | Confirmed equivalence |

## Technical Implementation Notes
- **Timezone handling**: Use `func.timezone("Asia/Dubai", ChatMessage.created_at).cast(func.current_date().type)` for daily bucketing.
- **Hourly bucketing**: Use `func.extract("HOUR", func.timezone("Asia/Dubai", ChatMessage.created_at))` for hourly bucketing.
- **Zero-filling**: For `get_peak_hours`, generate the 0-23 hours list in Python and left-merge the database results into it to ensure zero-filled buckets, rather than relying on Postgres `generate_series`.
- **Booleans**: `_ESCALATED_TRUTHY` logic becomes `func.lower(func.trim(ChatMessage.escalated)).in_({"true", "yes", "1", "y", "t"})`.
- **Identity**: `_CUSTOMER_IDENTITY` becomes `func.coalesce(ChatMessage.customer_phone, ChatMessage.customer_email_address, ChatMessage.session_id)`.
- **Conditional Aggregation**: Use `case()` within `func.count(func.distinct(...))` for calculating components like `total_leads` inside `get_analytics_summary`.
