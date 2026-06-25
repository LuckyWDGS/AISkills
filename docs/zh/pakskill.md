# pakskill

`pakskill` 用来围绕 UnrealPakTool 打包、检查、安装和清理 Unreal 内容 pak，尤其适合已有项目打包配置的 DLC/Android 流程。

## 什么时候用

- 你要按现有 UnrealPakTool 配置打 `.pak`
- 你要检查打包日志和输出目录
- 你要把 pak 安装到 Android 设备
- 你要清理设备上的 DLC 目录后重新安装

## 重点

- 从配置文件解析项目根目录、工具目录和输出目录
- 安装前检查 ADB 设备数量，避免推错设备
- 安装后用大小和 SHA1 校验本地 pak 与设备 pak 是否一致
