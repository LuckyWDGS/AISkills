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
