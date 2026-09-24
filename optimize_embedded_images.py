#!/usr/bin/env python3
"""Losslessly preserve dimensions while recompressing legacy embedded article art as WebP.
Future publisher content already uses remote image URLs; this is only for old queued files.
"""
from pathlib import Path
from io import BytesIO
import base64, re
from PIL import Image

ROOT = Path(__file__).parent / 'scheduled_ready'
PAT = re.compile(r'data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)')

def convert(m):
    raw = base64.b64decode(m.group(2))
    if len(raw) < 20_000: return m.group(0)
    im = Image.open(BytesIO(raw))
    out = BytesIO()
    has_alpha = im.mode in ('RGBA','LA') or (im.mode == 'P' and 'transparency' in im.info)
    if not has_alpha and im.mode != 'RGB': im = im.convert('RGB')
    im.save(out, 'WEBP', quality=80, method=6, lossless=has_alpha)
    webp = out.getvalue()
    if len(webp) >= len(raw) * .90: return m.group(0)
    stats[0] += len(raw); stats[1] += len(webp); stats[2] += 1
    return 'data:image/webp;base64,' + base64.b64encode(webp).decode('ascii')

total_before=total_after=images=0
for p in sorted(ROOT.glob('*.html')):
    s=p.read_text(encoding='utf-8'); before=len(s.encode())
    stats=[0,0,0]
    new=PAT.sub(convert,s)
    if new != s:
        p.write_text(new,encoding='utf-8')
        after=len(new.encode()); total_before+=before; total_after+=after; images+=stats[2]
        print(f'{p.name}: {before:,} -> {after:,} bytes; {stats[2]} image(s)')
print(f'TOTAL: {images} images; saved {total_before-total_after:,} HTML bytes')
