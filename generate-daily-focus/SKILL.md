---
name: generate-daily-focus
description: Generate a concise daily focus note from an Obsidian or Markdown knowledge base. Use when the user asks what to prioritize today, requests up to three daily outcomes, or runs a daily planning automation based on active projects, open tasks, weekly plans, and recent processing reports. Read workspace-specific paths, priorities, exclusions, and output requirements from the invocation prompt or local instructions; generate recommendations without changing source tasks, owners, due dates, or project status.
---

# Generate Daily Focus

Turn current projects, open tasks, weekly intentions, and recent reports into no more than three evidence-backed outcomes for today. Keep all workspace-specific information in the invocation prompt or local workspace instructions, not in this skill.

## Resolve configuration

Before reading content, resolve the following from the invocation prompt, then from local instruction files such as `AGENTS.md`:

- knowledge-base root;
- governing schema or writing rules;
- project, task, weekly-plan, and recent-report locations;
- priority policy, including weekday or cadence rules;
- topics or data sources that must remain separate;
- excluded paths;
- output path, language, and frontmatter requirements.

Use explicitly supplied values over discovered defaults. If a missing value does not affect safety or routing, discover it from indexes, filenames, frontmatter, and directory descriptions. Mark material ambiguity as needing confirmation instead of guessing.

Do not embed discovered names, organizations, folder layouts, or personal priorities back into this skill.

## Read progressively

Read only enough context to rank today’s work:

1. Read local instruction and schema files.
2. Read the task index, current-week plan, and active-project index or frontmatter.
3. Read active project pages, focusing on outcomes, status, next actions, review dates, and blockers.
4. Collect incomplete formal tasks from their canonical source notes. Exclude completed tasks, templates, candidate tasks, generated duplicates, and configured archive paths.
5. Read the most recent relevant processing or triage report. Treat synchronization reports only as evidence of new input, not proof that the input has been reviewed.
6. Follow links only when needed to verify a recommendation.

Do not scan the entire knowledge base or archive without explicit authorization.

## Build the candidate pool

Collect candidates from:

- current-week outcomes and near-term plans;
- active project outcomes, review dates, next actions, and blockers;
- overdue, due-today, or otherwise time-constrained formal tasks;
- recent reports containing actionable exceptions, newly reviewed input, or items needing confirmation.

Convert scattered actions into an observable same-day outcome when the evidence supports it. Preserve links or paths to the canonical sources. Never turn an unapproved candidate, raw input, or model inference into a formal task or confirmed fact.

## Rank candidates

Apply the priority and cadence policy supplied in the invocation prompt. Then:

1. Prefer work that advances a primary outcome, clears a blocker, or meets a verified time constraint.
2. Keep supporting technical work attached to the project or outcome it serves unless it is explicitly managed as an independent project.
3. Use secondary or personal areas as cross-cutting work unless the supplied policy or verified urgency elevates them.
4. Prefer outcomes that can produce an observable result today.
5. Do not raise priority merely because a file is recent.
6. Allow fewer than three outcomes; never invent work to fill the list.

If two data domains must remain separate, compare only their priority metadata and do not merge or copy their source content.

## Write the daily note

Use the configured output path. If none is supplied, propose a path before writing when routing would be materially ambiguous.

Follow the workspace schema. When no schema is supplied, use minimal Markdown frontmatter:

```yaml
---
title: YYYY-MM-DD Daily Focus
summary: Up to three evidence-backed outcomes recommended for today.
tags: [daily-focus, ai-generated]
type: plan
status: active
created: YYYY-MM-DD
updated: YYYY-MM-DD
ai_generated: true
---
```

Use the requested language and this body structure:

```markdown
# YYYY-MM-DD Daily Focus

> AI-generated recommendations; owners, due dates, and project status are not implicitly confirmed.

## Core outcomes

### 1. Outcome
- Expected result:
- Why today:
- Suggested first step:
- Evidence:
- Needs confirmation: None, or a specific gap.

## Other signals

- Include only overdue items, blockers, waiting states, risks, or input exceptions that affect today’s choices.

## Sources used

- List only the pages, tasks, and reports actually used.
```

Do not add formal task tags to recommendations or copy source tasks into the note.

## Preserve idempotency

- Create the daily note when it does not exist.
- Regenerate the same path only when the existing file is clearly marked as AI-generated and local rules allow replacement.
- Preserve the original creation date and update the modification date.
- Do not overwrite human-maintained sections.
- Do not create version-suffixed duplicates.

## Verify

- Recommend no more than three outcomes.
- Apply every explicit priority, cadence, separation, and exclusion rule from the prompt.
- Cite at least one real source for each outcome.
- Distinguish confirmed tasks from candidates, raw inputs, sync events, and inferences.
- Leave source projects, tasks, owners, due dates, and statuses unchanged.
- Follow the configured schema, output path, language, and date.
- Ensure the skill files themselves contain no workspace-specific or private information.
