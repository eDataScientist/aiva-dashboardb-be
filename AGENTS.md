<AGENTS>
  <Context>
    - At the start of every interaction, if @docs contents are not already in context, read ALL docs in @docs.
    - CRITICAL: Always read @docs/project-progress.md at the beginning of every session (if not already in context).
    - CRITICAL: Keep @docs/tasks.md up to date after each meaningful subphase/phase completion.
    - Phase-specific docs: Each phase has a dedicated doc (docs/phase-<n>-*.md) that outlines tasks, streams, and notes.
  </Context>

  <TaskAdoptionWorkflow>
    1) Read project state:
       - Ensure project-progress.md is in context.
       - Determine current phase from project-progress.md.
       - Pull phase-n-<phase-name>.md into context.
    2) Pull tasks:
       - Use vibe-kanban MCP to list tasks in TODO and IN PROGRESS.
       - The project name for the kanban board is "aiva-dashboard-be".
    3) If tasks exist:
       - Run git diff to confirm tasks are not already completed in code.
       - If work already exists, reconcile Kanban status:
         - Move to IN REVIEW if code is done but needs review.
         - Move to DONE if already reviewed/accepted.
         - Otherwise move to IN PROGRESS for active work.
       - Select a task prioritizing:
         - Independent > Dependent
         - Dependencies completed
         - Do not start dependent tasks blocked by other in-progress authors.
       - Move selected task to IN PROGRESS and assign yourself.
    4) If no tasks exist:
       - Plan current phase using:
         - Phase-specific doc (docs/phase-<n>-*.md)
         - docs/tasks.md as the canonical checklist
       - Create atomic, numbered tasks with dependencies and "Independent/Dependent" labels.
       - Break into parallel streams where possible.
       - Do NOT create Kanban tasks unless explicitly instructed by the user.
  </TaskAdoptionWorkflow>

  <TaskCreationProtocol>
    - Task title format (required):
      "P<phase>.<subphase>.<item> - <TaskType> - <Short title> - <Gate|Stream X> (<Independent|Dependent>)"
      Examples:
      - "P5.1.2 - API - Create match endpoint - Stream A (Independent)"
      - "P5.2.4 - DB - Match wizard step 2 - Stream B (Dependent)"
    - Task description must include:
      - Goal/acceptance criteria
      - Dependencies (by task title)
      - Files to be modified/created (if known)
      - Testing/validation requirements
    - Streams:
      - Stream letters (A, B, C, ...) are parallelizable tracks.
      - Gate tasks are blockers for cross-stream progress.
  </TaskCreationProtocol>

  <GateAndStreamExecutionLoop>
    - Trigger phrases:
      - "carry out gate" => execute Gate tasks in order.
      - "carry out stream X" => execute Stream X tasks in order.
    - Loop behavior:
      1) Select the first task in the target set (Gate or Stream X).
      2) Move it to IN PROGRESS and assign yourself.
      3) Reply with the task title and its required format.
      4) Execute the task.
      5) On completion:
         - DO NOT move to DONE.
         - Move to IN REVIEW and append files modified/created.
      6) Move to the next task in the same set and repeat.
  </GateAndStreamExecutionLoop>

  <PlanTime>
    - Always ask clarifying questions until requirements are fully clear.
    - For a new phase, analyze in this order:
      1) Data models
      2) Migration
      3) Dependencies
      4) Configuration
      5) Endpoints 
    - Then create dedicated tasks with streams, parallelization, and explicit dependencies.
  </PlanTime>

  <TaskExecution>
    - Complete one atomic task at a time.
    - On completion:
      - Code changes: move task to IN REVIEW and list modified/created files.
        - Do not self test and move to DONE. 
      - No code changes: move task to DONE.
    - After a meaningful group (subphase/phase), update docs/tasks.md.
  </TaskExecution>

  <CodeReviewProcess>
    - Tasks in IN REVIEW require review after lint is clean.
    - Append review section to the task description:
      Reviewer: [Your Name]
      Review Notes:
      - Adherence to project coding standards
      - Code quality and functionality
      - Style and consistency
      - Potential issues or improvements
      - Positive aspects
      Suggested Fixes:
      - [Fix list or "None required - Approved"]
    - When asked to "review gate" or "review stream X":
      - Only add to the task description; do not delete existing content.
      - Provide detailed review comments when fixes are required.
    - Approved => move to DONE. Fixes needed => keep IN REVIEW or move to IN PROGRESS (assign original author).
  </CodeReviewProcess>

  <UserTesting>
    - For features requiring user validation:
      - Create explicit testing tasks.
      - Move to IN REVIEW and ask the user to test.
      - Do not mark DONE until user confirms.
  </UserTesting>

  <GitWorkflow>
    - Commit only after completing a subphase or logical group of related tasks.
    - Commit message must include author name (e.g., "Author: [Name] - ...").
    - Before starting a new phase, run git diff to verify repo state.
  </GitWorkflow>

  <DevelopmentStandards>
    - No lint errors in modified files.
    - Run python compile to check for syntax errors.
    - Database models must follow SQLAlchemy 2.0 declarative ORM style (`DeclarativeBase`, `Mapped`, `mapped_column`, `relationship`).
  </DevelopmentStandards>

  <GeneralPrinciples>
    - Clear communication, dependency awareness, clean handoffs.
    - Leave project stable and reviewable after each session.
  </GeneralPrinciples>
</AGENTS>
