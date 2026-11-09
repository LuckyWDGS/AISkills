"""Create anonymous review views; never resample or overwrite scored originals."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'review';OUT.mkdir(exist_ok=True)
font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',32)
small=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',24)
manifest=[]
for task in ('T1','I1'):
    sheet=Image.new('RGB',(2560,1600),'#f1f0eb')
    draw=ImageDraw.Draw(sheet)
    for index,code in enumerate('ABCD'):
        case=f'{task}_{code}';f=ROOT/'results'/case/'result.json'
        x=(index%2)*1280;y=(index//2)*800
        draw.text((x+20,y+12),case,font=font,fill='#182824')
        if not f.exists():continue
        data=json.loads(f.read_text(encoding='utf-8'))
        recovered=ROOT/'recovery_20261107'/case/'result.json'
        if not data.get('has_readable_image') and recovered.exists():
            candidate=json.loads(recovered.read_text(encoding='utf-8'))
            if candidate.get('has_readable_image'):data=candidate
        readable=[i for i in data['images'] if i['readable']]
        if not readable:
            draw.text((x+20,y+120),'No readable image',font=font,fill='#984129');continue
        path=Path(readable[0]['path'])
        with Image.open(path) as original:
            pic=original.convert('RGB')
            thumb=pic.copy();thumb.thumbnail((1240,700),Image.Resampling.LANCZOS)
            sheet.paste(thumb,(x+(1280-thumb.width)//2,y+64))
            thumb.save(OUT/f'{case}_preview.jpg',quality=94)
            w,h=pic.size
            boxes={'UL':(0,0,w//2,h//2),'UR':(w//2,0,w,h//2),
                   'LL':(0,h//2,w//2,h),'LR':(w//2,h//2,w,h),
                   'CENTER':(w//4,h//4,3*w//4,3*h//4)}
            for label,box in boxes.items():pic.crop(box).save(OUT/f'{case}_{label}_native.png')
            manifest.append(dict(case=case,path=str(path),size=[w,h],seconds=data['duration_seconds']))
    sheet.save(OUT/f'{task}_comparison_blind.jpg',quality=96)
(OUT/'blind_image_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
