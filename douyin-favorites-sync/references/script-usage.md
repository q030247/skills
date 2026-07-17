# 脚本使用说明

## 1. 浏览器采集脚本

读取 `scripts/douyin_capture.js` 的完整文本，通过浏览器工具的初始化脚本能力注册，然后再进入或刷新收藏页。不同平台的工具名可能不同，但必须保证脚本先于页面业务请求执行。

进入收藏页后，在页面上下文依次调用：

```javascript
window.__douyinFavoritesCapture.status()
window.__douyinFavoritesCapture.collectBootstrap()
await window.__douyinFavoritesCapture.scroll()
window.__douyinFavoritesCapture.status()
```

确认首个响应已捕获后，导出对象：

```javascript
window.__douyinFavoritesCapture.exportData({
  displayed_total: 401,
  collection: "合集名称",
  page_complete: true
})
```

需要由浏览器直接下载时：

```javascript
window.__douyinFavoritesCapture.download("douyin-favorites.json", {
  displayed_total: 401,
  collection: "合集名称",
  page_complete: true
})
```

不要把 Cookie、请求头或 localStorage 传给导出函数。

## 2. Python 处理脚本

Python 脚本只使用标准库。以技能目录为基准调用：

```sh
python3 scripts/process_favorites.py capture-1.json capture-2.json \
  --output "<抖音目标目录>/<收藏列表>.md" \
  --index "<抖音目标目录>/<同步索引>.md" \
  --report "<AI报告目录>/<执行报告>.md" \
  --collection "<合集名称>" \
  --displayed-total 401 \
  --page-complete
```

路径和文件名必须来自目标知识库规则，不要直接复制示例占位符。输入可以是浏览器脚本导出的完整 JSON，也可以是多个单批响应 JSON。

### 参数

| 参数 | 含义 |
|---|---|
| `inputs` | 一个或多个采集 JSON，脚本会递归查找 `aweme_list` |
| `--output` | 收藏列表 Markdown 文件 |
| `--index` | 带机器 JSON 区的 Markdown 同步索引 |
| `--report` | 本次执行报告 |
| `--collection` | 收藏合集名称 |
| `--displayed-total` | 页面显示的收藏总数，用于完整性对账 |
| `--page-complete` | 已确认滚动分页结束；没有证据时不要传 |
| `--restore-missing` | 明确恢复本地已标记缺失的记录；只有用户授权时使用 |

## 3. 输出与保护机制

- 收藏列表只更新 `<!-- AI:START -->` 与 `<!-- AI:END -->` 区域。
- 索引只更新 `<!-- DOUYIN_SYNC_INDEX:START -->` 与 `<!-- DOUYIN_SYNC_INDEX:END -->` 区域。
- 既有文件没有对应标记时脚本停止，避免覆盖人工内容。
- 文件先写临时文件，再原子替换目标。
- 指纹忽略采集时间和人工填写字段，避免每次运行把全部记录误判为更新。
- 增量合并保留已经人工填写的“为什么收藏”和“支持什么决策/输出”。
- 只有页面总数、合并唯一数一致且确认分页结束时，才更新全量成功时间。
