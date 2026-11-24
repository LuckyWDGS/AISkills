# unreal-sequencer

`unreal-sequencer` 负责 UE 关卡序列、摄像机、镜头切换与演出，依赖同级的
`unreal-engine-mcp` 共享客户端。工具能力以目标编辑器实时发现的 schema 为准。

## 什么时候用

- 做过场动画、开场/结尾镜头、镜头巡游、游戏内演出
- 摄像机推拉摇移、镜头切换、焦距/对焦/光圈动画、淡入淡出
- 给关卡里的 Actor 打位移关键帧或挂骨骼动画
- 审查或修复已有序列：镜头空档、重叠、没绑摄像机、空轨道、关键帧超范围

## 操作与验证

先给出镜头目的、时长、节拍、主体、构图和触发方式；已有任务授权时直接推进。
后台制作优先使用显式传入序列的官方 MCP 操作，不自动打开 Sequencer。

部分现有辅助脚本仍依赖打开的时间线或捕获窗口，因此默认拒绝相应操作。
`--allow-editor-ui` 只用于用户明确要求的界面流程，不能为了绕过失败自行添加。
离线计划校验和后台结构检查可以独立使用：

```powershell
python scripts/sequence_plan_apply.py plan.json
python scripts/sequence_inspect.py /Game/Cinematics/LS_Name --project <完整项目路径> --out <报告目录> --strict
```

结构检查、时间点求值、动态画面、PIE 运行和正式渲染是不同验收。
游戏内演出还要检查结束、停止、跳过和中止后的相机、输入及状态恢复。
使用 `--save` 的辅助脚本只在明确选择保存时保存；直接编辑时记录目标包的实际保存状态。

## 版本相关注意事项

- 已审计的普通 Sequencer/Keyframing 工具按显示帧率计帧；Control Rig、子序列、导入导出和渲染接口分别核对单位。
- Actor 进入序列前，保留其变换通道默认值，避免未打关键帧的通道归零或缩放变为 1。
- 已审计的 UE 5.8.4 `set_camera_cut_binding` 存在写入前错误。当前 `Editor.bind_camera_cuts` 使用官方 MCP 的 `get_binding_id` 和 `ObjectTools` 完整写入、回读 `cameraBindingId`，无需 Remote Python。
- 后台 Spawnable 兼容路径中的公开 API 有弃用提示，仅允许已审计的 `5.8.4-58902052+++UE5+Release-5.8` 构建；升级后先复查官方接口，不能直接放宽版本限制。
- `sequence_render.py` 是旧版预览捕获辅助脚本，不等于 Movie Render Queue / Movie Render Graph 正式出片。

## 调用示例

```text
$unreal-sequencer 把这段演出整理成 20 秒：花间引入、跟随行走、停步近景、越肩拉远。
后台操作，保留原序列，检查相机遮挡、步幅与位移、动作过渡和结束后的状态恢复。
```

具体方法见 [SKILL.md](../../skills/ue5.8/unreal-sequencer/SKILL.md)；组合与安装见
[UE 技能总览](ue-skills-overview.md)。
