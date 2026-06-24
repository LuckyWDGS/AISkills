# UE 材质纹理策略、Flipbook、图集与 AI 提示词

## 用途

这份文档现在只作为纹理策略路由入口。按任务读取更窄的 reference，避免为了一个 prompt 或领域规则加载整本手册。

当需要实际出图时，默认加载并使用 `C:/Users/QY/.codex/skills/cm-imagegen/SKILL.md`。本 skill 的 texture references 负责决定纹理策略、prompt 内容、QA 与 UE 接入，cm-imagegen 负责生成与迭代图片。

如果已有设计图、参考图、已批准概念图或上一张选定输出，必须先缓存到本地，再把它作为 reference image 传入 cm-imagegen，用来锁定风格、结构、色彩和材质语言。

默认顺序是效果第一、性能第二。先生成或选择能匹配目标效果的纹理；效果成立后再做降采样、通道打包、压缩格式、LOD、mip、质量开关或低配版本。

---

## 目录

- [纹理选择、Flipbook/Atlas 接入与生成硬规则](texture-strategy-selection-and-rules.md)
- [VFX 纹理 AI 提示词：火焰、余烬、烟雾、闪电](texture-prompts-vfx.md)
- [Foliage / Water 领域纹理策略](texture-domain-foliage-water.md)
- [通用 prompt 框架](texture-prompt-framework.md)
- [生成纹理 QA](generated-texture-qa.md)
- [纹理集 pipeline](texture-set-pipeline.md)

---

## 快速路由

- 不确定该用单张图、Flipbook 还是 atlas：读 `texture-strategy-selection-and-rules.md`。
- 要写火焰、余烬、烟雾、闪电 prompt：读 `texture-prompts-vfx.md`。
- 叶片卡、水材质、参考图优先策略：读 `texture-domain-foliage-water.md`。
- 要验收生成纹理：读 `generated-texture-qa.md` 并跑对应工具。
