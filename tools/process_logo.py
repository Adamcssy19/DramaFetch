"""处理用户提供的透明底图标，生成应用图标与 Windows 用的 ICO。

源图已经是透明底，但照片抠图会在边缘留下白色毛边与零星噪点，这里做清理：
1. 移除卡片以外、不透明度很低的孤立噪点
2. 裁切到内容边界并补成正方形
3. 输出多尺寸 ICO 与各尺寸 PNG
"""

from pathlib import Path

from PIL import Image

SRC = Path(r'C:\Adam\000 收集箱 & 处理中\remove.photos-removed-background.png')
PROJECT = Path(r'C:\Users\Administrator\WorkBuddy\2026-09-26-14-46-17\guoapp-src\DramaFetch')
OUT = PROJECT / 'tools' / 'out'
OUT.mkdir(parents=True, exist_ok=True)

im = Image.open(SRC).convert('RGBA')
w, h = im.size
print('源图尺寸', w, h)

# 统计不透明度的分布，确认噪点强度
alpha = im.getchannel('A')
hist = alpha.histogram()
total = w * h
for low, high in ((1, 40), (41, 100), (101, 200), (201, 254), (255, 256)):
    count = sum(hist[low:high])
    print(f'  不透明度 {low}-{high - 1}: {count} 像素（{count / total * 100:.3f}%）')

# 清理：把很淡的像素直接变全透明（去掉抠图残留的白边），其余保持
cleaned = im.copy()
cleaned.putalpha(alpha.point(lambda v: 0 if v < 60 else v))

# 再裁掉一圈很淡的边缘过渡：对 alpha 做一次轻微收缩
from PIL import ImageFilter

alpha2 = cleaned.getchannel('A')
shrunk = alpha2.filter(ImageFilter.MinFilter(3))
cleaned.putalpha(shrunk)

bbox = cleaned.getchannel('A').getbbox()
print('有效内容边界', bbox)

content = cleaned.crop(bbox)
cw, ch = content.size
side = max(cw, ch)
# 留 2% 内边距，避免图标贴边
pad = round(side * 0.02)
canvas = Image.new('RGBA', (side + pad * 2, side + pad * 2), (0, 0, 0, 0))
canvas.paste(content, ((side - cw) // 2 + pad, (side - ch) // 2 + pad), content)
print('内容尺寸', content.size, '→ 补边后', canvas.size)

master = canvas.resize((1024, 1024), Image.LANCZOS)
master.save(OUT / 'logo_1024.png')
master.resize((256, 256), Image.LANCZOS).save(OUT / 'logo_256.png')

master.save(
    OUT / 'app.ico',
    format='ICO',
    sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print('输出目录', OUT)
for f in sorted(OUT.iterdir()):
    if f.is_file():
        print(' ', f.name, f.stat().st_size, '字节')
