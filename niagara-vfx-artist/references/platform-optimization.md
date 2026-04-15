# Niagara VFX 平台优化指南

**版本**: v1.0.0  
**更新日期**: 2026/04/14

---

## 📋 目录

1. [PC 平台实现路径](#pc-平台实现路径)
2. [Android 平台实现路径](#android-平台实现路径)
3. [性能预算和基准](#性能预算和基准)
4. [跨平台优化策略](#跨平台优化策略)
5. [Scalability 设置](#scalability-设置)

---

## PC 平台实现路径

### 硬件能力
- **GPU**: 支持 DirectX 11/12, Vulkan
- **粒子预算**: 50,000 - 500,000+ 粒子（取决于 GPU）
- **GPU Compute**: 完全支持
- **材质复杂度**: 高（支持复杂 shader）

### 推荐配置

#### 1. GPU 粒子系统（高性能）
```
Emitter Properties:
├── Sim Target: GPUCompute Sim
├── Max Particles: 100,000+
├── Fixed Bounds: 启用（避免每帧计算边界）
└── Scalability Mode: Self
```

#### 2. 材质设置
```
Material Properties:
├── Shading Model: Unlit（粒子特效）
├── Blend Mode: Additive / Translucent
├── Two Sided: 根据需要
└── Instruction Count: < 200（理想）
```

#### 3. LOD 和剔除
```
Distance Culling:
├── Max Distance: 5000 - 10000 单位
├── LOD Distance 0: 0 - 2000（全质量）
├── LOD Distance 1: 2000 - 5000（中等质量）
└── LOD Distance 2: 5000+（低质量）
```

#### 4. 性能监控命令
```
控制台命令:
fx.Niagara.Debug.DrawSystemBounds 1    # 显示系统边界
fx.Niagara.ShowAllocationWarnings 1    # 显示分配警告
stat Niagara                            # Niagara 性能统计
stat GPU                                # GPU 性能统计
r.Niagara.GpuComputeDebug 1            # GPU Compute 调试
```

### PC 平台最佳实践

✅ **推荐做法**:
- 使用 GPU Compute Sim 处理大量粒子
- 启用 Fixed Bounds 避免动态计算
- 使用 Distance Culling 剔除远处特效
- 材质使用 Unlit + Additive 混合
- 启用 Scalability 自动降级

⚠️ **避免**:
- 过多的 CPU 粒子系统（< 10,000 粒子用 CPU）
- 材质指令数 > 300
- 禁用 Distance Culling
- 过多的 Emitter（每个系统 < 5 个）

---

## Android 平台实现路径

### 硬件限制
- **GPU**: Mali, Adreno, PowerVR（能力差异大）
- **粒子预算**: 1,000 - 10,000 粒子（取决于设备）
- **GPU Compute**: ⚠️ 部分支持（需要 Vulkan）
- **材质复杂度**: 低（移动 shader 限制）

### 关键要求

#### 1. 渲染 API
```
Android 平台要求:
├── Vulkan: 支持 GPU Compute（Android 7.0+）
├── OpenGL ES 3.1+: 基础支持
└── 推荐: Vulkan（更好的性能）
```

#### 2. CPU 粒子系统（推荐）
```
Emitter Properties:
├── Sim Target: CPUSim（移动端更稳定）
├── Max Particles: 1,000 - 5,000
├── Fixed Bounds: 必须启用
└── Scalability Mode: Self
```

#### 3. 材质优化（关键）
```
Material Properties:
├── Shading Model: Unlit（必须）
├── Blend Mode: Additive（最快）
├── Texture Size: 512x512 或更小
├── Instruction Count: < 50（严格限制）
└── Avoid: 
    ├── 复杂的 HLSL
    ├── 多层纹理采样
    └── 动态分支
```

#### 4. 移动端特效设计原则
```
设计限制:
├── 粒子数量: 尽可能少（< 2000）
├── 纹理: 单张，低分辨率
├── 透明度: 减少 Overdraw
├── 更新频率: 降低（30fps 可接受）
└── 剔除距离: 激进（< 2000 单位）
```

#### 5. GPU Compute 在移动端
```
⚠️ 注意事项:
├── 需要 Vulkan 支持
├── 并非所有设备支持
├── 性能不稳定
└── 推荐: 使用 CPU Sim + 低粒子数
```

### Android 平台最佳实践

✅ **推荐做法**:
- 使用 CPU Sim（更稳定）
- 粒子数 < 2000
- 材质指令数 < 50
- 纹理 512x512 或更小
- 激进的距离剔除（< 2000 单位）
- 使用 Additive 混合（最快）
- 禁用不必要的模块

❌ **严格避免**:
- GPU Compute Sim（除非确认设备支持）
- 复杂材质（HLSL, 多纹理）
- 大量透明粒子（Overdraw 杀手）
- 动态光照
- Ribbon 渲染器（性能差）

---

## 性能预算和基准

### PC 平台性能预算

| 质量级别 | 粒子数 | Emitter 数 | 材质指令 | GPU 时间 |
|---------|--------|-----------|---------|---------|
| 低 | 10,000 | 2-3 | < 100 | < 1ms |
| 中 | 50,000 | 3-5 | < 150 | < 2ms |
| 高 | 100,000+ | 5-8 | < 200 | < 5ms |
| 极致 | 500,000+ | 8+ | < 300 | < 10ms |

### Android 平台性能预算

| 设备级别 | 粒子数 | Emitter 数 | 材质指令 | GPU 时间 |
|---------|--------|-----------|---------|---------|
| 低端 | 500 | 1-2 | < 30 | < 1ms |
| 中端 | 2,000 | 2-3 | < 50 | < 2ms |
| 高端 | 5,000 | 3-4 | < 80 | < 3ms |
| 旗舰 | 10,000 | 4-5 | < 100 | < 5ms |

### 性能测试基准

#### PC 测试场景
```
测试配置:
├── 同时播放特效数: 10-20 个
├── 屏幕分辨率: 1920x1080
├── 目标帧率: 60 FPS
└── GPU 预算: 总计 < 5ms
```

#### Android 测试场景
```
测试配置:
├── 同时播放特效数: 3-5 个
├── 屏幕分辨率: 1080x2400
├── 目标帧率: 30-60 FPS
└── GPU 预算: 总计 < 3ms
```

---

## 跨平台优化策略

### 1. Scalability 系统（自动降级）

#### 配置 Scalability 模式
```
Niagara System Settings:
├── Scalability Mode: Self
├── Effect Type: 
│   ├── Gameplay（重要特效）
│   ├── Cosmetic（装饰特效）
│   └── Debug（调试特效）
└── Override System Scalability Settings: 启用
```

#### 平台特定设置
```python
# PC 配置
PC_Settings = {
    "Low": {"SpawnCountScale": 0.5, "MaxDistance": 3000},
    "Medium": {"SpawnCountScale": 0.75, "MaxDistance": 5000},
    "High": {"SpawnCountScale": 1.0, "MaxDistance": 8000},
    "Epic": {"SpawnCountScale": 1.5, "MaxDistance": 10000}
}

# Android 配置
Mobile_Settings = {
    "Low": {"SpawnCountScale": 0.25, "MaxDistance": 1000},
    "Medium": {"SpawnCountScale": 0.5, "MaxDistance": 1500},
    "High": {"SpawnCountScale": 0.75, "MaxDistance": 2000}
}
```

### 2. LOD 距离设置

#### PC LOD 配置
```
LOD Distance Settings:
├── LOD 0 (Full): 0 - 2000 单位
│   ├── Spawn Rate: 100%
│   ├── 所有模块启用
│   └── 全分辨率纹理
├── LOD 1 (Medium): 2000 - 5000 单位
│   ├── Spawn Rate: 50%
│   ├── 禁用次要模块
│   └── 中等纹理
└── LOD 2 (Low): 5000 - 8000 单位
    ├── Spawn Rate: 25%
    ├── 仅核心模块
    └── 低分辨率纹理
```

#### Android LOD 配置（更激进）
```
LOD Distance Settings:
├── LOD 0 (Full): 0 - 1000 单位
│   ├── Spawn Rate: 100%
│   ├── 核心模块
│   └── 优化纹理
└── LOD 1 (Low): 1000 - 2000 单位
    ├── Spawn Rate: 30%
    ├── 最小模块
    └── 低分辨率纹理
```

### 3. 材质优化策略

#### 跨平台材质设计
```
通用优化:
├── 使用 Material Quality Switch 节点
├── 移动端: 简化版本
├── PC: 完整版本
└── 共享纹理资源
```

#### 示例：跨平台材质
```hlsl
// PC 版本（复杂）
float3 PC_Effect = ComplexNoise + Fresnel + MultiTexture;

// Mobile 版本（简化）
float3 Mobile_Effect = SimpleTexture * VertexColor;

// 使用 Quality Switch
FinalColor = (IsMobile) ? Mobile_Effect : PC_Effect;
```

### 4. 粒子池和对象复用

#### 粒子系统池化
```cpp
// 推荐做法
UNiagaraComponent* GetPooledEffect(FName EffectName)
{
    // 从池中获取
    if (EffectPool.Contains(EffectName))
        return EffectPool[EffectName]->GetAvailable();
    
    // 创建新的
    return CreateNewEffect(EffectName);
}
```

---

## Scalability 设置详解

### 系统级 Scalability

#### 在 Niagara System 中配置
```
System Properties → Scalability:
├── Effect Type: Gameplay / Cosmetic
├── Scalability Mode: Self
├── Override System Scalability: 启用
└── Platform Scalability Overrides:
    ├── Windows: High
    ├── Android: Low
    └── iOS: Low
```

### Emitter 级 Scalability

#### 每个 Emitter 独立配置
```
Emitter Properties → Scalability:
├── Spawn Count Scale: 平台倍数
├── System Scalability Settings:
│   ├── Low: 0.25x
│   ├── Medium: 0.5x
│   ├── High: 1.0x
│   └── Epic: 1.5x
└── Distance Culling:
    ├── Enable: 启用
    ├── Max Distance: 平台特定
    └── Cull Reaction: Deactivate Immediate
```

### 控制台命令

#### 运行时调整
```
// 设置 Scalability 级别
fx.Niagara.QualityLevel 0  # Low
fx.Niagara.QualityLevel 1  # Medium
fx.Niagara.QualityLevel 2  # High
fx.Niagara.QualityLevel 3  # Epic

// 全局粒子预算
fx.Niagara.MaxGPUParticlesSpawnPerFrame 10000
fx.Niagara.MaxCPUParticlesPerSystem 5000

// 距离剔除
fx.Niagara.MaxSystemProxies 128
```

---

## 实战优化检查清单

### PC 平台检查清单

✅ **性能优化**:
- [ ] 使用 GPU Compute Sim（粒子数 > 10,000）
- [ ] 启用 Fixed Bounds
- [ ] 配置 Distance Culling（5000-10000 单位）
- [ ] 材质指令数 < 200
- [ ] 设置 LOD 距离（0/2000/5000）
- [ ] 使用 Scalability 系统

✅ **质量保证**:
- [ ] 测试不同质量级别
- [ ] 验证 LOD 切换平滑
- [ ] 检查 GPU 时间 < 5ms
- [ ] 确认无内存泄漏

### Android 平台检查清单

✅ **性能优化**:
- [ ] 使用 CPU Sim（更稳定）
- [ ] 粒子数 < 2000
- [ ] 材质指令数 < 50
- [ ] 纹理 512x512 或更小
- [ ] 激进距离剔除（< 2000 单位）
- [ ] 使用 Additive 混合
- [ ] 禁用不必要模块

✅ **兼容性测试**:
- [ ] 测试 Vulkan 支持
- [ ] 测试低端设备（Mali GPU）
- [ ] 测试中端设备（Adreno GPU）
- [ ] 验证帧率 > 30 FPS
- [ ] 检查发热和电池消耗

---

## 参考资源

### 官方文档
- [Scalability and Best Practices for Niagara](https://dev.epicgames.com/documentation/en-us/unreal-engine/scalability-and-best-practices-for-niagara)
- [Mobile Optimization Best Practices](https://dev.epicgames.com/documentation/en-us/unreal-engine/optimization-and-development-best-practices-for-mobile-projects-in-unreal-engine)
- [Rendering Features for Mobile Games](https://dev.epicgames.com/documentation/en-us/unreal-engine/rendering-features-for-mobile-games-in-unreal-engine)

### 社区资源
- [Complete Guide to Niagara VFX Optimization](https://morevfxacademy.com/complete-guide-to-niagara-vfx-optimization-in-unreal-engine/)
- [UE5 Niagara Performance Tips](https://toxigon.com/ue5-niagara-performance-tips)
- [LOD Scalability Tutorial](https://cghow.com/lod-scalability-in-ue5-niagara-tutorial/)

---

**版本**: v1.0.0  
**最后更新**: 2026/04/14

