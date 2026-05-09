# GREEN Task Subagent Prompt Template

Use this template when dispatching a subagent for a GREEN (implementation) task from a TDD plan.

```
Task tool (general-purpose):
  description: "Implement [feature name]"
  prompt: |
    You are implementing: [feature name]

    ## Task Description

    [FULL TEXT of Task N.2 from the plan — paste it here, don't make subagent read file]

    ## Context

    [Scene-setting: what was built before, where tests live, relevant architecture]

    ## Failing Tests

    Tests from the RED phase exist at: [test file path]
    These tests currently FAIL because the implementation doesn't exist yet.

    ## Before You Begin

    If ANYTHING is unclear about:
    - The requirements or approach
    - Where implementation files should go
    - Dependencies or patterns to follow

    **Ask now.** Don't guess.

    ## Your Job

    1. Read the failing tests first — understand what they expect
    2. Write the MINIMAL code to make ALL tests pass
    3. Do NOT add functionality beyond what the tests require (YAGNI)
    4. Run ONLY this feature's test file(s): [exact test file path(s)]
       They must ALL PASS.
       Do NOT run the full test suite or global build commands (tsc, npm run build) —
       other agents may be working in parallel. The controller verifies the full suite after.
    5. Commit ONLY your implementation files (do NOT use `git add .`):
       `git add [implementation file paths] && git commit -m "feat: implement [feature]"`

    ## Critical: Minimal Implementation

    Your goal is to make the tests pass, nothing more.
    - Don't add error handling the tests don't check for
    - Don't add features the tests don't verify
    - Don't refactor or optimize prematurely
    - If the tests are wrong, report it — don't silently change them

    ## Critical: UI Components Must Be Styled

    If this task creates a user-facing UI component (page, modal, panel, widget),
    you MUST style it to match the codebase's existing visual patterns:
    1. Find the codebase's CSS/design system (CSS variables, theme tokens, existing styles)
    2. Examine 2-3 existing styled components for patterns (spacing, colors, shadows)
    3. Apply consistent styling — use the same CSS variables and visual language

    Unstyled HTML with class names that have no CSS rules is NOT a valid deliverable.
    Matching the codebase's visual language is part of minimum implementation, not "extra."

    ## Critical: Plan-Specified Wiring Is Mandatory

    After making tests pass, implement ALL file modifications listed in the task's
    **"Files"** section — even if no unit test directly exercises them.

    Unit tests verify components in isolation. The plan also specifies **wiring**:
    DI registrations, pipeline hookups, config entries, decorator application.
    These modifications are part of the task deliverable. Skipping them because
    "tests pass without it" produces dead code — a component that works in
    isolation but is never activated in the real system.

    **Checklist before committing:**
    - Every file listed under "Create" → exists
    - Every file listed under "Create" → implements described behaviors from the task
      spec, not stubbed with TODO/placeholder comments. A file that exists but contains
      `// TODO: implement later` or `// Stub: will do X in a future iteration` is NOT
      a completed deliverable — it means you created the file but skipped the behavior.
    - Every file listed under "Modify" → has the specified changes applied
    - If a "Modify" file doesn't need changes for tests to pass, implement
      the wiring changes anyway — the integration triplet verifies them later

    ## Self-Review Before Reporting

    Before reporting back, check:
    - All tests pass (run them, paste output)
    - Implementation is minimal (no extra features)
    - Code follows existing patterns in the codebase
    - No obvious bugs or security issues

    ## Response Format

    Respond with EXACTLY one of the following lines and nothing else:
    - `SUCCESS` — all tests pass
    - `FAILURE <reason>` — single line explaining what went wrong (e.g., "2 tests still failing in auth module", "cannot resolve dependency X")

    No preamble, no explanation, no summary. Just the single line above.
```
