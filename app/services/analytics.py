"""Analytics service layer — aggregation queries against the chats table."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import Integer, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chats import ChatMessage
from app.schemas.analytics import (
    AnalyticsChannelFilter,
    AnalyticsSummaryResponse,
    DateCountPoint,
    DateValuePoint,
    HourCountPoint,
    IntentCountPoint,
    LeadConversionTrendPoint,
    LeadConversionTrendResponse,
    MessageVolumeTrendResponse,
    PeakHoursResponse,
    QualityTrendResponse,
    TopIntentsResponse,
)

LEAD_INTENTS = {
    "New Get-A-Quote Form Submitted in UAE",
    "New Contact Form Submitted",
}

_LEAD_INTENTS_TUPLE = tuple(LEAD_INTENTS)


def _get_channel_filter(channel: AnalyticsChannelFilter) -> list[Any]:
    if channel == AnalyticsChannelFilter.ALL:
        return []
    if channel == AnalyticsChannelFilter.WHATSAPP:
        return [ChatMessage.channel == "whatsapp"]
    if channel == AnalyticsChannelFilter.WEB:
        return [ChatMessage.channel == "web"]
    return []


def _get_default_date_range() -> tuple[date, date]:
    end_date = date.today()
    start_date = end_date - timedelta(days=29)
    return start_date, end_date


def _convert_to_gst_date(dt: Any) -> Any:
    return func.timezone("Asia/Dubai", dt).cast(func.current_date().type)


async def compute_quality_trend(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    channel: AnalyticsChannelFilter = AnalyticsChannelFilter.ALL,
) -> QualityTrendResponse:
    if start_date is None or end_date is None:
        start_date, end_date = _get_default_date_range()

    filters = [
        ChatMessage.created_at >= start_date,
        ChatMessage.created_at < end_date + timedelta(days=1),
    ]

    channel_filters = _get_channel_filter(channel)
    if channel_filters:
        filters.extend(channel_filters)

    customer_identity = func.coalesce(
        ChatMessage.customer_phone,
        ChatMessage.customer_email_address,
        ChatMessage.session_id,
    )

    gst_date = func.timezone("Asia/Dubai", ChatMessage.created_at).cast(
        func.current_date().type
    )

    escalated_is_failure = case(
        (
            func.lower(func.trim(ChatMessage.escalated)).in_(
                {"true", "yes", "1", "y", "t"}
            ),
            True,
        ),
        else_=False,
    )
    is_lead_intent = case(
        (ChatMessage.intent.in_(LEAD_INTENTS), True),
        else_=False,
    )

    daily_metrics = (
        select(
            gst_date.label("date"),
            func.count(func.distinct(customer_identity)).label(
                "total_customers"
            ),
            func.count(
                func.distinct(
                    case(
                        (escalated_is_failure, customer_identity),
                    )
                )
            ).label("failed_customers"),
            func.count(
                func.distinct(
                    case(
                        (is_lead_intent, customer_identity),
                    )
                )
            ).label("lead_customers"),
        )
        .where(and_(*filters))
        .group_by(gst_date)
        .order_by(gst_date)
        .subquery()
    )

    result = await session.execute(
        select(daily_metrics).where(daily_metrics.c.total_customers > 0)
    )

    points_dict = {row.date: row for row in result}
    points: list[DateValuePoint] = []
    
    current_date = start_date
    while current_date <= end_date:
        if current_date in points_dict:
            row = points_dict[current_date]
            total_customers = row.total_customers or 1
            failed_customers = row.failed_customers or 0
            lead_customers = row.lead_customers or 0

            resolution_rate = (total_customers - failed_customers) / total_customers
            lead_conversion_rate = lead_customers / total_customers

            ai_quality_score = (resolution_rate * 0.7 + lead_conversion_rate * 2.5) * 100
            ai_quality_score = min(100.0, max(0.0, ai_quality_score))
            score_value = round(ai_quality_score, 2)
        else:
            score_value = 0.0

        points.append(DateValuePoint(date=current_date, value=score_value))
        current_date += timedelta(days=1)

    return QualityTrendResponse(points=points)


async def compute_lead_conversion_trend(
    session: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    channel: AnalyticsChannelFilter = AnalyticsChannelFilter.ALL,
) -> LeadConversionTrendResponse:
    if start_date is None or end_date is None:
        start_date, end_date = _get_default_date_range()

    filters = [
        ChatMessage.created_at >= start_date,
        ChatMessage.created_at < end_date + timedelta(days=1),
    ]

    channel_filters = _get_channel_filter(channel)
    if channel_filters:
        filters.extend(channel_filters)

    customer_identity = func.coalesce(
        ChatMessage.customer_phone,
        ChatMessage.customer_email_address,
        ChatMessage.session_id,
    )

    gst_date = func.timezone("Asia/Dubai", ChatMessage.created_at).cast(
        func.current_date().type
    )

    is_lead_intent = case(
        (ChatMessage.intent.in_(LEAD_INTENTS), True),
        else_=False,
    )

    daily_metrics = (
        select(
            gst_date.label("date"),
            func.count(func.distinct(customer_identity)).label(
                "total_customers"
            ),
            func.count(
                func.distinct(
                    case(
                        (is_lead_intent, customer_identity),
                    )
                )
            ).label("lead_customers"),
        )
        .where(and_(*filters))
        .group_by(gst_date)
        .order_by(gst_date)
        .subquery()
    )

    result = await session.execute(
        select(daily_metrics).where(daily_metrics.c.total_customers > 0)
    )

    points_dict = {row.date: row for row in result}
    points: list[LeadConversionTrendPoint] = []
    
    current_date = start_date
    while current_date <= end_date:
        if current_date in points_dict:
            row = points_dict[current_date]
            total_customers = row.total_customers or 1
            lead_customers = row.lead_customers or 0
            rate_pct = (lead_customers / total_customers) * 100
            count_value = lead_customers
            rate_value = round(rate_pct, 2)
        else:
            count_value = 0
            rate_value = 0.0

        points.append(
            LeadConversionTrendPoint(
                date=current_date,
                count=count_value,
                rate_pct=rate_value,
            )
        )
        current_date += timedelta(days=1)

    return LeadConversionTrendResponse(points=points)


# ---------------------------------------------------------------------------
# P1.2.2 — Summary Endpoint
# ---------------------------------------------------------------------------


def _default_date_range(
    start_date: date | None, end_date: date | None
) -> tuple[date, date]:
    """Return a concrete (start, end) pair, defaulting to last 30 days."""
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=29)
    return start_date, end_date


async def get_analytics_summary(
    session: AsyncSession,
    start_date: date | None,
    end_date: date | None,
    channel: str,
) -> AnalyticsSummaryResponse:
    """Aggregate summary KPIs from chat data within a date/channel window."""
    start, end = _default_date_range(start_date, end_date)

    gst_date = func.timezone("Asia/Dubai", ChatMessage.created_at).cast(
        func.current_date().type
    )
    filters = [
        gst_date >= start,
        gst_date <= end,
    ]

    if channel != "all":
        filters.extend(_get_channel_filter(AnalyticsChannelFilter(channel)))

    customer_identity = func.coalesce(
        ChatMessage.customer_phone,
        ChatMessage.customer_email_address,
        ChatMessage.session_id,
    )

    escalated_is_failure = case(
        (
            func.lower(func.trim(ChatMessage.escalated)).in_(
                {"true", "yes", "1", "y", "t"}
            ),
            True,
        ),
        else_=False,
    )

    is_lead_intent = case(
        (ChatMessage.intent.in_(LEAD_INTENTS), True),
        else_=False,
    )

    query = select(
        func.count().label("total_messages"),
        func.count(func.distinct(customer_identity)).label("total_customers"),
        func.count()
        .filter(func.lower(ChatMessage.direction) == "inbound")
        .label("inbound_messages"),
        func.count()
        .filter(func.lower(ChatMessage.direction) == "outbound")
        .label("outbound_messages"),
        func.count(func.distinct(customer_identity))
        .filter(escalated_is_failure)
        .label("escalated_customers"),
        func.count(func.distinct(customer_identity))
        .filter(is_lead_intent)
        .label("total_leads"),
    ).where(and_(*filters))

    row = (await session.execute(query)).mappings().one()

    total_customers: int = row["total_customers"] or 0
    escalated_customers: int = row["escalated_customers"] or 0
    total_messages: int = row["total_messages"] or 0
    total_leads: int = row["total_leads"] or 0
    inbound_messages: int = row["inbound_messages"] or 0
    outbound_messages: int = row["outbound_messages"] or 0

    # Derived rates (division-by-zero safe)
    escalation_rate = (
        (escalated_customers / total_customers * 100.0)
        if total_customers
        else 0.0
    )
    resolution_rate = (100.0 - escalation_rate) if total_customers else 0.0
    avg_engagement = (
        (total_messages / total_customers) if total_customers else 0.0
    )
    lead_conversion_rate = (
        (total_leads / total_customers * 100.0) if total_customers else 0.0
    )
    ai_quality_score = min(
        (resolution_rate * 0.7) + (lead_conversion_rate * 2.5),
        100.0,
    )

    return AnalyticsSummaryResponse(
        total_messages=total_messages,
        total_customers=total_customers,
        inbound_messages=inbound_messages,
        outbound_messages=outbound_messages,
        escalated_customers=escalated_customers,
        escalation_rate_pct=round(escalation_rate, 2),
        resolution_rate_pct=round(resolution_rate, 2),
        avg_engagement=round(avg_engagement, 2),
        total_leads=total_leads,
        lead_conversion_rate_pct=round(lead_conversion_rate, 2),
        ai_quality_score=round(ai_quality_score, 2),
    )


# ---------------------------------------------------------------------------
# P1.2.3 — Message Volume Trend Endpoint
# ---------------------------------------------------------------------------


async def get_message_volume_trend(
    session: AsyncSession,
    start_date: date | None,
    end_date: date | None,
    channel: str,
) -> MessageVolumeTrendResponse:
    """Return daily message counts grouped by GST calendar date."""
    start, end = _default_date_range(start_date, end_date)

    gst_date = func.timezone("Asia/Dubai", ChatMessage.created_at).cast(
        func.current_date().type
    )
    filters = [
        gst_date >= start,
        gst_date <= end,
    ]

    if channel != "all":
        filters.extend(_get_channel_filter(AnalyticsChannelFilter(channel)))

    query = (
        select(
            gst_date.label("bucket_date"),
            func.count().label("count"),
        )
        .where(and_(*filters))
        .group_by(gst_date)
        .order_by(gst_date)
    )

    rows = (await session.execute(query)).mappings().all()
    counts_by_date = {r["bucket_date"]: r["count"] for r in rows}

    from datetime import timedelta
    points: list[DateCountPoint] = []
    current_date = start
    while current_date <= end:
        points.append(
            DateCountPoint(
                date=current_date, 
                count=counts_by_date.get(current_date, 0)
            )
        )
        current_date += timedelta(days=1)

    return MessageVolumeTrendResponse(points=points)


async def get_top_intents(
    session: AsyncSession,
    start_date: date | None,
    end_date: date | None,
    channel: str,
    limit: int = 5,
) -> TopIntentsResponse:
    """Return top-N intents with counts and share percentages.

    Null/blank/whitespace intents are normalized to 'Unknown'.
    Results are ordered by count descending, then intent name ascending
    for stable tie handling.
    """
    start, end = _default_date_range(start_date, end_date)

    gst_date = func.timezone("Asia/Dubai", ChatMessage.created_at).cast(
        func.current_date().type
    )
    filters = [
        gst_date >= start,
        gst_date <= end,
    ]

    if channel != "all":
        filters.extend(_get_channel_filter(AnalyticsChannelFilter(channel)))

    normalized_intent = case(
        (func.nullif(func.trim(ChatMessage.intent), "").is_(None), "Unknown"),
        else_=func.trim(ChatMessage.intent),
    ).label("normalized_intent")

    total_query = select(func.count()).where(and_(*filters))
    total_count = await session.scalar(total_query) or 0

    query = (
        select(
            normalized_intent,
            func.count().label("count"),
        )
        .where(and_(*filters))
        .group_by(normalized_intent)
        .order_by(func.count().desc(), normalized_intent.asc())
        .limit(limit)
    )

    rows = (await session.execute(query)).mappings().all()

    return TopIntentsResponse(
        points=[
            IntentCountPoint(
                intent=r["normalized_intent"],
                count=r["count"],
                share_pct=(
                    round((r["count"] / total_count * 100), 2)
                    if total_count > 0
                    else 0.0
                ),
            )
            for r in rows
        ]
    )


# ---------------------------------------------------------------------------
# P1.2.5 — Peak Hours Endpoint (Stream B)
# ---------------------------------------------------------------------------


async def get_peak_hours(
    session: AsyncSession,
    start_date: date | None,
    end_date: date | None,
    channel: str,
) -> PeakHoursResponse:
    """Return hourly message distribution for hours 0-23 in GST timezone.

    Always returns exactly 24 hourly buckets (0..23) with zero-filled buckets
    for hours with no activity.
    """
    start, end = _default_date_range(start_date, end_date)

    gst_date = func.timezone("Asia/Dubai", ChatMessage.created_at).cast(
        func.current_date().type
    )
    filters = [
        gst_date >= start,
        gst_date <= end,
    ]

    if channel != "all":
        filters.extend(_get_channel_filter(AnalyticsChannelFilter(channel)))

    hour_expr = func.cast(
        func.extract(
            "HOUR", func.timezone("Asia/Dubai", ChatMessage.created_at)
        ),
        Integer,
    )

    query = (
        select(
            hour_expr.label("hour"),
            func.count().label("count"),
        )
        .where(and_(*filters))
        .group_by(hour_expr)
    )

    rows = (await session.execute(query)).mappings().all()
    counts_by_hour = {
        r["hour"]: r["count"] for r in rows if r["hour"] is not None
    }

    points = [
        HourCountPoint(hour=h, count=counts_by_hour.get(h, 0))
        for h in range(24)
    ]

    return PeakHoursResponse(points=points)
