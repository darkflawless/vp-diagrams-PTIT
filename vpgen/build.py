"""Lệnh chung: đọc file mô tả JSON, chọn bộ sinh theo trường "type", xuất ảnh bằng Visual Paradigm.

Cách dùng:
    python build.py so_do.json [thu_muc_ra] [svg] [png_with_background] [pdf]
    python build.py thu_muc_chua_json/ [thu_muc_ra]      # build tất cả file .json trong thư mục

Thêm loại sơ đồ mới: viết module có hàm generate(spec) -> str (XML), rồi thêm 1 dòng vào GENERATORS.
"""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import write_and_build  # noqa: E402

GENERATORS = {
    "usecase": "usecase",
    "class": "classdiag",
    "sequence": "seqdiag",
    "erd": "erd",
    # "activity": "activity",  # <- thêm loại mới ở đây
}


def guess_type(spec):
    if "type" in spec:
        return spec["type"]
    if "lifelines" in spec:
        return "sequence"
    if "classes" in spec:
        return "class"
    if "usecases" in spec:
        return "usecase"
    if "tables" in spec:
        return "erd"
    raise SystemExit('Không đoán được loại sơ đồ — thêm "type": "usecase" | "class" | "sequence" | "erd".')


def build_one(spec_file, out_dir, image_types):
    spec = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    kind = guess_type(spec)
    if kind not in GENERATORS:
        raise SystemExit(f'Chưa hỗ trợ loại "{kind}". Có: {", ".join(GENERATORS)}')
    mod = importlib.import_module(GENERATORS[kind])
    print(f"[{kind}] {spec_file}")
    write_and_build(mod.generate(spec), spec, spec_file, out_dir, image_types or None)


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    src = Path(argv[0])
    out_dir = argv[1] if len(argv) > 1 else "out"
    image_types = argv[2:]
    files = sorted(src.glob("*.json")) if src.is_dir() else [src]
    for f in files:
        build_one(f, out_dir, image_types)


if __name__ == "__main__":
    main(sys.argv[1:])
