"""Deterministic reference for checking the independent edit endpoint, not a model output."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent
target = root / 'references'
target.mkdir(exist_ok=True)
im = Image.new('RGB', (1024, 1024), '#f2ecdf')
d = ImageDraw.Draw(im)
font = r'C:\Windows\Fonts\msyh.ttc'
def text(pos, value, size, fill='#183c36', anchor=None):
    d.text(pos, value, font=ImageFont.truetype(font, size), fill=fill, anchor=anchor)
d.rectangle((30, 30, 994, 994), outline='#183c36', width=4)
text((512, 75), '山间来信', 60, anchor='mt')
text((512, 154), 'BOTANICAL ARCHIVE / 026', 25, anchor='mt')
colors = ['#b46f3e', '#419278', '#c6a340', '#8474a3', '#4e86b2', '#b96b71']
for i, (x,y) in enumerate([(220,350),(512,350),(804,350),(220,690),(512,690),(804,690)]):
    d.ellipse((x-90,y+205,x+95,y+230),fill='#d4ccbc')
    d.rounded_rectangle((x-70,y,x+70,y+212),radius=25,fill=colors[i],outline='#183c36',width=3)
    d.rounded_rectangle((x-48,y-54,x+48,y+20),radius=10,fill='#183c36')
    d.rectangle((x-59,y+55,x+59,y+163),fill='#fff7df',outline='#d4c690',width=2)
    text((x,y+66), '山间来信', 21, anchor='mt')
    text((x,y+101), f'{i+1:02d}', 28,anchor='mt')
    text((x,y+139), '330 mL', 14,anchor='mt')
    d.ellipse((x+25,y+178,x+50,y+202),fill='#edcc79')
    for j in range(3):
        d.ellipse((x-60+j*46,y+238,x-35+j*46,y+253),fill='#668451')
d.line((80,619,944,619),fill='#bba47b',width=6)
text((512,950),'桂花乌龙 · 低温萃取 · 2026.11.04',22,anchor='mt')
im.save(target / 'edit_control.png')
print(target / 'edit_control.png')
