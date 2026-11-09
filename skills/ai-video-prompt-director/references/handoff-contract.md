# 交接合同：读入什么、交回什么

上游简报`pilot_brief`与验收四栏`review`的唯一定义在douyin-ai-creator-lab的`references/production-handoff.md`；本页只定义本Skill的输入检查和输出`prompt_package`。

## 读入

可以来自`pilot_brief`、项目剧本/场次文件，或用户在对话里直接给的节拍。开始编译前确认这几项；缺失时按右列处理，不追问能合理推断的内容：

| 需要 | 缺失时 |
|---|---|
| 本段唯一目标（人物戏：谁对谁做什么、为什么；环境片：观众发现什么） | 回到上游或请用户补一句；不用形容词补 |
| 任务类型：人物戏 / 环境片 / 物件小事件 | 从画面内是否有人和对白推断 |
| 时长 | 用户未指定时按项目偏好（见[项目偏好](project-preferences.md)） |
| 平台 | 按SKILL.md平台路由；最多问一次 |
| 参考文件及状态 | 无参考时用文字空间地图作主锚点 |
| 声音职责与能力 | 能力未核标`post_audio` |
| 执行者与授权 | 未授权就只交提示词 |

## 交回：prompt_package

```yaml
prompt_package:
  brief_id: 对应的pilot_brief或剧本段落
  tier: quick / standard / production
  platform: h3_freetext / h3_full_reference / seedance / neutral
  platform_surface: 界面可见版本或unknown
  generation_mode: multimodal_reference / first_frame / first_last_frame / edit / extend
  reference_plan:                  # 只在代码块外
    dominant_spatial_anchor: 稳定ID或text_space_map
    minimum_reference_set:
      - {id: CHAR-xxx, role: 唯一主要职责, keep: 保留, exclude: 排除}
    conflict_audit: 高冲突组合与处理
  audio_plan: 说话人/旁白归属、听话人、声源、嘴唇状态、native或post_audio
  copy_block: 复制正文（见SKILL.md复制区边界）
  lint: scripts/lint_prompt.py的结果摘要
  fallback_split: 仅在完整版本有明确风险时提供，写成片时间、职责和剪辑端点
  review_focus: 验片时重点看的时段与风险（例如“9–11秒推近是否超程”）
```

快速档只需`platform`、一句假设和`copy_block`；生产档补齐全部字段，并为每个生产单元单独给一份。

## 实片回来以后

执行方按creator-lab的`review`四栏交回。本Skill只处理`unresolved`里属于提示词或参考的部分：先判断层（参考 / 空间 / 动作 / 镜头 / 声音 / 平台语法），一轮只改这一层，保留上一版以便比较。属于剪辑、配音或文件问题的交回creator-lab。
