# POR-COSPLAY-001 · 首批造型示例

这些是类型下的两个示例，不是类型定义或默认穿搭。A 对应 LOOK-001，B 对应 LOOK-002；只在选中对应造型时加载。以下历史提示词中的黑色服装、窗边方向和固定人物参数只适用于本批示例，不能自动带入新造型。

## 逐图审查

两图均为 383×680 竖图。共同为室内暗背景、画面左侧亮光、发丝与身体轮廓的暖色侧逆光、面部柔和补光、浅景深。画面有真实人像摄影的皮肤与发丝细节，同时带精致 Cosplay 妆发风格。不能仅由画面确认真实年龄、身份、地点或摄影参数；生成明确设为 26 岁虚构成年女性。

| 参考逻辑 ID | 服装、配饰与妆发 | 姿势、构图与光线 | 使用角色 |
| --- | --- | --- | --- |
| cos-ref-01 | 浅金/铂金发底，头顶蓝绿挑染，粉色长马尾，齐碎刘海，带字发夹；粉紫眼妆。黑色挂脖服装，颈前金属环与胸前褶皱相连，侧腰花纹蕾丝，髋侧镂空系带。低腰深蓝牛仔短裤、毛边、侧边粉色挂件及毛绒小球；大腿边有细带金属扣，画面不足以确认其完整结构 | 站立侧身略回转，两臂举过头顶整理马尾；头顶/手部被上缘部分裁切，取景至大腿；背景深灰黑，左上方暖光勾勒肩臂与粉色发尾 | A 服装/发色/轮廓、姿态、光线；不复制身份或发夹文字 |
| cos-ref-02 | 酒红棕长发与齐刘海，成对毛绒猫耳，浅蓝虹膜效果；黑细肩带裙，银灰色胸片、黑色上缘与正中心银色心形装饰，黑色颈圈；细项链有青绿色小点坠饰和下垂金属饰件 | 坐姿或低位前倾，上身靠前、肩部放松，两臂向下在身前收拢；近正面、略歪头、看镜头，手被下缘裁切；左侧窗状亮区，暖色发丝逆光与脸部柔光，背景虚化 | B 服装/配饰/表情、构图、光线；坐具不明，不虚构已观察到家具 |

## 风格继承与新面容

继承黑色贴身服装、蕾丝/缎面/牛仔的材质反差、自然女性曲线与参考领口，A 的多色发束或 B 的酒红猫耳造型，以及暖光与暗背景的反差。A 与 B 是互斥造型：不要默认把猫耳、彩色马尾、银灰胸片和挂脖金属环混在同一件衣服上。

面容设计保留用户偏爱的清秀柔和写真审美，设为虚构成年中国女性；中国女性是创作设定，不是对原图身份的判断。新人物用柔和椭圆脸、略圆的下巴、自然弧眉、清澈杏眼、小巧鼻形和自然薄至中等唇形。通过不同的脸长/脸颊比例、眉弧、眼尾角度和唇峰组合形成新人物；不要为了“换脸”机械加宽下颌、加深眼窝、扩大鼻尖或加厚嘴唇。虹膜颜色属于可调 Cosplay 美瞳效果。不要照搬旧军装配方的面部结构参数。

## 正向提示词 · 共用基础

将下面共用基础与 A 或 B 造型段、一个姿势段合并成完整实际提示词，保存到项目 `prompts/`。每个请求只生成一个画面。

<!-- COMMON_START -->
Create exactly one high-quality photorealistic indoor fashion cosplay portrait of an original fictional 26-year-old adult Chinese woman. Use the supplied reference for costume design, hair styling, lighting and photographic mood, while creating a new individual face. Delicate harmonious adult beauty: a softly oval face, gently rounded chin, natural softly arched eyebrows, clear expressive almond eyes, a small refined nose, softly defined natural pink lips of moderate thickness, luminous skin with fine realistic texture and subtle makeup. Preserve the reference's delicate facial aesthetic without exaggerated jaw width, deep eye sockets or heavy contouring. Design individual differences in cheek proportions, eyebrow arc, eye-corner angle and lip contour. An attractive natural feminine silhouette, confident relaxed adult fashion presence.
Dim charcoal-toned indoor studio, a large window to camera-left providing warm directional side and rim light through the hair, gentle reflected fill on the face, natural soft shadows, delicate warm highlights against a dark blurred background. Realistic fine hair strands, skin and fabric, restrained elegant color grading, shallow depth of field with crisp eyes and readable clothing construction. A photographic portrait, not an illustration. Frame the chosen pose cleanly, preserving required hands and accessories. One continuous 1024x1536 portrait photo, no collage, no watermark or lettering. Generate only one final image, no alternate candidates.
<!-- COMMON_END -->

## A · 彩发蕾丝与牛仔

<!-- A_START -->
Hairstyle: platinum-blonde base with narrow teal-green and muted blue accent strands through the crown and fringe, a long flowing pastel-pink high ponytail, airy straight bangs and fine face-framing strands. A small plain dark hair clip, subtle mauve eye makeup. Outfit: an opaque black gathered halter bodysuit with a small metal ring at the front neckline, floral lace panels only at the side waist, slim tied straps at the side hips, low-rise dark-blue frayed denim shorts, and a small pink charm with an ivory fluffy pompom at the belt loop. Natural fitted silhouette and neckline consistent with the fashion reference; bust and central torso fabric opaque. The halter straps, metal ring, side lace and denim waistband are distinct, coherently constructed layers. No cat ears or silver chest panel in this variation.
<!-- A_END -->

姿势 A1：双臂举过头顶，一手轻握马尾，另一手在后脑整理头发；身体轻微侧转，头回向镜头，头顶与手完整入框，取景至大腿中部。A2 可替换为站立三分之二侧面、一手捋发、一手轻搭裤侧。不要把无法看清的腿部细带擅自扩展成复杂配饰。

## B · 酒红猫耳与心形黑裙

<!-- B_START -->
Hairstyle: long dark burgundy-auburn hair with straight airy bangs, loose strands around the cheeks and a matched pair of plush dark-burgundy cat-ear costume accessories. Soft muted blue cosmetic contact-lens effect. Outfit: a black thin-strap fitted dress with an opaque silver-grey satin bust inset, black top edging and one small silver heart ornament centered on the neckline. A slender black choker and a fine layered necklace with a tiny turquoise-colored charm and a small dangling silver pendant. The dress fabric and bust inset are opaque. Preserve the attractive natural neckline and fitted adult fashion silhouette. The heart ornament belongs to the dress, clearly separate from the necklace. No rainbow ponytail, halter ring or denim shorts in this variation.
<!-- B_END -->

姿势 B1：坐于简洁凳上、身体微微前倾、膝盖并拢、双手松弛交叠在膝上，略歪头看镜头。凳子是新图布景选择，不宣称参考中已见。B2：站在窗旁、身体轻微侧转，一手拨耳边头发，另一手松垂腰侧，看镜头，头到大腿构图。B2 与 B1 保持服装结构与发色，表情可轻微变化。


## 首批执行记录摘要

B1/B2 完成并目视检查；A1 首版服装偏离，修正请求未返回图像。详细证据保存在私人项目。这些结果不代表新造型的能力限制。
