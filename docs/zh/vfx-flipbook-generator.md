# vfx-flipbook-generator

`vfx-flipbook-generator` 用来规划、生成、补帧、修复和打包 VFX flipbook atlas，适合烟、尘、火、火星、爆炸、雾、云等 Sprite/SubUV 效果。

## 什么时候用

- 你要做 flipbook、sprite sheet、SubUV atlas 或序列图
- 你只有少量参考帧，需要扩展成完整网格
- 你要把生图帧整理成 power-of-two atlas
- 你要从文字、短视频、静帧或运动参考生成 VFX 帧序列

## 重点

- 先决定帧数、网格、相位、关键锚点和循环/非循环边界
- 生成阶段要分清 anchor approval 和 phase fill
- 打包前要检查透明度、裁切、排序、尺寸和 Niagara 可用性

## 依赖与边界

- 本地处理已有帧图只需 Python 3.10+ 与 Pillow；视频抽帧额外需要 FFmpeg。
- 自动生成新帧需要宿主可用的 `imagegen`，或按技能规则另行配置 `cm-imagegen`；图片生成服务不随本 UE 包附送。
- 导入 UE 后，由 `unreal-engine-mcp` 连接，材质技能处理 SubUV 材质，Niagara 技能验证系统实际绑定。
- 默认使用 2 的幂尺寸，并保证图集尺寸能被行列数整除；不能只缩放整张图而破坏每格 UV 边界。
- 文件检查通过只证明图集静态就绪；播放帧范围、速度、混合方式和最终效果需要 UE 内验证。

```text
$vfx-flipbook-generator 把这些烟雾帧整理成 8×8 的 2048×2048 图集，
检查透明边缘和帧顺序，输出有效帧范围、建议帧率与 Niagara 接入说明。
```

详见 [SKILL.md](../../skills/ue5.8/vfx-flipbook-generator/SKILL.md) 和 [UE 技能总览](ue-skills-overview.md)。
