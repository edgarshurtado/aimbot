# RED Task Subagent Prompt Template

Use this template when dispatching a subagent for a RED (test-writing) task from a TDD plan.

```
Task tool (general-purpose):
  description: "Write failing tests for [feature name]"
  prompt: |
    You are writing failing tests for: [feature name]

    ## Task Description

    [FULL TEXT of Task N.1 from the plan — paste it here, don't make subagent read file]

    ## Context

    [Scene-setting: what was built before this, where files live, relevant architecture]

    ## Before You Begin

    If ANYTHING is unclear about:
    - What requirements to test
    - Where test files should go
    - What testing framework/patterns to follow
    - How to import modules that don't exist yet

    **Ask now.** Don't guess.

    ## Your Job

    1. Write ALL tests specified in the task
    2. Tests MUST reference the implementation module (even though it doesn't exist yet)
    3. Each test should map to a specific requirement from the design
    4. Include edge cases listed in the task
    5. Run ONLY YOUR test file(s): [exact test file path(s)]
       They MUST ALL FAIL (module not found / function not found)
       Do NOT run the full test suite — other agents may be working in parallel
    6. Commit ONLY your test files (do NOT use `git add .`):
       `git add [test file paths] && git commit -m "test: add failing tests for [feature]"`

    ## Critical: Tests Must FAIL

    If any test passes, something is wrong:
    - You might be testing existing code by accident
    - You might be importing from the wrong module
    - The implementation might already exist

    **Every test must fail.** That's the point of RED.

    ## Response Format

    Respond with EXACTLY one of the following lines and nothing else:
    - `SUCCESS` — all tests written and all fail as expected
    - `FAILURE <reason>` — single line explaining what went wrong (e.g., "3 of 5 tests pass unexpectedly", "import error prevents tests from running")

    No preamble, no explanation, no summary. Just the single line above.
```
