# playwright

`playwright` 用来通过终端驱动真实浏览器，适合网页导航、点击、表单输入、截图、快照和数据抽取。

## 什么时候用

- 你要自动操作网页或本地 Web 应用
- 你要通过 snapshot 找元素，再稳定点击或输入
- 你要复现 UI 流程、抓取页面状态或导出截图
- 你只需要 CLI 自动化，不需要写完整测试工程

## 重点

- 先确认 `npx` 可用
- 优先使用 skill 自带的 Playwright CLI wrapper
- 每次页面跳转或 DOM 大变化后重新 snapshot
