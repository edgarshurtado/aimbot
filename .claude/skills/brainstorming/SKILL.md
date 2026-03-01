---
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."
---

# Brainstorming Ideas Into Designs

## Overview

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design in small sections (200-300 words), checking after each section whether it looks right so far.

## How to Interact With the User

**Always use the `AskUserQuestion` tool** for every question or choice you present to the user during this process. Never ask questions via plain text output — use the tool so the user gets a structured, interactive prompt.

- For multiple-choice questions: provide 2-4 options with descriptions via the tool's `options` field
- For validation checks ("does this section look right?"): use options like "Looks good" / "Needs changes"
- For open-ended input: provide contextual options but rely on the user selecting "Other" to type freely
- Keep `header` short (max 12 chars) — e.g., "Purpose", "Approach", "Validation"
- You may ask up to 4 questions per `AskUserQuestion` call when questions are independent

## The Process

**Understanding the idea:**
- Check out the current project state first (files, docs, recent commits)
- Use `AskUserQuestion` to ask questions one at a time to refine the idea
- Prefer multiple choice questions when possible, but open-ended is fine too
- Only one question per message - if a topic needs more exploration, break it into multiple questions
- Focus on understanding: purpose, constraints, success criteria

**Exploring approaches:**
- Propose 2-3 different approaches with trade-offs
- Use `AskUserQuestion` to present options with your recommendation first (add "(Recommended)" to its label) and reasoning in the descriptions
- Lead with your recommended option and explain why

**Presenting the design:**
- Once you believe you understand what you're building, present the design
- Break it into sections of 200-300 words
- Use `AskUserQuestion` after each section to check whether it looks right so far (options: "Looks good" / "Needs changes")
- Cover: architecture, components, data flow, error handling, testing
- Be ready to go back and clarify if something doesn't make sense

## After the Design

*Documentation:**
- Write the validated design to `docs/plans/YYYY-MM-DD-<topic>-design.md`
- Use elements-of-style:writing-clearly-and-concisely skill if available
- Commit the design document to git

## Key Principles

- **Always use `AskUserQuestion`** - Never ask questions via plain text; always use the tool
- **One question at a time** - Don't overwhelm with multiple questions
- **Multiple choice preferred** - Easier to answer than open-ended when possible
- **YAGNI ruthlessly** - Remove unnecessary features from all designs
- **Explore alternatives** - Always propose 2-3 approaches before settling
- **Incremental validation** - Present design in sections, validate each
- **Be flexible** - Go back and clarify when something doesn't make sense