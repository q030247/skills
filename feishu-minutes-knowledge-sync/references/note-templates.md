# 飞书妙记配对笔记模板

目标知识库规范优先于此模板。文件名双链不带 `.md`。

## 智能纪要

```markdown
---
title: YYYY-MM-DD 主题 智能纪要
summary: 飞书妙记生成的智能纪要，包含总结、章节、关键词和待办，需结合原始逐字稿复核。
tags: [飞书妙记, 会议纪要]
type: meeting
status: raw
source: feishu-minutes
source_id: obcnxxxxxxxx
source_group_id: obcnxxxxxxxx
content_role: summary
minute_token: obcnxxxxxxxx
source_url:
source_created_at:
source_updated_at:
note_id:
profile_name: PROFILE
sync_status: synced
capture_types: []
ai_processing_status: unprocessed
article_extraction_status: not_applicable
created: YYYY-MM-DD
updated: YYYY-MM-DD
ai_generated: false
---

# YYYY-MM-DD 主题 智能纪要

> 对应原始记录：[[YYYY-MM-DD-主题-原始逐字稿]]

## 飞书智能总结

保留飞书返回的 summary。

## 章节

保留飞书返回的 chapters。

## 待办

保留飞书返回的 todos；不得猜测负责人或截止日期。

## 关键词

保留飞书返回的 keywords。

## 来源

- 飞书妙记：来源 URL（如有）
- 原始逐字稿：[[YYYY-MM-DD-主题-原始逐字稿]]

<!-- AI:START -->
## AI处理区

- 内容分类：待处理
- 建议归属：待确认
- 衍生结果：待处理
<!-- AI:END -->
```

`ai_generated: false` 表示本地文件是来源同步副本，不表示飞书智能总结由人工撰写。若目标知识库把所有机器生成内容统一标为 AI，可按其规范改为 `true`，并在正文注明内容来源为飞书。`capture_types` 与 AI 受控区由每日处理维护；后续同步不得覆盖其已更新内容。

## 原始逐字稿

```markdown
---
title: YYYY-MM-DD 主题 原始逐字稿
summary: 飞书妙记的原始文字记录，结论待确认。
tags: [飞书妙记, 原始记录, 逐字稿]
type: transcript
status: raw
source: feishu-minutes
source_id: obcnxxxxxxxx
source_group_id: obcnxxxxxxxx
content_role: transcript
minute_token: obcnxxxxxxxx
source_url:
source_created_at:
source_updated_at:
note_id:
profile_name: PROFILE
sync_status: synced
transcript_review_status: pending_review
transcript_text_source:
corrected_transcript:
created: YYYY-MM-DD
updated: YYYY-MM-DD
ai_generated: false
---

# YYYY-MM-DD 主题 原始逐字稿

> 对应智能纪要：[[YYYY-MM-DD-主题-智能纪要]]

## 原始文字记录

完整写入 lark-cli 返回的 transcript_file 内容，不总结、不修正、不补造。

> [!warning] 人工校订闸门
> 原始文字记录永久保留。检查无误后，将`transcript_review_status`改为`ready_for_extraction`并把`transcript_text_source`设为`original`；需要修正时另建人工校订稿，设为`corrected`并填写`corrected_transcript`链接。人工放行前不得进行后续提取。

## 来源

- 飞书妙记：来源 URL（如有）
- 智能纪要：[[YYYY-MM-DD-主题-智能纪要]]
```
