# Database Schema: `conversation_grades`

Wide flat table storing daily AI grading output per customer conversation.

**Unique constraint:** `(phone_number, grade_date)` — one record per customer per day.

---

## Core Fields

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `phone_number` | varchar | Customer identifier |
| `grade_date` | date | The day this grade covers |
| `created_at` | timestamp | Insertion timestamp |

---

## AI Performance

| Column | Type | Notes |
|---|---|---|
| `relevancy_score` | smallint | 1–10 |
| `relevancy_reasoning` | text | |
| `accuracy_score` | smallint | 1–10 |
| `accuracy_reasoning` | text | |
| `completeness_score` | smallint | 1–10 |
| `completeness_reasoning` | text | |
| `clarity_score` | smallint | 1–10 |
| `clarity_reasoning` | text | |
| `tone_score` | smallint | 1–10 |
| `tone_reasoning` | text | |

---

## Conversation Health

| Column | Type | Notes |
|---|---|---|
| `resolution` | boolean | |
| `resolution_reasoning` | text | |
| `repetition_score` | smallint | 1–10 |
| `repetition_reasoning` | text | |
| `loop_detected` | boolean | |
| `loop_detected_reasoning` | text | |

---

## User Signals

| Column | Type | Notes |
|---|---|---|
| `satisfaction_score` | smallint | 1–10 |
| `satisfaction_reasoning` | text | |
| `frustration_score` | smallint | 1–10 |
| `frustration_reasoning` | text | |
| `user_relevancy` | boolean | True = genuine interaction |
| `user_relevancy_reasoning` | text | |

---

## Escalation

| Column | Type | Notes |
|---|---|---|
| `escalation_occurred` | boolean | |
| `escalation_occurred_reasoning` | text | |
| `escalation_type` | enum | `Natural` / `Failure` / `None` |
| `escalation_type_reasoning` | text | |

---

## Intent

| Column | Type | Notes |
|---|---|---|
| `intent_label` | varchar | Strongest prevalent intent |
| `intent_reasoning` | text | |