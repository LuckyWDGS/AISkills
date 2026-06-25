# unreal-bridge

`unreal-bridge` 用来通过 TCP bridge 在正在运行的 Unreal Engine 5.3+ 编辑器里执行 Python，适合查询场景、操作资产和自动化编辑器流程。

## 什么时候用

- 你要让 Codex 直接操作已打开的 UE 编辑器
- 你要执行 UE Python 脚本、查询资产、改关卡或批处理内容
- 你要检查 bridge 是否连接、编辑器是否 ready
- 你要在 UE 内部做自动化，而不是只改磁盘文件

## 重点

- 先确认插件已安装并启用
- `ping ready=true` 才代表可以执行脚本
- 多编辑器或网络阻断时要显式指定项目或 endpoint
