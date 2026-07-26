---
name: reconcile-markdown-tasks
description: Audit and reconcile formal Markdown tasks in an Obsidian or Markdown knowledge base. Use when the user asks to reconcile task status, check completed tasks for missing completion dates, count open and newly completed tasks by category, find exact duplicates, identify missing category labels or broken task-source links, or run a daily task-status automation. Read task tags, category labels, exclusions, completion-date policy, and report location from the invocation prompt or workspace instructions. Never infer completion from prose or automatically merge, close, or delete tasks.
---

# Reconcile Markdown Tasks

Reconcile canonical task lines without creating dashboard copies or inferring task completion. Keep workspace-specific paths, labels, sensitive categories, and reporting rules in the invocation prompt or local instructions.

## Resolve configuration

Before scanning, read the invocation prompt and workspace instructions to resolve:

- knowledge-base root and governing schema;
- formal task tag;
- allowed category or area labels;
- archive, template, generated-output, and other excluded paths;
- completion-date syntax and timezone;
- whether missing completion dates may be written automatically;
- task dashboard or query pages that must not be treated as canonical copies;
- report path, language, and frontmatter requirements.

If automatic date repair is not explicitly authorized, run in audit-only mode. Never embed discovered private information back into this skill.

## Use the scanner

Run:

```bash
python3 scripts/reconcile_tasks.py \
  --root "<knowledge-base-root>" \
  --task-tag "#task" \
  --category-label "#area-a" \
  --category-label "#area-b" \
  --exclude "archive/" \
  --exclude "templates/" \
  --date YYYY-MM-DD
```

The script prints JSON and does not modify files by default.

Add `--apply-completion-date` only when the invocation prompt or workspace rules explicitly authorize appending the supplied date to already checked tasks that lack a completion date:

```bash
python3 scripts/reconcile_tasks.py ... --apply-completion-date
```

The scanner:

- reads Markdown files only;
- skips symlinks and configured paths;
- recognizes formal tasks by checkbox syntax and the configured task tag;
- appends `✅ YYYY-MM-DD` only to an already checked canonical task line;
- does not change unchecked tasks;
- reports exact normalized duplicates without merging them;
- reports tasks missing an allowed category label;
- checks wiki links in each task block and reports unresolved links;
- returns counts by category for open tasks and tasks completed on the supplied date.

Treat scanner output as evidence, not as permission to perform other edits.

## Enforce completion boundaries

- Never mark a task complete from meeting notes, status prose, source records, or semantic similarity.
- Never change `[ ]` to `[x]`.
- Never replace an existing completion date.
- Never interpret a checked candidate task as a completed formal task.
- Never create a second task in a dashboard or aggregate page.
- Never automatically merge duplicate tasks.
- Never close a task because another similar task is completed.
- Never delete task lines or source files.

If a checked task lacks a date but workspace policy does not authorize using today, report it as ambiguous. This is especially important on the first run, when historical tasks may predate the automation.

## Review the proposed changes

When date repair is enabled:

1. Run once without `--apply-completion-date`.
2. Review `missing_completion_dates`, counts, exclusions, and target files.
3. Confirm every proposed edit is limited to an already checked formal task.
4. Run with `--apply-completion-date`.
5. Run again in audit-only mode and confirm `missing_completion_dates` is empty or contains only intentionally skipped items.

For unattended automation, the invocation prompt may authorize the two-pass sequence in advance. Stop if the scan unexpectedly exceeds workspace batch limits or includes an excluded path.

## Generate the reconciliation report

Follow the configured schema and report path. Include:

- scan date and timezone;
- files scanned and formal tasks found;
- number of completion dates added;
- open and today-completed counts by category;
- checked tasks still missing dates;
- uncategorized tasks;
- exact duplicate groups;
- unresolved task-block links;
- skipped files and errors;
- explicit statement that no task was semantically completed, merged, or deleted.

Link each anomaly to its canonical file and line number. Do not copy tasks into the report as new checkboxes with the formal task tag.

## Preserve idempotency

- Repeated runs with the same date must not append a second completion marker.
- Existing completion dates remain unchanged.
- Reports use the configured stable daily path rather than version-suffixed duplicates.
- Updating a report must not modify human-maintained sections unless local rules explicitly allow it.
- Dashboard queries remain queries; do not materialize task copies.

## Verify

- Every modified line was already checked and lacked a completion date.
- The number of modified lines matches `completion_dates_added`.
- No unchecked task, candidate task, dashboard query, excluded path, or symlink was modified.
- Category counts reconcile with the scanned task inventory.
- Duplicate and broken-link findings are report-only.
- Source tasks, owners, due dates, priorities, and project status remain otherwise unchanged.
- The skill files contain no workspace-specific or private information.
