# Task Planning Guideline

This document defines the terminology, structure, and conventions used across all phase planning documents in 5Aside Footy. It serves as a reference for anyone writing or reading a phase plan.

---

## Terminology

### Phase

A **Phase** is the top-level unit of project delivery. Each phase represents a major feature area or milestone (e.g., Phase 4 – Admin Foundation, Phase 5 – Match Recording). Phases are numbered sequentially and are the primary way the project roadmap is chunked.

- Phases can depend on earlier phases (e.g., Phase 5 depends on Phase 4's RBAC).
- A phase plan document (`phase-X-<name>.md`) details all the work within that phase.
- Fractional phases like **6.5** are used for polish or QoL work that doesn't warrant a full new phase number.

### Work Package (WP)

A **Work Package** groups related tasks at the same architectural layer or concern area. They are used primarily in the **design-system / component-building** phases (project-plan.md, project-plan-phase-2.md) where work is organized by atomic design layers.

| Property | Description |
|----------|-------------|
| **Naming** | `WP<phase>.<number>` (e.g., `WP2.0`, `WP2.3`) |
| **Scope** | One layer or concern (Foundation, Atoms, Molecules, Organisms, Templates, QA) |
| **Duration** | Measured in abstract **units** |
| **Parallelism** | How many independent streams it contains |
| **Dependencies** | Which WPs must complete (fully or partially) before it starts |

Work Packages are most useful when the work is layered (atoms → molecules → organisms) and each layer fans out into parallel streams.

### Gate

A **Gate** is a **blocking prerequisite** that must be completed before the rest of the phase's work can begin. Think of it as a checkpoint that "unlocks" parallel streams.

| Property | Description |
|----------|-------------|
| **Naming** | `<phase>.0` or `<phase>.1` (e.g., Gate 4.1, Gate 5.0, Gate 6.0, Gate 6.5.0) |
| **Purpose** | Establish foundational capabilities needed by all streams (e.g., RBAC guards, API endpoints, theme tokens + DB migrations) |
| **Characteristics** | Sequential, blocking, usually infrastructure or API work |
| **Acceptance Criteria** | Explicit checklist that must pass before streams start |

**Examples from the project:**
- **Gate 4.1** (RBAC): Role-checking utilities + guard components → unlocks all admin UI streams.
- **Gate 5.0** (API Foundation): All match CRUD endpoints → unlocks wizard and list UI.
- **Gate 6.5.0** (Theme + DB): Bronze color palette + attendance schema migration → unlocks squad allocation and goal animation.

### Stream

A **Stream** is a **parallelizable track of work** within a phase or work package. Once a gate completes, multiple streams can run concurrently, often by different agents.

| Property | Description |
|----------|-------------|
| **Naming** | Stream A, B, C… (descriptive label appended, e.g., "Stream A – Match Recording Wizard") |
| **Scope** | One coherent feature or UI surface |
| **Independence** | Streams should not depend on each other (exceptions noted, e.g., Stream C may depend on Stream A) |
| **Internal order** | Tasks within a stream are generally sequential (list view → add form → edit → validation edge cases) |

**Key rule:** Streams exist so that multiple agents/developers can work in parallel without blocking each other.

### Task

A **Task** is the smallest unit of deliverable work. Every task has:

| Field | Description |
|-------|-------------|
| **Task ID** | Hierarchical identifier (e.g., `5.0.1`, `A.3`, `P2.2.5`, `T1A.1`) |
| **Task Name** | Short description of the deliverable |
| **Duration** | Estimated in abstract **units** |
| **Dependencies** | Which tasks must complete first |
| **Notes** | Implementation hints, component reuse notes |

Tasks should be small enough that one can be completed in a single focused session.

### Acceptance Criteria

**Acceptance Criteria** are concrete, verifiable conditions attached to a gate, stream, or screen within a wizard. They answer: _"How do we know this is done?"_

- Written as checkbox lists: `- [ ] Condition`.
- Describe observable behavior, not implementation details.
- Cover happy paths, defaults, and validation states.

### Definition of Done (DoD)

The **Definition of Done** is a phase-level checklist that must pass before the entire phase is considered complete. It aggregates the most critical acceptance criteria and adds cross-cutting concerns.

Common DoD items across all phases:
- All routes are protected by the correct guard.
- Features function end-to-end with validation.
- Clear success and error feedback on all actions.
- No lint errors in files touched by the phase.
- Animations are smooth (where applicable).

### Parallelization Map

A **Parallelization Map** is an ASCII diagram showing how the gate and streams relate in time. It visually communicates:

1. What is blocking (the gate).
2. What can run in parallel (streams after the gate).
3. Any inter-stream dependencies (e.g., Stream C depends on Stream A).

```
Gate ──────────────────────────────┐
    │                              │
    ├── Stream A ─────────────────►│
    │                              │
    ├── Stream B ─────────────────►│  (parallel with A)
    │                              │
    └── Stream C ─────────────────►│  (after Stream A)
                                   │
                                   ▼
                          Phase Complete
```

---

## Naming Conventions

### Task ID Formats

The project uses several task ID schemes depending on the document type:

| Context | Format | Example |
|---------|--------|---------|
| Phase plan (gate tasks) | `<phase>.<gate>.<seq>` | `5.0.1`, `6.0.3` |
| Phase plan (stream tasks) | `<stream letter>.<seq>` | `A.3`, `B.2`, `C.1` |
| Work package tasks | `P<phase>.<WP>.<seq>` | `P2.2.5`, `P2.3.14` |
| Design system plan | `T<WP><stream>.<seq>` | `T1A.1`, `T2C.3`, `T3G.1` |

---

## Phase Document Structure

Every phase plan follows this template:

```
# Phase X - <Name> Plan

## Goals
## Dependencies
## Gate X.0 - <Foundation Name>
   - Gate tasks table
   - Acceptance criteria
   - API contracts (if applicable)

## Stream A - <Feature Name>
   - Tasks table (per screen/section)
   - Acceptance criteria (per screen)

## Stream B - <Feature Name>
   ...

## Component Dependency Summary
## Parallelization Map
## Definition of Done
## Test Scenarios
   - Happy path
   - Edge cases
## Open Questions and Assumptions
## Estimated Duration
```

---

## Planning Checklist (When Writing a New Phase Plan)

1. **Define goals** — 3-5 bullet points for what the phase delivers.
2. **List dependencies** — What must exist from previous phases? Show status.
3. **Identify the gate** — What foundational work must finish first?
4. **Design streams** — Group remaining work into independent tracks.
5. **Break streams into tasks** — Each task should be ≤ 2 units of effort.
6. **Write acceptance criteria** — For each gate, screen, and stream.
7. **Note component reuse** — Mark which existing components can be extended vs. built new.
8. **Draw the parallelization map** — ASCII diagram of gate → streams → completion.
9. **Write DoD** — Phase-level checklist.
10. **List test scenarios** — Happy path + edge cases.
11. **Document assumptions and open questions** — Flag decisions that need confirmation.
12. **Estimate duration** — Sequential total vs. parallelized total.

---

## Dependency Notation

| Symbol | Meaning |
|--------|---------|
| `->` | Sequential: must complete before next |
| `\|\|` | Parallel: can run concurrently |
| `*` or `★` | Critical path task |
| `◆` | Blocking task (many downstream dependents) |
| `⊕` | Partial dependency (only specific sub-tasks) |

---

## Duration Units

All durations use **abstract units**, not hours or days. One unit represents a consistent chunk of focused effort. This keeps estimates relative and avoids calendar-based overcommitment.

| Duration | Typical scope |
|----------|---------------|
| 0.25 | Verify/delete/rename an existing component |
| 0.5 | Simple wrapper, minor refactor, single endpoint |
| 0.75 | Compose 2-3 atoms into a molecule, small hook |
| 1.0 | New component with moderate logic, standard API endpoint |
| 1.5 | Complex component (e.g., PitchView, state machine hook) |
| 2.0 | Multi-concern organism, chart component |

---

*Document Version: 1.0*
*Created: 2026-02-10*
*Based on: project-plan.md, project-plan-phase-2.md, phase-4, phase-5, phase-6, phase-6.5*
