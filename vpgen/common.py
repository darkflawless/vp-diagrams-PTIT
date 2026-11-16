"""Phần dùng chung cho mọi bộ sinh sơ đồ: phong cách (đọc từ style.json), id, escape, ghi XML + xuất ảnh."""
import json
import sys
from itertools import count
from pathlib import Path
from xml.sax.saxutils import quoteattr

import hires
import vp

# Console Windows mặc định cp1252 → in tiếng Việt bị UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).parent
STYLE = json.loads((HERE / "style.json").read_text(encoding="utf-8"))

FILL = STYLE["fill"]
FONT = (f'<ElementFont Color="{STYLE["font_color"]}" Name="{STYLE["font_name"]}" '
        f'Size="{STYLE["font_size"]}" Style="0"/>')
LINE = (f'<Line Cap="0" Color="{STYLE["line_color"]}" Transparency="0" '
        f'Weight="{STYLE["line_weight"]}"><Stroke/></Line>')


def fill_xml(color=FILL):
    return f'<FillColor Color="{color}" Style="1" Transparency="0" Type="1"/>'


FILLC = fill_xml()

_ids = count(1)


def new_id() -> str:
    return f"GEN{next(_ids):013d}"


def a(v) -> str:
    """Giá trị thuộc tính XML đã escape, kèm dấu ngoặc kép."""
    return quoteattr(str(v))


def write_and_build(xml_text: str, spec: dict, spec_file, out_dir, image_type=None):
    """Ghi XML cạnh ảnh rồi gọi VP xuất ảnh. image_type: svg | pdf | png | png_with_background | jpg."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    xml = out / (Path(spec_file).stem + ".xml")
    xml.write_text(xml_text, encoding="utf-8")
    kind = image_type or spec.get("image_type") or STYLE.get("image_type", ["svg", "png_with_background"])
    kinds = [kind] if isinstance(kind, str) else list(kind)
    # VP không ghi đè ảnh cũ mà đặt tên '<tên>2.svg' → xoá ảnh cũ cùng tên trước khi xuất
    name = spec.get("name")
    if name:
        # VP thay ký tự cấm trong tên file Windows (\/:*?"<>|) bằng "_"
        name = "".join("_" if c in '\\/:*?"<>|' else c for c in name)
        for ext in (".svg", ".png", ".pdf", ".jpg"):
            (out / (name + ext)).unlink(missing_ok=True)
    before = {p: p.stat().st_mtime for p in out.glob("*.svg")}
    vp.build(xml, out, kind)
    print("XML :", xml)
    print("Ảnh :", out, f"({kind})")
    scales = spec.get("png_scales", STYLE.get("png_scales", []))
    if scales and "svg" in kinds:
        new_svgs = [p for p in out.glob("*.svg") if before.get(p) != p.stat().st_mtime]
        for svg in new_svgs:
            for png in hires.render(svg, scales):
                print("PNG nét cao:", png.name)
    print("VPP :", out / (xml.stem + ".vpp"), "(mở bằng Visual Paradigm để sửa tay)")
