# Niagara VFX Artist Skill - 快速参考

**版本**: v4.0.0 | **更新**: 2026/04/14

---

## 📁 文件说明

| 文件 | 用途 | 适用场景 |
|------|------|---------|
| **niagara-vfx.md** | 核心 Skill 定义 | AI 调用时的主要知识库 |
| **PLATFORM_OPTIMIZATION.md** | 平台优化指南 | PC/Android 性能优化 |
| **ADVANCED_TECHNIQUES.md** | 高级技术 | Flipbook/HLSL/Flow Maps |
| **EXAMPLES.md** | 示例对话 | 学习如何使用 Skill |
| **README.md** | 完整说明 | 了解 Skill 全貌 |

---

## 🎯 核心能力

### 1. 特效设计（艺术）
- 视觉分析（色彩、运动、层次）
- 审美提升（拟真度、和谐性）
- 情绪传达（力量、优雅、危险）

### 2. 技术实现（工程）
- Niagara 系统配置
- 材质节点和 HLSL
- 性能优化和 LOD

### 3. 平台适配（优化）
- PC: GPU Compute, 高粒子数
- Android: CPU Sim, 低粒子数, 简化材质

### 4. 高级技术（进阶）
- Flipbook 序列帧（性能 10x）
- Flow Maps 流向图（UV 流动）
- 通道打包（采样 4x 优化）
- HLSL Scratch Pad（自定义行为）

---

## 🚀 使用方式

```bash
# 在 Claude Code 中调用
/niagara

# 描述你的想法
我想做一个蓝色的魔法护盾特效，有能量流动的感觉

# 或上传参考图
[上传图片] 帮我分析这个特效如何实现
```

---

## 📊 性能基准

### PC 平台
```
粒子数: 10K - 500K+
GPU 时间: < 5ms
材质指令: < 200
距离剔除: 5000-10000 单位
```

### Android 平台
```
粒子数: 500 - 10K
GPU 时间: < 3ms
材质指令: < 50
距离剔除: < 2000 单位（激进）
```

---

## 🔧 技术速查

### Niagara 模块
- Spawn Rate, Burst, Lifetime
- Gravity, Drag, Curl Noise, Vortex
- Sprite/Mesh/Ribbon Renderer
- Color/Size/Alpha Curves

### 材质混合
- Additive（发光，最快）
- Translucent（烟雾，半透明）
- Masked（硬边缘）

### HLSL 函数
- `length()` - 距离
- `normalize()` - 归一化
- `cross()` - 叉积
- `lerp()` - 插值
- `step()` - 条件（无分支）

---

## 🌐 参考资源

- [Niagara Scalability](https://dev.epicgames.com/documentation/en-us/unreal-engine/scalability-and-best-practices-for-niagara)
- [Mobile Optimization](https://dev.epicgames.com/documentation/en-us/unreal-engine/optimization-and-development-best-practices-for-mobile-projects-in-unreal-engine)
- [Flipbook Baker](https://dev.epicgames.com/documentation/en-us/unreal-engine/niagara-flipbook-baker-quick-start-guide-in-unreal-engine)
- [Complete Optimization Guide](https://morevfxacademy.com/complete-guide-to-niagara-vfx-optimization-in-unreal-engine/)
- [Flow Maps Tutorial](https://80.lv/articles/tutorial-driving-niagara-with-flowmaps-and-baked-fluidsim-data)

---

## ✅ 设计原则

1. **拟真度** - 符合物理规律，光影合理
2. **审美** - 色彩和谐，层次分明
3. **可读性** - 清晰的视觉层次
4. **性能** - LOD 分级，距离剔除

---

**让 AI 成为你的特效艺术顾问！**
