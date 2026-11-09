# 视频提示词导演

[执行入口](../../skills/ai-video-prompt-director/SKILL.md) · [技能目录](README.md)

将已确定的剧本节拍、环境片节拍或 `douyin-ai-creator-lab` 交来的 `pilot_brief` 编译成可复制的视频提示词，核对角色、空间、连续动作、对白/旁白归属、参考职责、切点和稳定尾帧。按明确选择读取 H3 或 Seedance 适配；已选 Muse 而底层模型未知时写平台无关中文稿。

- 输出分快速 / 标准 / 生产三档，按请求自动选择。
- `scripts/lint_prompt.py` 自动检查复制区污染、平台语法混用、时间码覆盖、尾帧、角色开头和 H3 对白格式；`examples/` 有人物戏、环境片、H3 原生稿和单层修订的金标与反例。
- 剧本、素材和项目偏好（默认时长、字数、切点、配乐母题）继续由内容项目保存，Skill 内只保留可覆盖的默认值。

例：`$ai-video-prompt-director 按当前导演包整理 Seedance 提示词，保持角色与空间连续性。`

本技能整理提示词，不提交生成任务，也不会重新启用已暂停的视频生成自动化；实际生成、剪辑、配音和验片记录交 `douyin-ai-creator-lab`。
