---
name: audit-inbox-health
description: Audit the weekly health of an Obsidian or Markdown knowledge-base inbox using source indexes, processing reports, and narrowly scoped source metadata. Use when the user asks for an inbox health check, weekly source-ingestion audit, stale-input report, duplicate source-ID or URL check, paired-source integrity check, synchronization failure review, or analysis of whether inbox growth is producing downstream project, knowledge, content, or archive outcomes. Read source types, paths, age thresholds, pairing rules, and report location from the invocation prompt or workspace instructions. Generate a read-only report; never sync, rewrite, move, archive, or delete source content.
---

# Audit Inbox Health

Assess whether captured inputs are arriving, remaining traceable, being processed, and producing useful downstream outcomes. Keep workspace-specific paths, source names, pairing rules, and thresholds in the invocation prompt or local instructions.

## Resolve configuration

Read the invocation prompt and workspace instructions to resolve:

- knowledge-base root and governing schema;
- inbox root and per-source indexes;
- source types and their stable identifiers;
- paired or grouped source rules;
- processing-status fields and display-label conventions;
- weekly time window and stale-age threshold;
- synchronization and processing report locations;
- downstream project, resource, content, log, or archive indicators;
- excluded paths and report output path.

Use explicit configuration over inference. If an index schema is unclear, inspect its header and a small representative sample before continuing. Do not encode discovered private values into the skill.

## Read progressively

Use this order:

1. Read local instructions, schema, inbox description, and report-writing rules.
2. Read each configured source index for stable ID, source URL, local path, timestamps, source state, processing state, and last successful sync window.
3. Read weekly synchronization, triage, processing, audit, and closure reports.
4. Inspect frontmatter, summary, or controlled processing regions only for records needed to verify a finding.
5. Read source bodies only when a specific integrity question cannot be resolved from metadata.

Do not scan the full archive or the full body of every inbox record.

## Audit dimensions

### Weekly intake

- Count new and updated records by source for the configured week.
- Distinguish source records from files; grouped inputs count according to the configured source-unit rule.
- Separate successful additions, updates, skips, failures, missing records, deletion markers, and moved records.

### Staleness and processing

- Identify records older than the configured threshold with no valid processing record.
- Distinguish raw, processing, waiting, blocked, completed, moved, and deleted states using machine values.
- Do not classify an item as processed solely because it was synchronized.

### Identity and integrity

- Detect repeated stable source IDs and normalized source URLs.
- Report index rows pointing to missing local files.
- Apply configured group or pair checks and report missing members, inconsistent IDs, divergent local paths, or invalid review states.
- Treat semantic similarity as a lead, not proof of duplication.

### Operational failures

- Summarize failed syncs, expired authentication, unavailable tools, partial runs, and stalled success windows.
- Do not retry failed sources as part of this skill.
- Report when a failed source was incorrectly advanced to a successful watermark.

### Flow-through health

- Compare weekly inbox growth with verified downstream processing records and outputs.
- Report whether processed input produced project material, reusable knowledge, content material, logs, approved closure candidates, or another configured outcome.
- Do not infer value from folder location alone.
- Mark missing evidence as unknown rather than declaring that an input has no value.

## Generate the report

Follow the configured schema and output path. Include:

```markdown
# Weekly Inbox Health

## Scope and data quality
## Intake by source
## Stale or unprocessed inputs
## Duplicate identities and links
## Group or pair integrity
## Synchronization and authentication failures
## Processing and downstream flow
## Risks and recommended follow-ups
## Sources used
```

For every anomaly, include the source type, stable ID when available, canonical index or file link, observed evidence, and recommended human or downstream-system check.

## Boundaries

- Generate a report only.
- Do not synchronize external sources.
- Do not rewrite original records or source indexes.
- Do not create formal tasks unless the invocation explicitly starts a separate approved task-creation workflow.
- Do not move, archive, delete, or close inbox records.
- Do not approve closure candidates.
- Do not expose credentials, tokens, cookies, or sensitive source content in the report.

## Preserve idempotency

- Repeated runs for the same week use the configured stable report path.
- Counts use stable source units and the same time-window boundary.
- Existing human-maintained report sections are preserved according to workspace rules.
- A zero-result category is reported as zero, not omitted.

## Verify

- Counts reconcile with the indexes and reports actually read.
- Grouped inputs are not double-counted.
- Stale means synchronized but not validly processed under the configured threshold.
- Duplicate findings distinguish exact identity collisions from possible semantic similarity.
- Missing files, pairing errors, failures, and stalled watermarks are traceable.
- No source, index, status, approval, or file location was changed.
- The skill files contain no workspace-specific or private information.
