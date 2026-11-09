from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math, random

ROOT=Path(__file__).resolve().parent
random.seed(26)
im=Image.new('RGB',(2560,1440),'#e9e1cf')
d=ImageDraw.Draw(im)
FONT=r'C:\Windows\Fonts\msyh.ttc'
def txt(x,y,s,n=30,c='#243c35',anchor='mm'):
    d.text((x,y),s,font=ImageFont.truetype(FONT,n),fill=c,anchor=anchor)
def line(xy,fill='#5f6551',w=3): d.line(xy,fill=fill,width=w)
def plant(cx,base,spread,leaves=14):
    d.ellipse((cx-70,base-15,cx+70,base+20),fill='#b6a78b')
    d.polygon([(cx-55,base-120),(cx+55,base-120),(cx+40,base),(cx-40,base)],fill='#96724d',outline='#564e36')
    for k in range(leaves):
        ang=-2.9+k/(leaves-1)*2.65
        ex=cx+math.cos(ang)*spread
        ey=base-125+math.sin(ang)*spread*1.4
        line([(cx,base-110),(ex,ey)],'#54714b',4)
        for j in range(2,9):
            t=j/10; px=cx+(ex-cx)*t; py=base-110+(ey-(base-110))*t
            for side in (-1,1):
                tip=(px+side*24*(1-t*.45),py-25)
                d.polygon([(px,py),tip,(px+side*13,py-34)],fill='#647c51',outline='#456143')

d.rounded_rectangle((38,38,2522,1400),radius=18,outline='#30483d',width=7)
for y in range(220,1230,46): line([(80,y),(2480,y)],'#d4cbb8',1)
txt(1280,107,'山间来信',72)
txt(1280,183,'BOTANICAL ARCHIVE / 026',28)
d.rounded_rectangle((485,260,2075,1170),radius=14,fill='#c8b28a',outline='#624b30',width=8)
for x in range(505,2065,47): line([(x,280),(x,1150)],'#b9a079',2)
for y in (722,1142):
    d.rectangle((460,y,2100,y+33),fill='#80613e',outline='#55412c',width=3)
    line([(466,y+7),(2095,y+7)],'#b79461',3)

colors=['#b46f3e','#419278','#c6a340','#8474a3','#4e86b2','#b96b71']
for i,(x,base) in enumerate([(760,716),(1280,716),(1800,716),(760,1136),(1280,1136),(1800,1136)]):
    top=base-285
    d.ellipse((x-125,base-9,x+130,base+10),fill='#a38e6b')
    d.rounded_rectangle((x-108,top,x+108,base-5),radius=34,fill=colors[i],outline='#34493e',width=4)
    d.rounded_rectangle((x-67,top-65,x+67,top+28),radius=12,fill=colors[i],outline='#34493e',width=3)
    d.rounded_rectangle((x-76,top-82,x+76,top-40),radius=7,fill='#2f403a',outline='#24352e',width=3)
    for xx in range(x-67,x+68,12): line([(xx,top-76),(xx,top-46)],'#6c7464',2)
    d.rounded_rectangle((x-91,top+57,x+91,top+218),radius=4,fill='#fff4d5',outline='#a2956e',width=2)
    txt(x,top+89,'山间来信',28)
    txt(x,top+139,f'{i+1:02d}',48)
    txt(x,top+190,'330 mL',24)
    line([(x-84,top+25),(x-84,top+45)],'#e4d8b3',6)
    line([(x-84,top+229),(x-84,base-30)],'#e4d8b3',6)

# Peripheral anchors are part of the reference, not generation instructions.
line([(92,300),(188,300),(215,340)],'#665238',7)
d.ellipse((160,325,310,475),fill='#e3b95b',outline='#564d35',width=8)
d.ellipse((180,345,290,455),fill='#f8e6a9',outline='#9b834c',width=3)
plant(235,1150,150,13)
plant(390,1160,95,11)
d.rectangle((2200,310,2425,600),fill='#eee7cf',outline='#6a573b',width=10)
line([(2310,564),(2310,350)],'#577046',4)
for j in range(6):
    yy=385+j*28
    d.ellipse((2260,yy-20,2310,yy+4),fill='#73855b')
    d.ellipse((2310,yy-8,2360,yy+16),fill='#73855b')
for i,w in enumerate((270,250,285,260,240)):
    yy=1120-i*48
    d.rounded_rectangle((2160,yy,2160+w,yy+42),radius=5,fill=['#6a735d','#8a654a','#b6a67c','#61777c','#8e7f70'][i],outline='#514635',width=3)
    for xx in (2183,2195): line([(xx,yy+5),(xx,yy+36)],'#d5c6a7',3)
    line([(2220,yy+15),(2310,yy+15)],'#c7b78f',2)
line([(2300,916),(2300,700)],'#9d7a32',11)
line([(2180,748),(2420,730)],'#9d7a32',8)
for xx,yy in ((2180,748),(2420,730)):
    line([(xx,yy),(xx-43,yy+115),(xx+43,yy+115),(xx,yy)],'#8e794b',3)
    d.pieslice((xx-50,yy+95,xx+50,yy+135),0,180,fill='#af9554',outline='#5b553c',width=3)
d.rectangle((2255,900,2345,920),fill='#ac8a47',outline='#655436',width=3)

d.rectangle((80,1215,2480,1370),fill='#9f7a4c',outline='#5d4b34',width=6)
for y in (1240,1280,1320,1355):
    line([(95,y),(2465,y+3)],'#b68c58',3)
d.polygon([(280,1263),(420,1240),(575,1260),(580,1337),(425,1320),(285,1345)],fill='#eee6d2',outline='#655c49')
line([(420,1241),(425,1320)],'#b1a58d',3)
for j in range(5): line([(303,1278+j*9),(393,1264+j*9)],'#979581',2)
line([(485,1315),(480,1270)],'#6f7950',2)
for yy in (1280,1295):
    d.ellipse((461,yy,480,yy+8),fill='#8b9270');d.ellipse((480,yy+5,500,yy+13),fill='#8b9270')
d.ellipse((1960,1250,2040,1330),outline='#baa66c',width=9)
d.ellipse((1972,1262,2028,1318),fill='#c4cfbe',outline='#73674a',width=2)
line([(2025,1315),(2095,1350)],'#5d5038',16)
target=ROOT/'references'/'edit_control_2k.png'
target.parent.mkdir(exist_ok=True)
im.save(target)
print(str(target))
