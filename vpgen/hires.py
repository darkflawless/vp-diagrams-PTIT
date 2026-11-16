"""Dựng PNG nét cao (2x/3x/4x...) từ file SVG mà VP đã xuất, bằng Edge/Chrome chạy headless.

VP CE chỉ xuất PNG ở 1x (rất mờ khi dán vào báo cáo). SVG là vector nên render lại ở
device-scale-factor cao là ra PNG sắc nét. Lưu ý: dòng logo VP dùng font 'Dialog' (font Java),
trình duyệt thay bằng font khác nên chữ logo hơi khác bản gốc — logo vẫn còn nguyên.
Cấu hình trong style.json: "png_scales": [3, 4]  (bỏ trống / [] = không dựng).
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _browser():
    for b in BROWSERS:
        if Path(b).exists():
            return b
    return shutil.which("msedge") or shutil.which("chrome") or shutil.which("chromium")


def _size(svg_text: str):
    i = svg_text.index("<svg")
    tag = svg_text[i:svg_text.index(">", i)]
    w = re.search(r'\swidth="([\d.]+)', tag).group(1)
    h = re.search(r'\sheight="([\d.]+)', tag).group(1)
    return round(float(w)), round(float(h))


def render(svg: Path, scales) -> list[Path]:
    """Trả về danh sách PNG đã tạo: '<tên> (3x).png', '<tên> (4x).png', ..."""
    browser = _browser()
    if not browser:
        print("Bỏ qua PNG nét cao: không tìm thấy Edge/Chrome.")
        return []
    svg = Path(svg).resolve()
    w, h = _size(svg.read_text(encoding="utf-8"))
    made = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copy(svg, tmp / "d.svg")
        (tmp / "d.html").write_text(
            '<html><body style="margin:0;background:#fff">'
            f'<img src="d.svg" width="{w}" height="{h}" style="display:block"></body></html>',
            encoding="utf-8")
        for s in scales:
            out = svg.with_name(f"{svg.stem} ({s}x).png")
            r = subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            f"--force-device-scale-factor={s}", f"--window-size={w},{h}",
                            f"--screenshot={out}", (tmp / "d.html").as_uri()],
                           capture_output=True, timeout=120)
            if out.exists():
                made.append(out)
            else:
                print(f"Không dựng được {out.name}:", (r.stderr or r.stdout or b"")[-300:])
    return made
