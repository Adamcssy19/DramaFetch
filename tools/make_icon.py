"""把用户提供的 logo 处理成可用的应用图标。

流程：
1. 擦除右下角水印（该区域在卡片之外，用周边背景色填充）
2. 把卡片以外的白色背景变为透明（从四边向内做连通填充，避免掏空卡片内部）
3. 按透明区域裁切，输出多尺寸 PNG 与 Windows 用的 ICO
"""

from pathlib import Path

from PIL import Image, ImageDraw

SRC = Path(r'C:\Users\Administrator\.workbuddy\clipboard-images\clipboard-2026-09-26T07-04-59-908Z-6b391da6.jpg')
OUT = Path(r'C:\Users\Administrator\WorkBuddy\2026-09-26-14-46-17\tools\out')
OUT.mkdir(parents=True, exist_ok=True)

# 水印位置（前面扫描得到的包围盒，外扩若干像素）
WATERMARK = (1570, 1800, 1890, 1900)

im = Image.open(SRC).convert('RGB')
w, h = im.size

# ---- 1. 擦除水印 ----
# 取水印正上方的背景色作为填充色
bg = im.crop((WATERMARK[0], WATERMARK[1] - 60, WATERMARK[2], WATERMARK[1] - 10))
colors = bg.getdata()
avg = tuple(sum(c[i] for c in colors) // len(colors) for i in range(3))
draw = ImageDraw.Draw(im)
draw.rectangle(WATERMARK, fill=avg)
print('水印已擦除，填充色', avg)

# ---- 2. 透明背景 ----
rgba = im.convert('RGBA')

gray = rgba.convert('L')
# 二值化：明显偏暗的算作卡片本体（描边约 204~235），浅灰阴影与光晕（245 以上）算作背景。
# 卡片内部虽然是白色，但被描边围住，从四边填充进不去，所以不会被掏空。
binary = gray.point(lambda v: 0 if v >= 240 else 255, mode='L')

# 从四边向内填充，标记与边缘连通的背景
for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
    if binary.getpixel(seed) == 0:
        ImageDraw.floodfill(binary, seed, 128, thresh=0)

# 硬边透明。缩放时由重采样自动做抗锯齿，不做模糊，避免卡片外留下一圈半透明光晕
alpha = binary.point(lambda v: 0 if v == 128 else 255, mode='L')
rgba.putalpha(alpha)

# ---- 3. 裁切到内容边界 ----
bbox = alpha.getbbox()
print('内容边界', bbox, '原图尺寸', rgba.size)
content = rgba.crop(bbox)

# 补成正方形（居中），四周留一点边距，避免图标贴边
cw, ch = content.size
side = max(cw, ch)
canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
canvas.paste(content, ((side - cw) // 2, (side - ch) // 2), content)

master = canvas.resize((1024, 1024), Image.LANCZOS)
master.save(OUT / 'logo_1024.png')
master.resize((256, 256), Image.LANCZOS).save(OUT / 'logo_256.png')
master.resize((256, 256), Image.LANCZOS).save(OUT / 'preview_256.png')

# ---- 4. 生成 ICO ----
master.save(
    OUT / 'app.ico',
    format='ICO',
    sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print('输出目录', OUT)
for f in sorted(OUT.iterdir()):
    print(' ', f.name, f.stat().st_size, '字节')
