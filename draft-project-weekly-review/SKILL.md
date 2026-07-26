---
name: draft-project-weekly-review
description: Draft an evidence-backed weekly review for active projects in an Obsidian or Markdown knowledge base. Use when the user asks for a project weekly review, weekly status draft, active-project health review, summary of completed work and outcomes, blocker and decision review, next-action proposal, active-status recommendation, or suggested next review date. Read project paths, priority rules, domain boundaries, week window, and output location from the invocation prompt or workspace instructions. Produce an AI draft for human confirmation; never change project status, formal tasks, owners, due dates, decisions, or official logs.
---

# Draft Project Weekly Review

Create a concise, traceable review draft for each active project. Keep workspace-specific project names, domains, priorities, paths, and separation rules in the invocation prompt or local instructions.

## Resolve configuration

Read the invocation prompt and workspace instructions to resolve:

- knowledge-base root and governing schema;
- active-project index or project-page locations;
- weekly time window and timezone;
- daily processing reports, daily plans, logs, decisions, and task locations;
- priority, cadence, and domain-separation rules;
- rules for supporting technical work and independent-project eligibility;
- output path, language, and frontmatter requirements;
- excluded paths and sensitive-data boundaries.

Do not encode discovered private configuration into this skill.

## Read progressively

1. Read local instructions, schema, project index, and report-writing rules.
2. Identify active projects from canonical frontmatter or the configured project index.
3. Read each active project page, focusing on intended outcome, current status, next actions, blockers, review date, and AI-maintained sections.
4. Read weekly daily-processing reports and daily-focus notes.
5. Read only the weekly logs, confirmed decisions, and canonical formal tasks connected to each project.
6. Follow source links only when needed to verify a claimed completion, result, blocker, or decision.

Do not scan the full knowledge base or archive. Do not treat file modification time alone as evidence of project progress.

## Build evidence by project

For each project, classify evidence as:

- completed work: canonical task completion or explicit confirmed record;
- outcome: observable delivery, decision, metric change, validation, or resolved blocker;
- blocker: current obstacle supported by a source;
- decision: confirmed decision only, not a proposal or meeting remark;
- next action: existing formal task or clearly labeled recommendation;
- status signal: evidence supporting continuation, pause, completion, or review;
- missing evidence: expected information not recorded during the week.

Keep facts, recommendations, and items needing confirmation visibly separate. When evidence is absent, write the configured equivalent of “not recorded this week.”

## Handle supporting work

- Attribute supporting technical or operational work to the project outcome it serves.
- Do not create a separate project merely because the work produced code, automation, documentation, or a reusable component.
- Recommend independent-project consideration only when the configured eligibility criteria are all supported, such as an independent user, explicit deliverable, sustained maintenance, and cross-project reuse.
- Keep separated domains or organizations isolated; compare only high-level status metadata when configured.

## Draft each project section

Use the requested language and this structure:

```markdown
## Project name

- Work completed:
- Outcomes produced:
- Current blockers:
- New confirmed decisions:
- Next actions:
- Active-status recommendation:
- Suggested review date:
- Needs human confirmation:
- Evidence:
```

Rules:

- Link every substantive claim to a project page, task, report, log, or confirmed decision.
- Explain the evidence behind a status recommendation.
- Do not invent an owner, date, result, metric, or decision.
- A suggested review date is a recommendation, not a project-field update.
- Do not turn proposed next actions into formal tasks.

## Generate the weekly draft

Follow the configured schema and stable weekly output path. Include:

```markdown
# Weekly Project Review Draft

> AI-generated draft for human confirmation.

## Portfolio overview
## Project reviews
## Cross-project dependencies
## Decisions needing confirmation
## Proposed focus for next week
## Sources used
```

Keep cross-project observations abstract enough to respect configured data-separation boundaries.

## Boundaries

- Do not modify project pages, status fields, review dates, owners, or deadlines.
- Do not create, complete, merge, or delete formal tasks.
- Do not promote meeting statements into confirmed decisions.
- Do not write the draft into an official journal or review log without separate human approval.
- Do not move, archive, or delete source material.
- Do not expose sensitive source details beyond what the configured report permits.

## Preserve idempotency

- Repeated runs for the same week use the configured stable draft path.
- Preserve human-maintained sections according to workspace rules.
- Do not create version-suffixed duplicates.
- Re-running with new evidence updates recommendations but does not rewrite source records.

## Verify

- Every active project is included or explicitly listed as lacking evidence.
- Completed work is not confused with produced outcomes.
- Decisions are confirmed and traceable.
- Next actions are either canonical tasks or clearly labeled recommendations.
- Status and review-date suggestions remain draft recommendations.
- Supporting work remains attached to the project it serves unless all independent-project criteria are evidenced.
- Separated domains remain isolated.
- The skill files contain no workspace-specific or private information.
