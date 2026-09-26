"""生成图标预览，检查边缘是否干净、在深浅背景下是否正常。"""

import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent / 'out'
logo = Image.open(OUT / 'logo_1024.png').convert('RGBA')
SIZE = 1024


def on(color):
    background = Image.new('RGBA', (SIZE, SIZE), color)
    return Image.alpha_composite(background, logo).convert('RGB')


# 棋盘格
board = Image.new('RGBA', (SIZE, SIZE), (255, 255, 255, 255))
tile = 64
for y in range(0, SIZE, tile):
    for x in range(0, SIZE, tile):
        if (x // tile + y // tile) % 2:
            board.paste((200, 200, 200, 255), (x, y, x + tile, y + tile))
chess = Image.alpha_composite(board, logo).convert('RGB')

dark = on((32, 32, 32, 255))
light = on((243, 243, 243, 255))

sheet = Image.new('RGB', (SIZE * 3 + 80, SIZE), (120, 120, 120))
sheet.paste(chess, (0, 0))
sheet.paste(dark, (SIZE + 40, 0))
sheet.paste(light, (SIZE * 2 + 80, 0))

# 小尺寸检验
small = Image.new('RGB', (SIZE, SIZE), (120, 120, 120))
for i, size in enumerate((16, 32, 48, 64, 128, 256)):
    icon = logo.resize((size, size), Image.LANCZOS)
    background = Image.new('RGBA', (size, size), (243, 243, 243, 255))
    flat = Image.alpha_composite(background, icon).convert('RGB')
    small.paste(flat, (60 + i * 160, 400))

sheet.paste(small, (0, 0)) if False else None
sheet = sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS)
sheet.save(OUT / 'preview_sheet.png')
small.resize((SIZE // 2, SIZE // 2), Image.LANCZOS).save(OUT / 'preview_small.png')
print('预览已生成')
