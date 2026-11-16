"""Chạy công cụ dòng lệnh của Visual Paradigm: import XML -> .vpp -> xuất ảnh.

Đường dẫn VP lấy từ biến môi trường VP_HOME, mặc định bản CE 18.1.
"""
import os
import subprocess
import sys
from pathlib import Path

VP_HOME = Path(os.environ.get("VP_HOME", r"C:\Program Files\Visual Paradigm CE 18.1"))


def _classpath() -> str:
    jars = [".", r"..\lib\vpplatform.jar", r"..\lib\jniwrap.jar", r"..\lib\winpack.jar",
            r"..\ormlib\orm.jar", r"..\ormlib\orm-core.jar"]
    jars += [rf"..\lib\lib{i:02d}.jar" for i in range(1, 21)]
    return ";".join(jars)


def _run(main_class: str, *args: str) -> str:
    java = VP_HOME / "jre" / "bin" / "java.exe"
    if not java.exists():
        raise RuntimeError(f"Không thấy Visual Paradigm ở {VP_HOME}. Đặt biến môi trường VP_HOME.")
    cmd = [str(java), "-Xmx1024m", "-Djava.awt.headless=true", "-cp", _classpath(), main_class, *args]
    # Ghép tay dòng lệnh: "*" phải giữ nguyên dấu ngoặc kép, nếu không Java tự bung wildcard
    line = " ".join('"*"' if x == "*" else subprocess.list2cmdline([x]) for x in cmd)
    p = subprocess.run(line, cwd=VP_HOME / "bin", capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = p.stdout + p.stderr
    if p.returncode != 0:
        raise RuntimeError(f"{main_class} lỗi:\n{out}")
    return out


def build(xml_file, out_dir, image_types="png_with_background") -> Path:
    """Import XML vào project mới rồi xuất mọi sơ đồ theo từng định dạng trong image_types
    (một chuỗi hoặc danh sách: svg, pdf, png, png_with_background, jpg)."""
    if isinstance(image_types, str):
        image_types = [image_types]
    xml_file, out_dir = Path(xml_file).resolve(), Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    vpp = out_dir / (xml_file.stem + ".vpp")
    for old in [vpp, *out_dir.glob(vpp.name + ".bak*")]:
        old.unlink(missing_ok=True)
    _run("com.vp.cmd.ImportXML", "-project", str(vpp), "-file", str(xml_file))
    for t in image_types:
        _run("com.vp.cmd.ExportDiagramImage", "-project", str(vpp), "-out", str(out_dir),
             "-diagram", "*", "-type", t)
        if not any(out_dir.glob("*." + t.split("_")[0])):
            raise RuntimeError(f"VP không xuất ra ảnh {t} nào — có thể XML không hợp lệ.")
    for bak in out_dir.glob(vpp.name + ".bak*"):
        bak.unlink(missing_ok=True)
    return out_dir


if __name__ == "__main__":
    print(build(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:] or ["png_with_background"]))
