"""Publish the fixed anonymous scores with model names only after review completion."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from datetime import datetime,timezone
import json,hashlib,html,re

ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def esc(s):return html.escape(str(s),quote=True)
def rel(p):return Path(p).relative_to(ROOT).as_posix()
def hsh(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    scores=read(ROOT/'review'/'scores_blind.json')
    assert scores['review_state']=='completed_before_model_reveal'
    mapping=read(ROOT/'model_key.json')
    baseline=read(ROOT/'run_status.json')['cases']
    cases=[]
    for old in baseline:
        case=old['case'];picked=old;recovered=False
        candidate=ROOT/'recovery_20261107'/case/'result.json'
        if not picked['has_readable_image'] and candidate.exists():
            new=read(candidate)
            if new['has_readable_image']:picked=new;recovered=True
        assert case in scores and picked['has_readable_image'],case
        score=scores[case];assert sum(score['scores'])==score['total']
        image=picked['images'][0]
        assert hsh(image['path'])==image['sha256']
        assert picked['prompt_sha256']==hsh(ROOT/'prompts'/f"{case.split('_')[0]}.txt")
        assert picked['requested_model']==mapping[case[-1]]
        if case.startswith('I1'):assert picked['reference_sha256']==hsh(ROOT/'references'/'edit_control_2k.png')
        cases.append(dict(case=case,model=picked['requested_model'],task=case[:2],
                          score=score['total'],breakdown=score['scores'],strengths=score['strengths'],
                          deductions=score['deductions'],image=image['path'],size=image['size'],
                          seconds=picked['duration_seconds'],recovered=recovered,
                          meets_2k=picked['meets_2k'],attempts=picked['result'].get('attempt_count',1),
                          result_path=str((ROOT/'recovery_20261107' if recovered else ROOT/'results')/case/'result.json')))
    models=sorted(mapping.values())
    data=dict(published_at_utc=datetime.now(timezone.utc).isoformat(),
              requested_size=[2560,1440],quality='max',samples=cases,summary=[])
    for model in models:
        t=next(c for c in cases if c['model']==model and c['task']=='T1')
        i=next(c for c in cases if c['model']==model and c['task']=='I1')
        data['summary'].append(dict(model=model,T1=t['score'],I1=i['score'],mean=(t['score']+i['score'])/2,
                                    T1_seconds=t['seconds'],I1_seconds=i['seconds'],meets_2k=t['meets_2k'] and i['meets_2k']))
    (ROOT/'final_results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

    font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',34)
    small=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',26)
    titlefont=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',42)
    for task,label in [('T1','文生图：雨夜车站钟表铺'),('I1','图生图：植物档案室写实转换')]:
        sheet=Image.new('RGB',(2560,1960),'#eeeae1');d=ImageDraw.Draw(sheet)
        d.text((28,20),label,font=titlefont,fill='#163a32')
        d.text((28,80),'四模型同提示词 / quality=max / 请求 2560×1440 / 缩略对照图，原始输出均低于 2K',font=small,fill='#79562a')
        for index,model in enumerate(models):
            item=next(c for c in cases if c['task']==task and c['model']==model)
            x=(index%2)*1280;y=142+(index//2)*900
            d.rounded_rectangle((x+16,y,x+1264,y+876),radius=16,fill='#fffcf6')
            d.text((x+34,y+14),model.replace('gpt-image-','GPT Image '),font=font,fill='#163a32')
            d.text((x+34,y+62),f"{item['score']}/100 · 实际 {item['size'][0]}×{item['size'][1]} · {item['seconds']:.1f}s",font=small,fill='#79562a')
            with Image.open(item['image']) as pic:
                thumb=pic.convert('RGB');thumb.thumbnail((1216,756),Image.Resampling.LANCZOS)
                sheet.paste(thumb,(x+(1280-thumb.width)//2,y+110+(756-thumb.height)//2))
        sheet.save(ROOT/'review'/f'{task}_comparison_labeled.jpg',quality=96)

    md=['# GPT Image 2.5 / 2.6 同条件实测与评分','',
        '8 个条件均已取得可读图片；其中 3 个条件首轮 HTTP 503 后在本次补测成功。所有评分先按 A–D 代号完成，再揭示模型名。',
        '', '**原生 2K 未达标：8/8 张原图都小于请求的 2560×1440。文生图实际为 1536×1024，图生图为 1672×941；没有放大或修图。以下是这些实际返回图片的画质评分，不能当作 2K 能力排名。**','',
        '| 请求模型 | 文生图 /100 | 图生图 /100 | 两项平均 | 文 / 图耗时（秒） | 2K |',
        '|---|---:|---:|---:|---|---|']
    for row in data['summary']:
        md.append(f"| {row['model']} | {row['T1']} | {row['I1']} | {row['mean']:g} | {row['T1_seconds']:.1f} / {row['I1_seconds']:.1f} | 未达标 |")
    md+=['','## 本轮判断','',
         '这组样本中，2.6 Sunburst 文生图 96、图生图 96，综合略高；2.5 Sunburst 为 95/95，差距很小。两版 Flare 都在文生图里增加了背景路人，违反精确四人的约束，所以该项均为 92；其图生图均为 96。',
         '', '若只针对这次复杂场景及受控参考转换，暂选 2.6 Sunburst；已有 2.5 Sunburst 仍然可用，没有看到足以证明代际跃升的差异。图生图基本打平。2.6 Flare 的图生图这次用时 91.9 秒，其余约 43–45 秒；这是单次网关端到端观察，不能推断长期速度。',
         '', '原生 2K 交付这一项，四模型目前均不合格；没有任何型号可凭本轮结果被推荐为已验证的原生 2K 输出方案。','',
         '## 测试条件','',
         '同一网关、同一 Images API 路线、同一提示词文件、size=2560x1440、quality=max、n=1、PNG。文生图测试四人交接怀表、精确物品数量、中文/英文文字、时钟、雨水和玻璃金属材质；图生图使用同一张程序绘制的参考图，测试六瓶布局保持、写实转换及三处指定修改。',
         '', '每个模型每种任务取首张可读结果，没有择优重抽。客户端未提供 seed，不能称为同种子比较。省略 complexity 和 reasoning；不能据此证明网关上游用了相同计算量。请求模型 ID 未替换，但未获得可验证的底层模型身份。',
         '', '评分：文生图按指令关系 40、解剖物理 20、材质细节 20、构图光照 15、洁净度 5；图生图按指定修改 35、参考保持 35、材质几何 20、整体构图光照 10。延迟和尺寸达标情况不计入画质分，单独报告。',
         '', '本次每模型每任务仅一个样本，由同一助手视觉评审。1–4 分差距可能受采样和主观判断影响，不证明型号整体强弱；尤其不能仅因版本号更新断言 2.6 更好。',
         '', '## 对照图','', '![文生图对照](review/T1_comparison_labeled.jpg)','', '![图生图对照](review/I1_comparison_labeled.jpg)',
         '', '## 每张图片的评分依据','']
    for model in models:
        for task in ('T1','I1'):
            c=next(c for c in cases if c['model']==model and c['task']==task)
            md+=[f"### {model} · {'文生图' if task=='T1' else '图生图'} · {c['score']}/100",'',
                 f"分项分数：{' / '.join(map(str,c['breakdown']))}。原图 {c['size'][0]}×{c['size'][1]}，成功请求耗时 {c['seconds']:.2f} 秒。{'使用补测首张；先前 503 记录保留。' if c['recovered'] else '使用首轮首张。'}",'',
                 '完成较好：'+' '.join(c['strengths']),'','扣分依据：'+' '.join(c['deductions']),'',
                 f"![{model} {task}]({rel(c['image'])})",'',f"[原图]({rel(c['image'])}) · [请求与结果记录]({rel(c['result_path'])})",'']
    md+=['## 尺寸与可复现性','',
         'CLI 已将 size 原样放入请求，并对返回字节直接保存；当前证据只能定位为网关或其上游未满足尺寸要求，不能确认是哪一层改变。正式的原生 2K 比较需要先解决这项问题，再按同一协议测试。',
         '', '[尺寸核查](尺寸核查.md) · [预先评分协议](protocol.md) · [逐项 JSON](final_results.json) · [文生图提示词](prompts/T1.txt) · [图生图提示词](prompts/I1.txt)',
         '', '参考图：','', '![统一参考图](references/edit_control_2k.png)',
         '', '[OpenAI 官方图像生成文档](https://developers.openai.com/api/docs/guides/image-generation#size-and-quality-options) 于 2026-11-07 在线核对。实际网关计费未读取，耗时是本机端到端成功请求耗时，不代表纯模型推理时间。','']
    (ROOT/'实测报告.md').write_text('\n'.join(md),encoding='utf-8')

    cards=[]
    for task in ('T1','I1'):
        for model in models:
            c=next(c for c in cases if c['task']==task and c['model']==model)
            caption=f"{model} · {c['score']}/100 · {c['size'][0]}×{c['size'][1]}"
            cards.append(f'''<article class="card" data-task="{task}">
<div class="card-head"><div><span class="eyebrow">{'文生图' if task=='T1' else '图生图'} · {c['case']}</span><h3>{esc(model.replace('gpt-image-',''))}</h3></div><strong>{c['score']}<small>/100</small></strong></div>
<button class="image-button" data-image="{rel(c['image'])}" data-caption="{esc(caption)}" aria-label="打开{esc(caption)}原图"><img src="{rel(c['image'])}" alt="{esc(caption)}" loading="lazy"></button>
<p class="meta">实际 {c['size'][0]}×{c['size'][1]} · {c['seconds']:.1f} 秒 · {'补测首张' if c['recovered'] else '首轮首张'}</p>
<p>{esc(' '.join(c['strengths']))}</p><p class="deduction"><b>扣分：</b>{esc(' '.join(c['deductions']))}</p>
<p class="meta">分项：{' / '.join(map(str,c['breakdown']))}</p><a href="{rel(c['image'])}" target="_blank">打开原图 ↗</a></article>''')
    rows=''.join(f"<tr><td>{esc(r['model'].replace('gpt-image-',''))}</td><td>{r['T1']}</td><td>{r['I1']}</td><td><b>{r['mean']:g}</b></td><td>{r['T1_seconds']:.1f} / {r['I1_seconds']:.1f}</td><td class='fail'>未达标</td></tr>" for r in data['summary'])
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GPT Image 2.5 / 2.6 同条件实测</title>
<style>
:root{font-family:'Segoe UI','Microsoft YaHei',sans-serif;color:#193c33;background:#f2efe8;color-scheme:light}*{box-sizing:border-box}body{margin:0}main{max-width:1500px;margin:auto;padding:42px 28px 70px}header{border-bottom:1px solid #c9c9b9;padding:0 0 28px;margin-bottom:28px}.eyebrow{font-size:12px;letter-spacing:.12em;color:#6c775e}h1{font-size:clamp(28px,4vw,48px);line-height:1.2;margin:14px 0}h2{font-size:25px;margin-top:42px}p{line-height:1.8}.notice{background:#fff0da;border-left:5px solid #a66923;padding:18px 24px;color:#704515;border-radius:7px}.sub{color:#526355;max-width:1100px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;background:#fffcf6;margin:24px 0}td,th{padding:16px;text-align:left;border-bottom:1px solid #e0ddcf;white-space:nowrap}th{font-weight:500;color:#62745c}.fail{color:#9a5226}nav{display:flex;gap:10px;margin:28px 0 20px;flex-wrap:wrap}button{font:inherit;cursor:pointer}nav button{border:1px solid #b7bcaa;background:#fffcf6;color:inherit;padding:10px 22px;border-radius:50px}nav button.active{background:#1f4a3e;color:white;border-color:#1f4a3e}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}.card{background:#fffcf6;border:1px solid #dedccf;border-radius:16px;overflow:hidden;padding:20px}.card-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}h3{margin:5px 0;font-size:25px}.card-head strong{font-size:36px}.card-head small{font-size:15px;color:#6b7d63}.image-button{padding:0;border:0;display:block;width:100%;background:#e9e4d8}.image-button img{display:block;width:100%;aspect-ratio:3/2;object-fit:contain}.meta{font-size:13px;color:#697258;margin:12px 0}.card p{font-size:14px}.deduction{background:#f3f0e7;padding:12px;border-radius:7px}a{color:#236650}details{padding:20px;border:1px solid #d7d5c8;margin-top:20px;background:#fffcf6;border-radius:12px}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;line-height:1.7;color:#344c42;font-size:13px}.reference{max-width:100%;display:block;margin:20px 0}dialog{max-width:95vw;width:fit-content;border:none;padding:16px;background:#f7f4ed;border-radius:12px}dialog::backdrop{background:#071c19ce}dialog img{display:block;max-width:90vw;max-height:80vh;object-fit:contain}dialog button{float:right;padding:6px 16px;border-radius:30px;border:1px solid #a7b3a1;background:white}dialog p{margin:6px 0 16px;padding-right:80px}[hidden]{display:none!important}@media(max-width:760px){main{padding:24px 14px}.grid{grid-template-columns:1fr}.card{padding:14px}td,th{padding:12px}.notice{padding:15px}h1{font-size:32px}}
</style><main><header><span class="eyebrow">2026.11.07 · CM IMAGEGEN · 4 MODELS × 2 TASKS</span><h1>GPT Image 2.5 / 2.6<br>统一条件实测与评分</h1><p class="sub">每个模型一张文生图、一张图生图。相同提示词、相同参考图、quality=max，先按匿名代号评审，再揭示模型名称。点击图片查看原图。</p></header>
<div class="notice"><b>8 张已出图，但原生 2K 全部未达标。</b><br>请求 2560×1440；文生图实际 1536×1024，图生图实际 1672×941。此处评分针对实际返回图片，原图未放大、未修图。</div>
<div class="table-wrap"><table><thead><tr><th>请求模型</th><th>文生图</th><th>图生图</th><th>平均 /100</th><th>文 / 图耗时（秒）</th><th>原生 2K</th></tr></thead><tbody>'''+rows+'''</tbody></table></div>
<p class="sub"><b>本轮暂选 2.6 Sunburst：</b>复杂场景的约束完成度略高；2.5 Sunburst 很接近。两版 Flare 都因额外背景路人扣分；图生图基本打平。没有看到明确的代际跃升，四个型号的原生 2K 交付均未通过。</p>
<p class="sub">单样本视觉评测，1–4 分不构成统计显著差异。模型名称是实际提交的请求 ID；未验证网关最终使用的底层模型。无固定随机种子，耗时不计入画质分。3 项首轮 503 后补测成功，已出图条件没有重做。</p>
<nav aria-label="选择测试类别"><button class="active" data-filter="all" aria-pressed="true">全部 8 张</button><button data-filter="T1" aria-pressed="false">文生图 · 车站钟表铺</button><button data-filter="I1" aria-pressed="false">图生图 · 植物档案室</button></nav><section class="grid">'''+''.join(cards)+'''</section>
<h2>输入与评分标准</h2><p class="sub">文生图：指令关系 40、解剖物理 20、材质细节 20、构图光照 15、洁净度 5。图生图：指定修改 35、参考保持 35、材质几何 20、构图光照 10。每项满分 100，两项各占一半。尺寸单独判定。</p>
<details><summary>统一图生图参考 · 程序绘制，2560×1440</summary><img class="reference" src="references/edit_control_2k.png" alt="统一参考图：两排六瓶的植物档案陈列"></details>'''
    for task,label in [('T1','文生图原始提示词'),('I1','图生图原始提示词')]:
        page+=f'<details><summary>{label}</summary><pre>{esc((ROOT/"prompts"/f"{task}.txt").read_text(encoding="utf-8"))}</pre></details>'
    page+='''<p class="sub"><a href="实测报告.md">完整评分报告</a> · <a href="protocol.md">预先评分协议</a> · <a href="final_results.json">结果 JSON</a> · <a href="尺寸核查.md">2K 尺寸核查</a></p></main>
<dialog id="zoom"><button id="close">关闭</button><p id="caption"></p><img id="zoomImage" alt=""></dialog>
<script>const dialog=document.querySelector('#zoom');document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-filter]').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',x===b?'true':'false')});document.querySelectorAll('.card').forEach(c=>c.hidden=b.dataset.filter!=='all'&&c.dataset.task!==b.dataset.filter)}));document.querySelectorAll('[data-image]').forEach(b=>b.addEventListener('click',()=>{document.querySelector('#zoomImage').src=b.dataset.image;document.querySelector('#zoomImage').alt=b.dataset.caption;document.querySelector('#caption').textContent=b.dataset.caption;dialog.showModal()}));document.querySelector('#close').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});</script></html>'''
    (ROOT/'评测画廊.html').write_text(page,encoding='utf-8')
    print(json.dumps(data['summary'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
