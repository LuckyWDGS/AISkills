# portrait-recipe-studio

可扩展的人像与服装提示词配方库，提供参考审查、面容设计和按配方生成图片的工作流。

见[技能入口](../../skills/portrait-recipe-studio/SKILL.md)和[配方索引](../../skills/portrait-recipe-studio/references/index.md)。

- 仅在用户点名本技能或明确要求使用这套提示词库时调用，保留 `allow_implicit_invocation: false`。
- 普通生图仍使用对应的生图技能；这套配方库不作为默认入口。
- 按本次主题加载所需配方；只有用户要求收录时才保存新增配方。

开始示例：

```text
$portrait-recipe-studio 根据这张参考选择合适的人像服装配方，先整理提示词。
```
