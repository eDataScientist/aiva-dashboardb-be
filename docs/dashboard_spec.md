# AI Agent Performance Dashboard — Technical Specification

**Version 1.0 — March 2026 — DRAFT**

Based on the `conversation_grades` schema

---

## 1. Executive summary

This document specifies the design, data requirements, component structure, and technology stack for an AI Agent Performance Dashboard. The dashboard transforms raw grading data from the `conversation_grades` table into actionable visual insights across three views: **Agent Pulse**, **Correlations**, and **Daily Timeline**.

The goal is to move beyond generic metric cards and instead tell the story of how the AI agent is performing — where it fails, why it fails, and what to fix first.

---

## 2. Data source

### 2.1 Schema overview

The dashboard reads from a single wide flat table called `conversation_grades`. Each row represents one AI grading output per customer conversation per day, uniquely constrained by `(phone_number, grade_date)`.

### 2.2 Field groups

| Group | Fields | Types | Notes |
|---|---|---|---|
| Core | `id`, `phone_number`, `grade_date`, `created_at` | uuid, varchar, date, timestamp | Primary key + unique constraint |
| AI Performance | `relevancy_score`/`reasoning`, `accuracy_score`/`reasoning`, `completeness_score`/`reasoning`, `clarity_score`/`reasoning`, `tone_score`/`reasoning` | smallint (1–10) + text | Five scored dimensions with free-text justification |
| Conversation Health | `resolution`/`reasoning`, `repetition_score`/`reasoning`, `loop_detected`/`reasoning` | boolean, text, smallint, boolean | Resolution success + repetition/loop signals |
| User Signals | `satisfaction_score`/`reasoning`, `frustration_score`/`reasoning`, `user_relevancy`/`reasoning` | smallint (1–10), smallint, boolean | Customer sentiment + genuine interaction flag |
| Escalation | `escalation_occurred`/`reasoning`, `escalation_type`/`reasoning` | boolean, enum (`Natural`/`Failure`/`None`) | Whether and how escalation happened |
| Intent | `intent_label`, `intent_reasoning` | varchar, text | Strongest prevalent intent detected |

---

## 3. Dashboard architecture

### 3.1 Technology stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| UI Framework | React | 18.x | Component-based SPA rendering |
| Charting | Chart.js | 4.4.1 | Line charts, scatter plots via canvas |
| Styling | Tailwind CSS or inline styles | 3.x / N/A | Utility-first CSS or zero-dependency inline approach |
| State | React `useState` / `useRef` | Built-in | Local component state, no external store needed |
| Data layer | REST API / Supabase client | Any | Fetch aggregated data from `conversation_grades` |
| Build | Vite or Next.js | 5.x / 14.x | Dev server + production bundling |

### 3.2 CDN dependencies (standalone artifact mode)

```
Chart.js 4.4.1 UMD
https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js
```

For a production build, install via npm:

```bash
npm install chart.js react-chartjs-2
```

### 3.3 No additional dependencies required

The dashboard intentionally avoids heavyweight libraries. The score ring is drawn with native Canvas API, the heatmap and funnel are pure CSS/HTML, and only the trend line chart and scatter plot use Chart.js. This keeps the bundle small and the dependency surface minimal.

---

## 4. View specifications

### 4.1 View 1: Agent pulse

The executive glance. Answers: **how is the AI agent performing right now?**

#### Components

| Component | Visual type | Data source | SQL pattern |
|---|---|---|---|
| Overall score ring | Canvas arc gauge | AVG of all 5 score columns | `SELECT ROUND(AVG((relevancy_score + accuracy_score + completeness_score + clarity_score + tone_score) / 5.0), 1)` |
| Dimension bars | Horizontal bar chart | AVG per score column | `SELECT AVG(relevancy_score), AVG(accuracy_score), ... WHERE grade_date BETWEEN :start AND :end` |
| Health chips | Stat cards with icon | `resolution` %, `AVG(repetition_score)`, `loop_detected` % | `SELECT COUNT(*) FILTER (WHERE resolution), AVG(repetition_score), COUNT(*) FILTER (WHERE loop_detected)` |
| Escalation strip | Stacked horizontal bar | `escalation_type` distribution | `SELECT escalation_type, COUNT(*) GROUP BY escalation_type` |
| User signals | Metric cards (3-up grid) | `satisfaction_score`, `frustration_score`, `user_relevancy` | `AVG(satisfaction_score)`, `AVG(frustration_score)`, `COUNT(*) FILTER (WHERE user_relevancy)` |
| Trend chart | Chart.js multi-line | Daily averages over 7 days | `SELECT grade_date, AVG(satisfaction_score), AVG(frustration_score), AVG(overall) GROUP BY grade_date` |
| Intent tags | Tag grid with counts | `intent_label` frequency | `SELECT intent_label, COUNT(*) GROUP BY intent_label ORDER BY count DESC LIMIT 6` |
| Attention signals | Colored pills | Derived from thresholds | Business rules applied to aggregated metrics |

#### Design notes

- The score ring uses a 270° arc (from -135° to +135°) with a blue fill proportional to score/10.
- Dimension bars are horizontal with the score value right-aligned. Bar width = `score * 10%`.
- Attention signal pills are computed client-side: red if failure escalation > 10%, amber if any dimension < 7.5, green if frustration is trending down.

---

### 4.2 View 2: Correlations

The insight layer. Maps how AI performance dimensions relate to user outcomes and traces the path to failure escalation.

#### Components

| Component | Visual type | Data source | Logic |
|---|---|---|---|
| Heatmap | Colored grid (5 cols × 3 rows) | Cross-tab: dimension score range vs avg satisfaction | Bucket each dimension into 1–4, 5–7, 8–10; compute `AVG(satisfaction_score)` per bucket |
| Failure funnel | Horizontal bar funnel | Filtered counts down escalation path | Sequential filters: total → `loop_detected` → `frustration_score >= 7` → `NOT resolution` → `escalation_type = 'Failure'` |
| Frustration distribution | Vertical bar histogram | `frustration_score` bucketed by range | `SELECT CASE WHEN frustration_score BETWEEN 1 AND 2 THEN '1–2' ... END, COUNT(*)` |
| Story cards | Insight cards (2×2 grid) | Derived analysis | Pre-computed or dynamically generated from correlation analysis |

#### Design notes

- The heatmap uses a diverging color scale from red (low satisfaction) through amber to green (high satisfaction).
- The funnel is not a true funnel chart — it's horizontal bars with decreasing widths. Each bar represents a subset of the previous one, showing the path conversations take before failure.
- Story cards have a 4px left accent bar matching their severity color and present a single metric prominently with explanatory copy below.

---

### 4.3 View 3: Daily timeline

Operational mode. Shows how individual conversations map across the day to spot temporal patterns.

#### Components

| Component | Visual type | Data source | Logic |
|---|---|---|---|
| Hourly heatmap | 24-cell grid with volume circles | Resolution rate + count per hour | `SELECT EXTRACT(HOUR FROM created_at), COUNT(*), AVG(resolution::int) GROUP BY hour` |
| Best/worst hour | Metric card pair | Min/max resolution rate hours | `ORDER BY resolution_rate ASC/DESC LIMIT 1` |
| Scatter plot | Chart.js scatter | `satisfaction_score` vs `frustration_score` per row | `SELECT satisfaction_score, frustration_score, resolution, loop_detected` |
| Worst performers table | Data table with mini-charts | Bottom N conversations by composite score | `ORDER BY (rel + acc + com + cla + ton) / 5 ASC LIMIT N` |

#### Design notes

- Each heatmap cell has a background color (resolution rate) and a circle overlay (conversation volume). This dual encoding avoids the common mistake of showing only one dimension.
- The scatter plot uses shape encoding in addition to color: resolved = circle, unresolved = circle, loop detected = triangle. This ensures accessibility for colorblind users.
- The mini performance bars in the table (5 thin bars per row, one per AI dimension) let you visually spot the *shape* of a bad conversation — one bar drastically shorter tells a different story than uniformly low.

---

## 5. Color system

### 5.1 Semantic palette

| Purpose | Hex | Usage |
|---|---|---|
| Primary blue | `#378ADD` | Overall performance, neutral data, active tab indicator |
| Success green | `#1D9E75` | Resolution, satisfaction, positive signals |
| Danger red | `#E24B4A` | Failure escalation, high frustration, unresolved |
| Warning amber | `#EF9F27` | Loops detected, mid-range scores, natural escalation |
| Coral | `#D85A30` | Secondary warning, funnel mid-stages |
| Teal | `#5DCAA5` | Natural escalation, mid-health indicators |
| Neutral gray | `#888780` | No-escalation, structural elements |

### 5.2 Background / badge variants

| Purpose | Background | Text |
|---|---|---|
| Green badge | `#E1F5EE` | `#085041` |
| Red badge | `#FCEBEB` | `#791F1F` |
| Amber badge | `#FAEEDA` | `#633806` |
| Gray badge | `#F1EFE8` | `#444441` |

### 5.3 Heatmap color mapping

The performance-to-outcome heatmap uses a diverging scale:

| Satisfaction avg | Fill | Text |
|---|---|---|
| 7.5+ | `#C0DD97` | `#27500A` |
| 6.0–7.4 | `#9FE1CB` | `#085041` |
| 4.5–5.9 | `#FAEEDA` | `#633806` |
| 3.0–4.4 | `#F7C1C1` | `#791F1F` |
| Below 3.0 | `#F09595` | `#791F1F` |

### 5.4 Resolution heatmap (hourly)

| Resolution rate | Cell color |
|---|---|
| < 50% | `#FCEBEB` |
| 50–59% | `#FAC775` |
| 60–69% | `#9FE1CB` |
| 70–79% | `#5DCAA5` |
| 80%+ | `#1D9E75` |

---

## 6. Component structure

The React application is structured as a single-page tabbed dashboard.

### 6.1 Component tree

```
Dashboard (root)
├── Tab bar (Agent pulse | Correlations | Daily timeline)
├── AgentPulse
│   ├── ScoreRing (canvas arc gauge)
│   ├── Dimension bars (pure CSS)
│   ├── Health chips (3× stat cards)
│   ├── Escalation strip (stacked bar)
│   ├── User signals (3-up metric grid)
│   ├── ChartCanvas → Chart.js line (trend)
│   ├── Intent tags (CSS grid)
│   └── Attention signals (colored pills)
├── Correlations
│   ├── Heatmap (CSS grid with colored cells)
│   ├── Failure funnel (horizontal bars)
│   ├── Frustration distribution (CSS bar chart)
│   └── Story cards (2×2 insight grid)
└── DailyTimeline
    ├── Hourly heatmap (24-cell CSS grid)
    ├── Best/worst hour (metric pair)
    ├── ChartCanvas → Chart.js scatter
    └── Worst performers table (with MiniPerf, ScoreDot, Badge)
```

### 6.2 Utility components

| Component | Props | Responsibility |
|---|---|---|
| `ScoreRing` | `score`, `size` | Canvas-based 270° arc gauge |
| `ChartCanvas` | `id`, `config`, `height` | Chart.js wrapper that polls for CDN load |
| `Badge` | `variant` (green/red/amber/gray) | Colored pill label |
| `ScoreDot` | `value` | Circular score indicator with semantic color |
| `MiniPerf` | `scores` (array of 5) | Sparkline-style mini bar chart for table rows |
| `SectionLabel` | `children` | Uppercase section heading |

---

## 7. SQL query reference

All queries target the `conversation_grades` table. Date filters should be parameterized.

### 7.1 Overall composite score

```sql
SELECT ROUND(
  AVG((relevancy_score + accuracy_score + completeness_score 
       + clarity_score + tone_score) / 5.0), 1
) AS overall_score
FROM conversation_grades
WHERE grade_date BETWEEN :start AND :end;
```

### 7.2 Per-dimension averages

```sql
SELECT
  ROUND(AVG(relevancy_score), 1)    AS avg_relevancy,
  ROUND(AVG(accuracy_score), 1)     AS avg_accuracy,
  ROUND(AVG(completeness_score), 1) AS avg_completeness,
  ROUND(AVG(clarity_score), 1)      AS avg_clarity,
  ROUND(AVG(tone_score), 1)         AS avg_tone
FROM conversation_grades
WHERE grade_date BETWEEN :start AND :end;
```

### 7.3 Escalation distribution

```sql
SELECT
  escalation_type,
  COUNT(*) AS cnt,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM conversation_grades
WHERE grade_date BETWEEN :start AND :end
GROUP BY escalation_type;
```

### 7.4 Cross-tab heatmap (performance vs satisfaction)

```sql
WITH scored AS (
  SELECT
    satisfaction_score,
    unnest(ARRAY['relevancy','accuracy','completeness','clarity','tone']) AS dim_name,
    unnest(ARRAY[relevancy_score, accuracy_score, completeness_score, 
                  clarity_score, tone_score]) AS dim_score
  FROM conversation_grades
  WHERE grade_date BETWEEN :start AND :end
)
SELECT
  dim_name,
  CASE
    WHEN dim_score BETWEEN 1 AND 4 THEN '1-4'
    WHEN dim_score BETWEEN 5 AND 7 THEN '5-7'
    ELSE '8-10'
  END AS score_bucket,
  ROUND(AVG(satisfaction_score), 1) AS avg_satisfaction
FROM scored
GROUP BY dim_name, score_bucket;
```

### 7.5 Hourly resolution rate

```sql
SELECT
  EXTRACT(HOUR FROM created_at) AS hr,
  COUNT(*) AS vol,
  ROUND(AVG(resolution::int) * 100, 0) AS resolution_pct
FROM conversation_grades
WHERE grade_date = :date
GROUP BY hr
ORDER BY hr;
```

### 7.6 Failure escalation funnel

```sql
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE loop_detected)                                    AS loops,
  COUNT(*) FILTER (WHERE frustration_score >= 7)                           AS high_frustration,
  COUNT(*) FILTER (WHERE NOT resolution)                                   AS unresolved,
  COUNT(*) FILTER (WHERE escalation_type = 'Failure')                      AS failure_escalations
FROM conversation_grades
WHERE grade_date BETWEEN :start AND :end;
```

### 7.7 Intent frequency

```sql
SELECT intent_label, COUNT(*) AS cnt
FROM conversation_grades
WHERE grade_date BETWEEN :start AND :end
  AND intent_label IS NOT NULL
GROUP BY intent_label
ORDER BY cnt DESC
LIMIT 6;
```

### 7.8 Worst performing conversations

```sql
SELECT
  phone_number,
  intent_label,
  relevancy_score, accuracy_score, completeness_score, clarity_score, tone_score,
  satisfaction_score,
  frustration_score,
  resolution,
  escalation_type
FROM conversation_grades
WHERE grade_date = :date
ORDER BY (relevancy_score + accuracy_score + completeness_score 
          + clarity_score + tone_score) / 5.0 ASC
LIMIT 10;
```

---

## 8. Production considerations

### 8.1 Data layer

- Replace sample data constants with API calls or Supabase client queries
- Add a date range picker to parameterize all queries
- Cache aggregated results (5-minute TTL) to avoid repeated heavy queries
- Consider materialized views for the cross-tab heatmap query (it unnests and re-aggregates on every call)

### 8.2 Performance

- Lazy-load Chart.js only when the trend or scatter tab is active
- Virtualize the worst-performers table if row count exceeds 50
- Use `React.memo` on pure components (`Badge`, `ScoreDot`, `MiniPerf`)
- Debounce date range filter changes to prevent excessive re-renders

### 8.3 Accessibility

- Add `aria-labels` to all interactive elements (tabs, score rings, chart canvases)
- Provide text alternatives for visual-only data (heatmap cell values, scatter plot summaries)
- Ensure color is never the sole differentiator — combine with shape (triangle for loops) and text labels
- Support keyboard navigation between tabs and focusable chart elements

### 8.4 Responsiveness

- Dashboard `max-width: 720px` (comfortable reading width)
- Stat grids collapse from 3-column to stacked below 480px
- Hourly heatmap switches to vertical list on narrow screens
- Table scrolls horizontally on mobile with sticky first column

### 8.5 Dark mode

- The current implementation uses hardcoded light-theme colors
- For dark mode support, extract all colors into CSS custom properties and provide a dark variant
- Chart.js grid lines and text colors need to be swapped via the `options.scales` config

---

## 9. File manifest

| File | Type | Description |
|---|---|---|
| `ai_agent_dashboard.jsx` | React component | Complete dashboard with all three views, sample data, and Chart.js integration |
| `dashboard_spec.md` | Markdown | This specification document |

---

*End of specification.*
