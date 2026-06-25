# playwright-interactive

`playwright-interactive` 用来在持久的 Playwright 会话里调试 Web 或 Electron 应用，适合需要反复刷新、点击、截图和视觉 QA 的前端任务。

## 什么时候用

- 你要调试本地 dev server、网页游戏或 Electron 窗口
- 你要保留同一个浏览器上下文，快速迭代 UI
- 你要做功能 QA、视觉 QA、响应式检查或截图证据
- 你需要反复执行小段浏览器脚本而不想每次重启

## 重点

- 先列 QA 覆盖清单，再测试
- 复用同一个 Playwright handle
- 功能验证和视觉验证分开做，最后保留关键证据
