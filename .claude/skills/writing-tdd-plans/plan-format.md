# TDD Plan Output Format

Shared format for TDD implementation plans. Both writing-tdd-plans and debating-tdd-plans produce plans in this format, compatible with executing-tdd-plans.

## Quick Reference: Required Fields Per Task

| Field | RED | GREEN | REVIEW |
|-------|-----|-------|--------|
| **Type** | RED (Test Writing) | GREEN (Implementation) | REVIEW (Adversarial) |
| **Depends on** | Previous feature's REVIEW, or none (also serialize if file overlap with parallel features) | Same feature's RED | Same feature's GREEN |
| **Design requirements** | Verbatim from design | Reference RED task | Verbatim from design |
| **Files** | Exact paths to create | Exact paths to create/modify | Files to review |
| **Spec** | Test cases table + key assertions | Implementation spec + DI registration table + endpoint bindings | Review checklist + startup verification + tests for any gaps found |
| **Verification** | Command + "ALL tests FAIL" | Command + "ALL tests PASS" | Verdict: PASS/FAIL |
| **Commit** | `test: add failing tests for [feature]` | `feat: implement [feature]` | `test: add adversarial tests for [feature]` |

## Incremental Commits Are Mandatory

Every task ends with a git commit. The plan must specify the commit message:

- **RED:** `git commit -m "test: add failing tests for [feature]"`
- **GREEN:** `git commit -m "feat: implement [feature]"`
- **REVIEW:** `git commit -m "test: add adversarial tests for [feature]"`

## Detail Level

**Core principle: The plan locks down design decisions. The executor makes implementation decisions.**

If the executor needs to decide function signatures, data types, error conditions, or API contracts — the plan wasn't detailed enough. The plan author has full context (design doc, codebase, debate log); the executor subagent has only the task spec.

**A plan that vaguely summarizes what to do is too short. A plan that pre-writes the full code is too verbose.**

The sweet spot: detailed specifications that tell the executor exactly WHAT to build, without writing the code for them. The executor (a capable subagent) writes the actual code from the spec.

### Design Decisions vs Implementation Decisions

| Decided by Plan (design decisions) | Decided by Executor (implementation decisions) |
|-------------------------------------|------------------------------------------------|
| Function/method signatures with types | Variable names, internal control flow |
| Data structures and interfaces | Private helper methods |
| Error conditions and error types returned | Try/catch placement, logging format |
| Validation rules and business logic rules | Code organization within a file |
| API contracts (inputs, outputs, status codes) | Framework-specific syntax, import order |
| Which edge cases to handle and how | Test assertion style, fixture setup mechanics |
| Concrete test inputs and expected outputs | Test helper utilities, setup/teardown code |

### Before/After Examples

**RED task — too abstract vs detailed enough:**

Too abstract:
```
| test_create_user | Creates a user | User is created |
| test_invalid_email | Bad email | Returns error |
```

Detailed enough:
```
| test_create_user_success | POST /users with {"name": "Alice", "email": "alice@example.com"} | 201, body has id (uuid), name="Alice", email="alice@example.com", created_at (ISO 8601) |
| test_create_user_duplicate_email | POST /users with email "existing@example.com" (already in DB) | 409 Conflict, body: {"error": "email_taken", "message": "..."} |
| test_create_user_invalid_email | POST /users with email "not-an-email" | 422, body: {"error": "validation_error", "fields": {"email": "invalid format"}} |
```

**GREEN task — too abstract vs detailed enough:**

Too abstract:
```
- Create UserService that handles CRUD operations
- Add proper validation and error handling
```

Detailed enough:
```
- Create `UserService` class:
  - `create_user(name: str, email: str) -> User` — validates email format (regex: `^[^@]+@[^@]+\.[^@]+$`), checks uniqueness against DB, returns User or raises `DuplicateEmailError` / `ValidationError`
  - `get_user(user_id: UUID) -> User | None` — returns None if not found (caller decides 404 vs skip)
- Interfaces/types: `User(id: UUID, name: str, email: str, created_at: datetime)`
- Error types: `DuplicateEmailError(email: str)`, `ValidationError(fields: dict[str, str])`
```

### Detail Checklist

- Specify **what to test**: test names, scenario, **concrete input values and expected outputs** — not full test function bodies
- Specify **what to implement**: functions/classes, **signatures with types**, behaviors, constraints — not full implementation code
- Specify **exact file paths** — not "create a test file for the feature"
- Include **verification commands** with expected outcomes — not "run the tests"
- Quote **design requirements verbatim** in each task — don't reference the design doc
- Include **key assertions/edge cases** the executor must not miss — not every assertion line
- Specify **error conditions** with concrete error types and responses — not "add proper error handling"
- Specify **validation rules** concretely — not "validate input"
- Specify **DI registrations** for every constructor dependency of new classes — not "register the service in DI"
- Specify **parameter binding sources** for web endpoint parameters — not "create a GET endpoint with these parameters"

## Save Location

**Always use multi-file format** — save as a subfolder under `docs/plans/`, regardless of plan size:

```
docs/plans/{plan-name}/
  README.md                    # Header, dependency graph, file index, execution instructions
  task-0-scaffolding.md        # Task 0 (if present)
  feature-1-{name}.md          # Triplet 1: RED/GREEN/REVIEW
  feature-2-{name}.md          # Triplet 2: RED/GREEN/REVIEW
  ...
  integration.md               # Integration triplet
```

Each feature file contains the complete triplet (N.1 RED, N.2 GREEN, N.3 REVIEW) for that feature. The README.md contains the plan header, a file index table mapping each file to its feature and dependencies, the dependency graph, and execution instructions.

**README.md file index table:**

```markdown
## Plan Files

| File | Feature | Depends On |
|------|---------|------------|
| task-0-scaffolding.md | Project scaffolding | None |
| feature-1-auth.md | Authentication | Task 0 |
| feature-2-users.md | User Management | Task 0 |
| integration.md | End-to-end integration | All features |
```

**Multiple PRs (only when user explicitly requests):** If the user asks to split execution into multiple PRs, each PR gets its own numbered subfolder: `docs/plans/{NN}-{plan-name}-{pr-descriptor}/` where `{NN}` is the zero-padded PR number (01, 02, ...). The number indicates execution order — PRs must be executed in numerical sequence. Each plan must be self-contained and independently executable. **CRITICAL: The plan MUST still cover the ENTIRE design document.** Never omit features from the plan because "they belong in a different PR." Plan everything first, then split into PRs if requested. If not requested, produce a single plan covering all features.

## Header Template (README.md)

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** This plan is split across multiple files. Read this README for the
> dependency graph and execution order, then read individual feature files for task details.
> Dispatch a fresh subagent per task using the Task tool (subagent_type: "general-purpose").

**Goal:** [One sentence from design]

**Architecture:** [2-3 sentences from design]

**Tech Stack:** [Key technologies/libraries]

**Design Document:** [path/to/design.md]

## Plan Files

| File | Feature | Depends On |
|------|---------|------------|
| ... | ... | ... |

---
```

## Triplet Templates

For each feature/component identified in the design:

### Task N.1 — Write Failing Tests (RED)

```markdown
### Task N.1: Write failing tests for [Feature Name]

**Type:** RED (Test Writing)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** [previous feature's Task M.3, or none if first]

**Design requirements being tested:**
- [Requirement A from design doc]
- [Requirement B from design doc]
- [Edge case X from design doc]

**Files:**
- Create: `tests/exact/path/to/test_feature.py`

**Test cases:**

Inputs and outputs must be concrete values, not placeholders. The executor should be able to write assertions directly from this table without inventing test data.

| Test | Scenario | Expected |
|------|----------|----------|
| test_requirement_a | [Concrete setup/input values] | [Concrete expected outcome with specific values. Verifies: Requirement A] |
| test_requirement_b | [Concrete setup/input values] | [Concrete expected outcome with specific values. Verifies: Requirement B] |
| test_edge_case_x | [Concrete edge input values] | [Concrete expected behavior. Verifies: Edge case X] |

**Data structures referenced:** [Optional — types/interfaces the tests reference, with fields and types. Include when tests use domain objects that the executor might define differently without guidance.]

**Setup:** [Fixtures or test data needed — describe what, not how]

**Key assertions:** [Non-obvious assertions the executor must include, e.g., "soft-delete means record stays in DB with deleted_at set"]

**UI deliverable rule:** If the feature creates a UI component (page, modal, widget, settings panel), at least one test MUST verify the component **renders** — not just that store actions dispatch or services resolve from DI. Store/action tests can pass without the component file existing. The GREEN step (YAGNI) will only create what tests require, so a feature with only state management tests produces only state management code — no component. Include a rendering test (e.g., bUnit, React Testing Library) that imports and renders the component. **If the codebase lacks component rendering test infrastructure** (no bUnit, no React Testing Library, etc.), establishing it is a Task 0 or feature prerequisite — NOT a reason to exclude the component from the plan. A design that specifies "settings page with Connect/Disconnect" requires the component to exist, not just the state management behind it.

**Side-effect handler rule:** If the feature includes side-effect handlers (Fluxor effects, Redux thunks/sagas, MobX reactions) that perform external operations (JS interop, HTTP calls, hub methods, WebSocket sends), at least one test MUST verify each handler's side effect fires — independent of any component rendering test. Mock the external dependency, dispatch the triggering action, assert the handler called the dependency. Store/state tests verify reducers update state but do NOT exercise effects. Component rendering tests (bUnit, React Testing Library) CAN exercise effects but may be skipped due to infrastructure friction. Without standalone effect tests, the GREEN step creates the handler file as a stub — "file exists" passes but delivers no functionality.

**Verification:**
Run: `[exact test command]`
Expected: ALL tests FAIL (function/module not found)

**Commit:** `git commit -m "test: add failing tests for [feature]"`
```

### Task N.2 — Implement to Pass Tests (GREEN)

```markdown
### Task N.2: Implement [Feature Name]

**Type:** GREEN (Implementation)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task N.1 must be complete (failing tests must exist)

**Goal:** Write the minimal code to make ALL tests from Task N.1 pass.
Do NOT add functionality beyond what the tests require. YAGNI.

**UI styling rule:** If this task creates a user-facing UI component (page, modal, panel, widget), the component MUST be styled to match the codebase's existing visual patterns. Examine existing styled components and the CSS/design system (variables, themes, component conventions) — then apply consistent styling. Unstyled HTML with CSS class names that have no corresponding CSS rules is not a deliverable. Matching the codebase's visual language is part of the minimum implementation, not "extra functionality."

**Files:**
- Create/Modify: `src/exact/path/to/feature.py`
- Reference: `tests/exact/path/to/test_feature.py` (already exists from N.1)

**What to implement:**

Function/class signatures must include types. The executor should know exactly what to create without inventing APIs.

- [Function/class to create with typed signature: `func_name(param: Type) -> ReturnType` — and key behavior]
- [How it connects to existing code — imports, integrations]
- [Constraints: what it must/must not do]
- [Any non-obvious implementation detail the executor needs to know]

**Interfaces/types to create:** [Types, interfaces, or data classes this task introduces — with fields and types. Omit if no new types.]

**Error handling:**

| Condition | Error Type | Response |
|-----------|-----------|----------|
| [Specific error condition] | [Concrete exception/error class] | [What happens: return value, HTTP status, error body, etc.] |

**Behavioral rules:** [Validation logic, business rules, ordering guarantees, idempotency requirements — anything the tests assert that the implementation must satisfy. Omit if fully covered by the test cases table.]

**DI registration table (MANDATORY):** List ALL constructor dependencies for each new class this task creates. For each dependency, state whether it's already registered in the correct host's DI container, or must be registered by this task. If not registered, specify the exact registration call and which file to add it to. The executor has no context beyond this task — an unlisted dependency becomes a missing DI registration at runtime.

| Class | Dependency | Registered? | Registration |
|-------|-----------|------------|--------------|
| [NewClass] | [IDependency] | Yes (Task X) / No | `services.AddSingleton<IDep, Impl>()` in [File.cs] |

Common gaps: `TimeProvider` (not auto-registered — use `services.AddSingleton(TimeProvider.System)`), `IHttpClientFactory` (needs `AddHttpClient()`), services in one host needed in another (Agent DI ≠ MCP server DI ≠ WASM DI).

**Endpoint parameter bindings (web endpoint tasks only):** If this task creates HTTP endpoints (Minimal API, MVC, etc.), specify the parameter binding source for EVERY parameter. Framework-inferred binding often guesses wrong — especially for GET endpoints where complex types are inferred as `[FromBody]` (which is invalid for GET). Be explicit with attributes.

| Endpoint | Parameter | Source |
|----------|-----------|--------|
| [GET /path] | [param] | `[FromQuery]` / `[FromServices]` / `[FromRoute]` |

**Verification:**
Run: `[exact test command]`
Expected: ALL tests PASS

**Commit:** `git commit -m "feat: implement [feature]"`
```

### Task N.3 — Adversarial Review

```markdown
### Task N.3: Adversarial review of [Feature Name]

**Type:** REVIEW (Adversarial)
**Dispatch as:** Fresh subagent via Task tool
**Depends on:** Task N.2 must be complete (implementation must exist and tests pass)

**Your role:** You are an adversarial reviewer with TWO equally important jobs:
1. **Verify requirements** — confirm the implementation actually delivers what was
   specified. Bug-free code that doesn't follow the requirements is a FAIL.
2. **Break it** — find bugs, edge cases, and gaps. Assume the implementation is wrong
   until proven otherwise.

**Design requirements to verify:**
- [Requirement A from design doc — verbatim]
- [Requirement B from design doc — verbatim]
- [Edge case X from design doc — verbatim]

**Review checklist:**

**Requirements verification (does it do what was asked?):**

1. **Requirements compliance** — Read the implementation and compare against EACH
   requirement listed above. Treat requirements as a checklist: each one must map to
   actual code. Is anything missing? Misinterpreted? Partially implemented? Over-built?
   A bug-free implementation that doesn't match the requirements is a FAIL.

2. **Completeness** — Are ALL required features present and working as specified?
   Does any requirement lack corresponding implementation?

**Breaking the implementation (does it work correctly?):**

3. **Test adequacy** — Do the tests actually test what they claim? Could the tests pass
   with a WRONG implementation? If yes, write additional tests that expose gaps.

4. **Edge cases** — Try to break it. Think of inputs the tests don't cover.
   If you find uncovered cases, write tests for them and run them.

5. **Error handling** — What happens with invalid input? Null? Empty? Huge? Concurrent?

6. **Integration** — Does it work with the rest of the system? Any assumptions that
   could break when connected to real code?

7. **Visual consistency (UI features only)** — If this feature includes a UI component:
   Does it use the codebase's existing CSS variables/design tokens? Are all CSS class
   names defined with actual styling rules? Does it look visually consistent with existing
   components? An unstyled component that relies on class names with no CSS definitions
   is a FAIL — it means the GREEN step skipped styling.

8. **Startup verification** — Build the solution and start the application(s) this
   feature modifies. If the app fails to start (DI resolution errors, endpoint mapping
   errors, missing service registrations), this is a CRITICAL FAIL. Unit tests mock DI
   and pass even when the real container can't build the dependency graph. Don't wait
   for the integration triplet to catch what a simple `dotnet run` / `npm start` reveals.

**You MUST actively try to break the implementation and find gaps.** If you find coverage
gaps, edge cases, or ways the existing tests could pass with a wrong implementation,
you MUST write and run additional tests targeting those gaps. If the existing tests are
comprehensive and you find no gaps after thorough analysis, you may skip writing tests
— but you must explain why the existing coverage is sufficient.

**What to produce:**
- List of issues found (Critical / Important / Minor)
- Additional tests written and their results (if gaps were found)
- If no tests written: explanation of why existing coverage is sufficient
- Verdict: PASS (all requirements implemented correctly, no critical/important issues)
  or FAIL (requirements missing/misimplemented OR critical/important bugs found)

**If FAIL:** Create fix tasks (following same triplet: test the fix, implement fix,
re-review). Append them to the plan.

**If additional tests written:** `git commit -m "test: add adversarial tests for [feature]"`
```

## Special Task Types

### Task 0 — Scaffolding (optional)

If features share infrastructure (database setup, config, project structure, dependency installation), create a **Task 0** before any triplets. This is the only task that doesn't follow the triplet pattern. Keep it minimal — just enough for the first triplet to run.

**Integration test infrastructure is a Task 0 concern.** If the plan's integration triplet needs real services (databases, message brokers, caches) and the project lacks the infrastructure to run them in tests — the plan MUST include setup in Task 0: package installation (e.g., testcontainers, docker-compose), container/fixture definitions, seed data scripts. An integration test that assumes testcontainers exist but no task installs the package will fail at execution time.

**UI component test infrastructure is a Task 0 concern.** If the design includes ANY UI component (page, modal, panel, widget), you MUST check whether the project has component rendering test packages installed (bUnit for Blazor, React Testing Library for React, Vue Test Utils for Vue, etc.). **How to check:** search project files for package references (e.g., `bunit` in .csproj, `@testing-library/react` in package.json). If the package is not installed, Task 0 MUST install it and create a minimal test scaffold (test project, configuration, example test that renders a trivial component). Without this, RED tasks for UI features cannot write rendering tests, agents will fall back to store/state-only tests, and the GREEN step will never create the actual component. This is the #1 cause of UI components being silently dropped from plans.

### Integration Triplet (final)

After all feature triplets pass, add one final triplet for end-to-end integration.

**Why this matters:** Feature triplets test components in isolation with mocks. Every mock is a lie — it asserts two components work together without proving it. The integration triplet verifies what mocks hide.

**The Mock Trap:** When every feature is tested with mocks, all feature tests pass even when:
- A service is registered in DI but the implementation is a stub (`NotImplementedException`)
- A decorator/middleware exists in code but is never applied to the pipeline
- A project reference is missing so the app can't compile with its real dependencies
- A DI registration is missing so the app crashes at startup resolving a service

**The integration triplet MUST cover these categories:**

1. **Startup/DI verification** — Can each application/host actually start and resolve all registered services? Build the real DI container (or start the real app) and verify key interfaces resolve to real implementations (not stubs). This catches: missing DI registrations, missing project references, misconfigured service lifetimes, stub implementations that survived mock-based feature testing.

2. **Mock boundary verification** — Every mock used in a feature test represents a real connection that was NOT tested. For each mock used in feature tests, the integration test must exercise the REAL connection. Example: if Feature A mocked `ITokenExchangeService`, integration must test the real `MsalTokenExchangeService` in the actual OAuth callback flow.

3. **Pipeline/middleware hookup** — Decorators, middleware, filters, and interceptors tested in isolation must be verified as actually applied in the real pipeline. Example: if a feature tested `TokenInjectingMcpTool` as a standalone decorator, integration must verify it's actually wrapping tool calls in the real pipeline.

4. **End-to-end data flows** — Trace each primary user-facing flow from entry point to final effect, using real implementations for internal components. Only mock truly external services (third-party APIs with no local alternative).

**To build the integration task list, create a Mock Boundary Table** during planning. **The table MUST have one row per feature** — not just features that use `Mock<>`. UI features tested at the store/state level hide real connections too: store effects that call backend APIs, hub methods never invoked against a running server, components that may not exist because no rendering test required them. List the untested boundary even when the "Mock Used" column is "None (store-level tests only)."

| Feature | Mock Used | Real Connection Hidden | Integration Test |
|---------|-----------|----------------------|-----------------|
| *Example:* F2 (MCP Tools) | `Mock<ICalendarProvider>` | MCP server DI can't resolve real provider | Start MCP server, resolve `ICalendarProvider` |
| *Example:* F1 (Decorator) | Tested decorator standalone | Decorator isn't applied in pipeline | Make real MCP call, verify decorator intercepts |
| *Example:* F7 (OAuth) | `Mock<ITokenExchangeService>` | Real MSAL impl is a stub | Real OAuth callback exchanges code for tokens |
| *Example:* F5 (Settings UI) | None (store-level tests only) | Store effects → real hub methods never tested; component may not exist | Connect store to real hub, invoke effect, verify hub method called; verify component file exists |

**Integration Test Prerequisites Check (MANDATORY):** For each row in the Mock Boundary Table where the real connection can be tested with fixtures, testcontainers, or local service emulators — verify the plan includes a task (Task 0 or feature prerequisite) that: (1) installs required packages (testcontainers library, docker-compose, test SDK), (2) creates container/fixture definitions (docker-compose.yml, testcontainer configs, database migration scripts for test), and (3) provides seed data or factory methods if tests need realistic data. If the project already has this infrastructure, note "existing" — don't duplicate. If a prerequisite is missing and no task creates it, the integration test is unrunnable.

**The UI Integration Trap:** UI features tested only at the store/state level (Redux stores, Fluxor, Vuex) are the most commonly missed integration gap. Store tests pass without: the component file existing, effects connecting to a real backend, or hub/API methods accepting the expected parameters. **Every UI feature MUST have at least one integration test that connects store effects to a real backend endpoint** (SignalR hub, REST API, WebSocket) and verifies the round-trip.

**Template:**
- **N.1:** Write integration tests covering all four categories. Include the Mock Boundary Table in the task spec with **one row per feature** listing each mock or untested boundary and the corresponding real-connection test. **Prerequisites:** List any packages, containers, or fixtures that must exist for these tests to run — and verify Task 0 or a prior feature task creates them. If prerequisites are missing from the plan, flag this as a blocker before writing tests.
- **N.2:** Fix integration failures. Expect: missing DI registrations, project references, stub replacements, pipeline hook-ups, **missing test infrastructure (packages not installed, containers not configured)**. This is often NOT a no-op.
- **N.3:** Final adversarial review against ALL design requirements as a checklist, plus full build and full test suite verification across ALL features.

## Execution Instructions

The plan must include this section after the tasks:

```markdown
## Execution Instructions

**Recommended:** Execute using subagents for fresh context per task.

For each task, dispatch a fresh subagent using the Task tool:
- subagent_type: "general-purpose"
- Provide the FULL task text in the prompt (don't make subagent read this file)
- Include relevant context from earlier tasks (what was built, where files are)

**Execution order:**
- Tasks within a triplet are strictly sequential: N.1 → N.2 → N.3
- Independent triplets MAY run in parallel ONLY if they have zero file overlap (no shared created/modified files)
- Dependent triplets are sequential: complete triplet N before starting triplet M
- If the dependency graph says two features are parallel, they MUST NOT modify any overlapping files — this was verified during planning

**Never:**
- Skip a test-writing task (N.1) — "I'll write tests with the implementation"
- Skip an adversarial review task (N.3) — "The tests already pass, it's fine"
- Combine tasks within a triplet — each is a separate subagent dispatch
- Proceed to N.2 if N.1 tests don't compile/exist
- Proceed to N.3 if N.2 tests don't pass
- Proceed to next triplet if N.3 verdict is FAIL
```
