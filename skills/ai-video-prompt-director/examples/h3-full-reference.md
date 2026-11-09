# 样例：MiniMax H3 全参考原生六段稿

同一场“母亲送汤”（见[人物戏15秒](character-drama-15s.md)）编译到H3“全参考/全模态参考”模式。演示：六段英文结构、`<Subject>/<Picture>`只在平台层、`(Sx)`写在发声动词和`<d>`之前、`<d>`内只有语言标签和原台词、三层声音。

## 代码块外：稳定ID → H3临时标签

```text
画面内角色：
- 母亲（CHAR-mother）→ <Subject 1>，身份来自 <Picture 1>，发声者 (S1)
- 林晓（CHAR-linxiao）→ <Subject 2>，身份来自 <Picture 2>，发声者 (S2)
空间锚点 ENV-stairwell-door → <Subject 3>，来自 <Picture 3>
上传顺序：Picture 1/2/3 按上面顺序，由用户在界面操作
```

## 复制正文

<!-- lint platform=h3_full_reference type=character duration=15 expect=pass -->
```text
subject_definitions
<Subject 1>: the mother, a Chinese woman in her mid-fifties with short slightly curled hair, wearing a dark red knitted cardigan and black trousers; identity from <Picture 1>, keep face, hair and clothing only.
<Subject 2>: Lin Xiao, a Chinese woman around 27 with long black hair loosely tied, wearing a light grey hoodie; identity from <Picture 2>, keep face, hair and clothing only.
<Subject 3>: the doorway of an old apartment stairwell from <Picture 3>; keep the door frame, wall tiles and warm ceiling light, exclude any readable signs.

summary
At night in an old stairwell, the mother hands a steel thermos of soup to her daughter Lin Xiao, who complains but finally takes it. Two short Mandarin lines, one planned hard cut to a hand close-up, and a stable final shot.

retention_analysis
From <Picture 1> and <Picture 2> keep only identity and clothing; do not inherit their backgrounds, poses or camera angles. <Picture 3> is the single spatial anchor for the doorway layout. No other people appear or speak.

detailed_description
0.0s–4.0s: Fixed medium shot, side-on at eye level. <Subject 1> stands outside the door on screen left facing right, holding the thermos with both hands at chest height between them. <Subject 2> stands inside the half-open door on screen right, left hand on the door, not reaching out. The mother (S1) looks at her daughter's face and says in a coaxing tone: <d>[Chinese] 你上回说想喝排骨汤，我就炖了点。</d> Lin Xiao keeps her mouth closed and looks down at the thermos.
4.0s–8.0s: Same fixed medium shot. Lin Xiao (S2) lifts her eyes back to her mother, fingers tightening on the door, and says in a low, slightly sharp voice: <d>[Chinese] 我都说了不用跑这一趟，这么远。</d> The mother keeps holding out the thermos; her smile stiffens, then she nods.
8.0s–11.5s: Planned hard cut to a close-up of the hands between them, door frame edge kept on screen right. Lin Xiao's right hand leaves the door and grips the thermos handle; both hands rest on the handle for a moment, then the mother lets go and the thermos stays still in Lin Xiao's hand.
11.5s–13.5s: Planned hard cut back to the opening medium shot, same positions. Lin Xiao holds the thermos in front of her and says nothing; the mother's empty hands drop to her sides and her shoulders relax.
13.5s–15.0s: Stable final frame. Same composition, no camera movement, only natural breathing; no new dialogue, action or people.

overall_soundscape
Quiet stairwell room tone, the soft clink of the thermos handle and faint fabric rustle; the room tone dips slightly under each line and returns afterward.

non_diegetic_music
N/A
```

## 反例

<!-- lint platform=h3_full_reference type=character duration=15 expect=fail:copy_zone,h3_sections,h3_dialogue -->
```text
summary
妈妈送汤给女儿。
detailed_description
0.0s–15.0s: 妈妈说：<d>你上回说想喝排骨汤。</d>（S1）参考@图1。
```

问题：没有从`subject_definitions`开始，缺四个原生段落；`(S1)`写在台词之后；`<d>`内没有`[Chinese]`；临时`@图1`进了正文；六段主体应为英文；15秒只有一句、没有动作链和尾帧。
