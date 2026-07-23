# Markdown 输出模板

## 字段映射

| 输出字段 | 优先来源 | 缺失处理 |
|---|---|---|
| 作品 ID | `aweme_id` | 该条失败，不写入成功索引 |
| 标题/描述 | `desc` 或等价原文字段 | `待确认` |
| 作者 | `author.nickname` | `待确认` |
| 发布时间 | `create_time` | Markdown 显示为 `YYYY-MM-DD HH:mm`；缺失时写 `待确认` |
| 时长 | `duration` | `—` |
| 类型 | `aweme_type` | 保留原始代码 |
| 点赞/评论/分享/收藏 | `statistics.*` | `—` |
| 话题 | `text_extra[].hashtag_name` | 空 |
| 视频位置 | `poi_info.poi_name` → POI 地址/城市 → `ip_attribution`/`ip_location` | `—`，不推测 |
| 封面 | 视频封面 URL | `—` |
| 分享链接 | `share_url` → `share_info.share_url` → 响应中的等价原始字段 | `待确认`，并记录已检查字段 |
| 站内链接 | 基于 `aweme_id` 的抖音站内作品链接 | 仅链接规则明确且作品类型适用时生成 |
| 视频播放地址 | H264 `bit_rate[].play_addr.url_list` → `video.play_addr.url_list` → H265 `bit_rate[].play_addr.url_list` | `待确认`，并记录已检查字段 |
| 视频原始链 | 其他技能写入的 `original_video_url` | 新同步默认空白；后续同步保留已有值，不用采集到的 `video_url` 覆盖 |
| H264 地址 | 编码信息明确为 H264/AVC 的 `play_addr.url_list` | `待确认` |
| H265 地址 | 编码信息明确为 H265/HEVC 的 `play_addr.url_list` | `待确认` |
| 媒体地址采集时间 | 本次采集时间 | 必填，用于识别带时效签名的 URL |
| 播放量 | API 返回的明确字段 | 未返回时 `—`，不能写 0 |
| 为什么收藏 | 用户人工补充 | `待确认`，AI 不推测 |
| 支持什么决策/输出 | 用户人工补充 | `待确认`，AI 不推测 |

## 文件模板

```markdown
---
title: 抖音收藏列表 - [合集名]
summary: 本地增量同步的抖音收藏合集，共 [N] 条，最近同步于 [时间]。
tags: [抖音收藏, 收件箱]
type: inbox
status: raw
status_label: 原始 / Raw
source: douyin
source_collection: [合集名]
created: YYYY-MM-DD
updated: YYYY-MM-DD
ai_generated: true
---

# 抖音收藏列表 - [合集名]

<!-- AI:START -->
## 同步摘要

| 项目 | 内容 |
|---|---|
| 最近同步 | [时间] |
| 去重键 | `aweme_id` |
| 本地条数 | [N] |
| 本次变更 | 新增 [A] / 更新 [U] / 跳过 [S] / 失败 [F] |

## 收藏列表

| 视频名称 | 视频地址 | 视频原始链 | 视频标签 | 视频发布时间 | 作者 |
|---|---|---|---|---|---|
| ... | https://www.douyin.com/video/... |  | ... | ... | ... |

分享链接、视频播放地址、H264/H265 地址和媒体采集时间不在 Markdown 中另建明细表，完整保存在压缩状态文件中。媒体 URL 必须保留完整查询参数；缺失时在下方“待确认”表记录原因。

## 待确认

| 作品 ID | 问题 | 建议动作 |
|---|---|---|
<!-- AI:END -->
```

写表格前统一清洗单元格：换行变空格、`|` 转义为 `\|`、过长文本合理截断但不得改写原意。标题等展示文本可以截断，但分享链接和视频播放地址不能截断、去查询参数或用省略号代替。完整原文可放到详情区或独立来源文件，并保留追溯链接。
