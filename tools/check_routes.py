"""Kiểm tra XML đã sinh: đường nối có cắt vào hình hay chạy trùng nhau không.
Dùng: python tools/check_routes.py so_do.xml"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
shapes, conns = {}, []
for diag in root.find("Diagrams"):
    for s in diag.find("Shapes"):
        shapes[s.get("Id")] = (s.get("Name"), float(s.get("X")), float(s.get("Y")),
                               float(s.get("Width")), float(s.get("Height")))
    for c in diag.find("Connectors"):
        pts = [(float(p.get("X")), float(p.get("Y"))) for p in c.find("Points")]
        conns.append((c.get("From"), c.get("To"), pts))


def segs(pts):
    return list(zip(pts, pts[1:]))


def hits_rect(a, b, r):
    _, x, y, w, h = r
    (x1, y1), (x2, y2) = a, b
    if y1 == y2:
        return y < y1 < y + h and min(x1, x2) < x + w and max(x1, x2) > x
    return x < x1 < x + w and min(y1, y2) < y + h and max(y1, y2) > y


bad = 0
for f, t, pts in conns:
    for a, b in segs(pts):
        for sid, r in shapes.items():
            if hits_rect(a, b, r):
                bad += 1
                print("CẮT HÌNH:", shapes[f][0], "->", shapes[t][0], "qua", r[0])
for i in range(len(conns)):
    for j in range(i + 1, len(conns)):
        for a, b in segs(conns[i][2]):
            for c, d in segs(conns[j][2]):
                if a[1] == b[1] == c[1] == d[1]:
                    lo, hi = max(min(a[0], b[0]), min(c[0], d[0])), min(max(a[0], b[0]), max(c[0], d[0]))
                elif a[0] == b[0] == c[0] == d[0]:
                    lo, hi = max(min(a[1], b[1]), min(c[1], d[1])), min(max(a[1], b[1]), max(c[1], d[1]))
                else:
                    continue
                if hi - lo > 0:
                    bad += 1
                    print("TRÙNG NÉT:", shapes[conns[i][0]][0], "->", shapes[conns[i][1]][0], "và",
                          shapes[conns[j][0]][0], "->", shapes[conns[j][1]][0])
print("OK, không lỗi" if not bad else f"{bad} lỗi")
