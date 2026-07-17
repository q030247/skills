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
minute_token: obcnxxxxxxxx
source_url:
source_created_at:
source_updated_at:
note_id:
profile_name: PROFILE
sync_status: synced
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidentiality: 待目标知识库规范确定
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
```

`ai_generated: false` 表示本地文件是来源同步副本，不表示飞书智能总结由人工撰写。若目标知识库把所有机器生成内容统一标为 AI，可按其规范改为 `true`，并在正文注明内容来源为飞书。

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
minute_token: obcnxxxxxxxx
source_url:
source_created_at:
source_updated_at:
note_id:
profile_name: PROFILE
sync_status: synced
created: YYYY-MM-DD
updated: YYYY-MM-DD
confidentiality: 待目标知识库规范确定
ai_generated: false
---

# YYYY-MM-DD 主题 原始逐字稿

> 对应智能纪要：[[YYYY-MM-DD-主题-智能纪要]]

## 原始文字记录

完整写入 lark-cli 返回的 transcript_file 内容，不总结、不修正、不补造。

## 来源

- 飞书妙记：来源 URL（如有）
- 智能纪要：[[YYYY-MM-DD-主题-智能纪要]]
```
