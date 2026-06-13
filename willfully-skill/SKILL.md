---
name: willfully-skill
description: Create, review, and refine agent skills for Pi and other Agent Skills-compatible environments. Use when designing a new skill, improving an existing SKILL.md, tightening scope, writing better frontmatter, deciding whether to add helper files, or generating realistic trigger tests for a skill.
---

# Willfully Skill

Create skills deliberately.

Use this skill to design high-quality agent skills that are specific, discoverable, concise, actionable, and easy to maintain.

Favour simple, focused skills over broad ones. Capture repeatable workflows, not vague capabilities.

Ask the user focused questions early. Good skill design depends on understanding the real problem, the repeated workflow, and why the skill should exist at all.

## Core principles

1. Skills should capture repeatable workflows.
2. Start from concrete use cases, not file structure.
3. The context window is a public good: keep skill content lean.
4. Strong frontmatter is critical, especially the description.
5. Keep scope narrow and explicit.
6. Pick the right degree of freedom:
   - high freedom: prose instructions when judgement is needed
   - medium freedom: patterns, pseudocode, or helper files when some structure helps
   - low freedom: specific helper files when correctness or consistency is fragile
7. Use extra files only when they add real leverage.
8. Skills should compose cleanly with other skills and avoid unnecessary assumptions about exclusive control.
9. Ask the user enough questions to justify the skill's existence and scope before drafting.
10. Review and iterate from real usage.

## What a skill is

A skill is a directory with a required `SKILL.md` file and optional helper files.

```text
skill-name/
├── SKILL.md
├── template.SKILL.md
├── helper-script.py
├── example.json
└── subskills/
```

### File guidance

Prefer the simplest possible layout. Keep helper files at the skill root by default.

- `SKILL.md`: the main instructions and frontmatter
- root-level helper files: templates, scripts, examples, or other supporting files
- `subskills/`: optional, only when this skill is intentionally a composite made of smaller skills

Do not add extra files unless they materially help the agent do the task.

Avoid clutter such as:
- `README.md` inside the skill folder
- changelogs
- auxiliary notes about the authoring process
- duplicate documentation spread across multiple files

## Progressive disclosure

Design skills in layers:

1. Frontmatter: always visible to the model, so it must clearly say what the skill does and when to use it.
2. `SKILL.md` body: loaded when the skill is relevant; keep it focused on the workflow.
3. Helper files: only add them when they reduce repetition, improve determinism, or prevent SKILL.md from becoming bloated.

Keep `SKILL.md` concise. Move material into helper files only when that improves clarity.

If the skill becomes a composite of smaller skills, keep the main flow in `SKILL.md` and place the smaller pieces in `subskills/`.

## Modes

### Mode 1: Create a new skill

Work through these phases in order.

#### Phase 1: Clarify the skill

Ask the user and gather or infer:
- the skill's goal
- 2-3 concrete use cases
- realistic trigger phrases or user wording
- expected outputs or outcomes
- intended users or environment
- non-goals and boundaries
- whether the workflow is repeated enough to justify a skill
- why this should be a skill instead of a one-off prompt or ordinary task

If the request is vague, stop and refine the use case before drafting.

#### Phase 2: Choose the right shape

Decide:
- should this be one skill or multiple smaller skills?
- should it be instructions-only?
- does it need a small number of helper files for deterministic validation, transformation, or templates?
- should it be a composite skill with `subskills/`?
- is any part environment-specific and worth declaring in `compatibility`?

Ask the user when the scope or intended shape is unclear.

Prefer the smallest viable skill.

#### Phase 3: Write frontmatter

Produce:
- a kebab-case name
- a precise description containing:
  - what the skill does
  - when to use it
  - realistic trigger phrases or contexts
  - enough detail to reduce undertriggering without becoming vague or spammy

Use optional frontmatter only when useful and supported by the target environment.

Pi supports these frontmatter fields:
- `name`
- `description`
- `license`
- `compatibility`
- `metadata`
- `allowed-tools`
- `disable-model-invocation`

Do not put angle brackets in the description.

#### Phase 4: Write the skill body

Structure the skill so another agent can use it reliably.

Prefer sections like:
- purpose or overview
- instructions or workflow
- examples
- troubleshooting
- setup, if required

Write instructions in clear imperative language. Be concrete and operational. Avoid vague advice.

Include examples whenever they help clarify:
- when the skill should trigger
- what the workflow looks like
- what output is expected

If important details are missing, ask the user rather than inventing process or scope.

#### Phase 5: Validate and test

Generate realistic tests:
- prompts that should trigger the skill
- prompts that should not trigger the skill
- paraphrases and near-misses
- edge cases where scope might be confused

If available, run `quick_validate.py` against the skill directory.

### Mode 2: Review an existing skill

Evaluate the skill across these dimensions.

#### Scope
- Is it too broad?
- Does it mix unrelated workflows?
- Should it be split?

#### Discoverability
- Does the description clearly say what it does and when to use it?
- Are trigger phrases realistic?
- Is it likely to undertrigger because it is too vague or too technical?
- Is it likely to overtrigger because it is too broad?

#### Instruction quality
- Are instructions actionable?
- Are steps explicit?
- Are examples present where useful?
- Is troubleshooting included where needed?

#### Structure
- Is the skill concise enough?
- Are helper files justified?
- Would a flat layout be clearer?
- Should this be a composite skill with `subskills/`?
- Is critical guidance in the right place?

#### Output

Provide:
- strengths
- weaknesses
- concrete rewrite suggestions
- improved frontmatter if needed
- questions to ask the user if the skill's purpose is underspecified
- suggested trigger and non-trigger tests

### Mode 3: Refactor a skill

When refactoring:
- tighten scope
- improve frontmatter
- simplify instructions
- reduce unnecessary context
- split large skills if necessary
- add examples or troubleshooting where needed
- extract repeated deterministic work into scripts when justified

## Authoring standards

### Good skills

A good skill:
- solves a repeatable problem
- has a clear boundary
- is easy to trigger correctly
- gives explicit guidance
- uses the smallest effective structure
- asks good questions before committing to scope or structure
- works well alongside other skills
- is concise but complete

### Weak skills

A weak skill is:
- vague
- overly broad
- mostly generic advice
- missing trigger language
- missing examples where they would help
- bloated with unnecessary files or prose
- too complex for its actual value

## Guidance on helper files

Recommend helper files only when they:
- validate inputs deterministically
- transform data reliably
- automate repeated setup or processing
- replace code the agent would otherwise rewrite over and over
- reduce fragile manual steps
- provide templates, boilerplate, or sample files that materially help

Keep them at the skill root by default.

If the skill is intentionally made of smaller reusable pieces, place them in `subskills/`.

Do not recommend extra files just to make a skill seem more advanced.

## Output expectations

When asked to create a skill, produce:
1. a recommended skill name
2. a draft frontmatter block
3. a proposed directory structure
4. a complete first draft of `SKILL.md`
5. any suggested helper files or `subskills/` entries with justification
6. trigger and non-trigger test prompts
7. suggested follow-up improvements

When asked to review or refactor, produce:
1. a diagnosis
2. specific improvements
3. revised text where appropriate
4. test prompts for validation

## Review checklist

Before finalizing, check:
- Is the workflow repeatable?
- Is the skill specific enough?
- Does the description say what and when?
- Are trigger phrases realistic?
- Are undertrigger and overtrigger risks addressed?
- Are non-goals clear?
- Are instructions explicit?
- Are examples included where useful?
- Are helper files or `subskills/` actually justified?
- Would this skill work well in Pi or another target environment?

## Style

Prefer:
- concise wording
- numbered or clearly sequenced steps
- explicit decisions
- concrete examples
- practical defaults
- minimal but sufficient structure
- British English throughout

Avoid:
- fluff
- abstract guidance without action
- unnecessary complexity
- duplicate content
- broad claims without scope boundaries

## Template helper

If helpful, use `template.SKILL.md` as a starting point for new skills.
