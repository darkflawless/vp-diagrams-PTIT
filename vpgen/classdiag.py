"""Sinh XML Class Diagram cho Visual Paradigm từ file mô tả JSON, tự tính bố cục.

Cách dùng:  python vpgen/classdiag.py examples/gio_hang.json out/

Mô tả class:
  {"name": "Cart", "attributes": ["-id : Integer"], "operations": ["+total(from : Date) : Float"],
   "abstract": false, "stereotype": "interface", "pos": [cột, hàng]}   # pos là tuỳ chọn
Quan hệ (type): association | aggregation | composition | inheritance | realization | dependency
  aggregation/composition: "from" là bên TỔNG THỂ (có hình thoi), "to" là bên thành phần
  inheritance/realization: "from" là lớp con, "to" là lớp cha / interface
  "from_mult", "to_mult": bội số hai đầu, ví dụ "1", "0..*", "1..*"
"""
import json
import re
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FONT, LINE, FILLC, FILL, a, new_id, write_and_build  # noqa: E402
from router import route_all  # noqa: E402

CHAR_W = 6.3
ROW_H = 15
HEAD_H = 18
MIN_W = 120
GAP_X, GAP_Y = 120, 90      # vẫn đủ 3-5 làn cho router (mỗi hình nới 20px)
MARGIN = 40
VIS = {"+": "public", "-": "private", "#": "protected", "~": "package"}


def parse_member(s):
    """'-name : Type' hoặc '+op(a : T, b) : R' -> dict."""
    s = s.strip()
    vis = VIS.get(s[:1], None)
    if vis:
        s = s[1:].strip()
    m = re.match(r"^(\w+)\s*\((.*)\)\s*(?::\s*(.+))?$", s)
    if m:
        params = []
        for p in filter(None, (x.strip() for x in m.group(2).split(","))):
            pn, _, pt = p.partition(":")
            params.append((pn.strip(), pt.strip()))
        return {"kind": "op", "vis": vis or "public", "name": m.group(1), "params": params,
                "type": (m.group(3) or "").strip()}
    name, _, typ = s.partition(":")
    return {"kind": "attr", "vis": vis or "private", "name": name.strip(), "type": typ.strip()}


def member_text(m):
    sym = {v: k for k, v in VIS.items()}[m["vis"]]
    if m["kind"] == "attr":
        return f'{sym}{m["name"]}' + (f' : {m["type"]}' if m["type"] else "")
    ps = ", ".join(n + (f" : {t}" if t else "") for n, t in m["params"])
    return f'{sym}{m["name"]}({ps})' + (f' : {m["type"]}' if m["type"] else "")


class Cls:
    def __init__(self, d):
        self.name = d["name"]
        self.abstract = d.get("abstract", False)
        self.stereotype = d.get("stereotype")
        self.attrs = [parse_member(x) for x in d.get("attributes", [])]
        self.ops = [parse_member(x) for x in d.get("operations", [])]
        self.pos = d.get("pos")
        self.model_id, self.shape_id = new_id(), new_id()
        texts = [self.name, *(member_text(m) for m in self.attrs + self.ops)]
        if self.stereotype:
            texts.append(f"<<{self.stereotype}>>")
        self.w = round(max(MIN_W, max(len(t) for t in texts) * CHAR_W + 14))
        head = HEAD_H + (ROW_H if self.stereotype else 0)
        self.h = round(head + 6 + len(self.attrs) * ROW_H + 6
                       + (len(self.ops) * ROW_H + 6 if self.ops else 0))
        self.h = max(self.h, 50)
        self.x = self.y = 0

    @property
    def cx(self): return self.x + self.w / 2

    @property
    def cy(self): return self.y + self.h / 2


def auto_grid(classes, rels, fixed):
    """Đặt tham lam từng class vào ô lưới rẻ nhất:
    gần các class đã nối, ưu tiên cùng hàng/cột (đường thẳng), cha ở ngay trên con,
    phạt đường nối đi xuyên qua ô đã có class."""
    names = [c.name for c in classes]
    adj = {n: [] for n in names}
    up = set()      # (con, cha): cha phải ở hàng trên
    for r in rels:
        adj[r["from"]].append(r["to"]); adj[r["to"]].append(r["from"])
        if r["type"] in ("inheritance", "realization"):
            up.add((r["from"], r["to"]))
    grid = dict(fixed)
    # Thứ tự: bắt đầu từ class nhiều liên kết nhất, rồi BFS ưu tiên bậc cao
    remaining = [n for n in sorted(names, key=lambda n: -len(adj[n])) if n not in grid]
    order, seen = [], set(grid)
    while remaining:
        start = next(n for n in remaining if n not in seen)
        q = deque([start]); seen.add(start)
        while q:
            n = q.popleft(); order.append(n)
            for m in sorted(adj[n], key=lambda m: -len(adj[m])):
                if m not in seen:
                    seen.add(m); q.append(m)
        remaining = [n for n in remaining if n not in seen]

    def blocked(p, q, occ):
        """Số ô bị chiếm nằm giữa p và q (khi cùng hàng/cột) — đường nối sẽ cắt qua."""
        (c1, r1), (c2, r2) = p, q
        if r1 == r2:
            return sum((c, r1) in occ for c in range(min(c1, c2) + 1, max(c1, c2)))
        if c1 == c2:
            return sum((c1, r) in occ for r in range(min(r1, r2) + 1, max(r1, r2)))
        # chéo: kiểm tra hai ô góc
        return ((c1, r2) in occ) + ((c2, r1) in occ)

    for n in order:
        if not grid:
            grid[n] = (0, 0); continue
        occ = set(grid.values())
        cols = [c for c, _ in occ]; rows = [r for _, r in occ]
        best = None
        for c in range(min(cols) - 1, max(cols) + 2):
            for r in range(min(rows) - 1, max(rows) + 2):
                if (c, r) in occ:
                    continue
                cost = 0.0
                for m in adj[n]:
                    if m not in grid:
                        continue
                    cm, rm = grid[m]
                    d = abs(c - cm) + abs(r - rm)
                    cost += d * 10 + (0 if c == cm or r == rm else 6) + blocked((c, r), (cm, rm), occ) * 40
                    if (n, m) in up:        # n là con của m
                        cost += 0 if r == rm + 1 else 60 + abs(r - rm - 1) * 20
                    if (m, n) in up:        # n là cha của m
                        cost += 0 if r == rm - 1 else 60 + abs(r - rm + 1) * 20
                # đường của class khác đi xuyên qua ô này
                for x, y in ((x, y) for x in grid for y in adj[x] if y in grid and x < y):
                    if blocked(grid[x], grid[y], {(c, r)}):
                        cost += 30
                cost += 0.5 * (abs(c) + abs(r))   # gọn về gốc
                if best is None or cost < best[0]:
                    best = (cost, (c, r))
        grid[n] = best[1]
    return grid


LAYOUT_CENTER = None    # (cột, hàng) tâm khung lưới — đặt bởi improve_grid
LAYOUT_DEG = {}         # số liên kết của mỗi class


def grid_cost(grid, edges, up):
    """Tổng chi phí bố cục: đường nối dài, không thẳng hàng, bị class khác chắn giữa; cha phải ở trên con.
    Cực tiểu hoá chi phí này kéo class trung tâm (nhiều liên kết) vào giữa cụm của nó."""
    occ = set(grid.values())
    cost = 0.0
    for x, y in edges:
        (c1, r1), (c2, r2) = grid[x], grid[y]
        d = abs(c1 - c2) + abs(r1 - r2)
        # siêu tuyến tính: nối xa bị phạt nặng (người dùng: "Driver một đường, Alert một nẻo")
        cost += 10 * d + 6 * (d - 1) ** 2 + (0 if c1 == c2 or r1 == r2 else 6)
        if r1 == r2:
            cost += 40 * sum((c, r1) in occ for c in range(min(c1, c2) + 1, max(c1, c2)))
        elif c1 == c2:
            cost += 40 * sum((c1, r) in occ for r in range(min(r1, r2) + 1, max(r1, r2)))
        else:
            cost += 15 * (((c1, r2) in occ) + ((c2, r1) in occ))
        if (x, y) in up:
            cost += 0 if r1 == r2 + 1 else 60 + abs(r1 - r2 - 1) * 20
        if (y, x) in up:
            cost += 0 if r2 == r1 + 1 else 60 + abs(r2 - r1 - 1) * 20
    if LAYOUT_CENTER:       # class nhiều liên kết kéo về tâm sơ đồ
        cx, cy = LAYOUT_CENTER
        for k, (c, r) in grid.items():
            deg = LAYOUT_DEG.get(k, 0)
            if deg >= 4:
                cost += 1.5 * deg * (abs(c - cx) + abs(r - cy))
    return cost


def anneal(grid, cells, edges, up, fixed, iters=40000, restarts=4):
    """Ủ mô phỏng (simulated annealing) với seed cố định — kết quả lặp lại được giữa các lần build.
    Thoát cực tiểu cục bộ mà tìm kiếm tham lam hay mắc (vd. class trung tâm bị đẩy ra rìa)."""
    import math
    import random
    rnd = random.Random(42)
    movable = [k for k in grid if k not in fixed]
    if len(movable) < 2:
        return grid
    best_g, best_c = dict(grid), grid_cost(grid, edges, up)
    for rs in range(restarts):
        g = dict(best_g) if rs == 0 else dict(grid)
        if rs:
            free = [c for c in cells if c not in {g[k] for k in fixed}]
            rnd.shuffle(free)
            for k, c in zip(movable, free):
                g[k] = c
        cur = grid_cost(g, edges, up)
        T0, T1 = 60.0, 0.5
        for it in range(iters):
            T = T0 * (T1 / T0) ** (it / iters)
            k = rnd.choice(movable)
            cell = rnd.choice(cells)
            owner = next((kk for kk, v in g.items() if v == cell), None)
            if owner == k or owner in fixed:
                continue
            here = g[k]
            g[k] = cell
            if owner:
                g[owner] = here
            c = grid_cost(g, edges, up)
            if c <= cur or rnd.random() < math.exp((cur - c) / T):
                cur = c
                if c < best_c:
                    best_c, best_g = c, dict(g)
            else:
                g[k] = here
                if owner:
                    g[owner] = cell
    return best_g


def improve_grid(grid, rels, fixed, passes=12):
    """Tìm kiếm cục bộ: thử dời từng class sang ô trống hoặc đổi chỗ với class khác trong khung
    lưới gọn (ngang hơn dọc, hợp khổ giấy), giữ thay đổi nào giảm chi phí. Class có `pos` không bị dời."""
    import math
    names = list(grid)
    n = len(names)
    edges = [(r["from"], r["to"]) for r in rels if r["from"] != r["to"]]
    up = {(r["from"], r["to"]) for r in rels if r["type"] in ("inheritance", "realization")}
    # khung rộng rãi (người dùng chấp nhận sơ đồ thưa, miễn bố trí khoa học)
    # khung vừa đủ: ít ô trống -> không có vùng thưa (người dùng: "chỗ thưa quá thì co cụm lại")
    ncol = max(3, math.ceil(math.sqrt(n * 1.6)))
    nrow = max(2, math.ceil(n / ncol) + 1)
    global LAYOUT_CENTER, LAYOUT_DEG
    LAYOUT_CENTER = ((ncol - 1) / 2, (nrow - 1) / 2)
    LAYOUT_DEG = {}
    for x, y in edges:
        LAYOUT_DEG[x] = LAYOUT_DEG.get(x, 0) + 1
        LAYOUT_DEG[y] = LAYOUT_DEG.get(y, 0) + 1
    # dịch lưới về gốc và nén vào khung ncol x nrow
    c0 = min(c for c, _ in grid.values()); r0 = min(r for _, r in grid.values())
    grid = {k: (c - c0, r - r0) for k, (c, r) in grid.items()}
    cells = [(c, r) for r in range(nrow) for c in range(ncol)]
    for k in sorted(grid, key=lambda k: grid[k]):
        if k in fixed:
            continue
        c, r = grid[k]
        if c >= ncol or r >= nrow:
            free = [x for x in cells if x not in set(grid.values())]
            grid[k] = min(free, key=lambda x: abs(x[0] - c) + abs(x[1] - r))
    grid = anneal(grid, cells, edges, up, fixed)
    best = grid_cost(grid, edges, up)
    for _ in range(passes):
        improved = False
        for k in names:
            if k in fixed:
                continue
            here = grid[k]
            owner = {v: kk for kk, v in grid.items()}
            for cell in cells:
                if cell == here:
                    continue
                other = owner.get(cell)
                if other in fixed:
                    continue
                grid[k] = cell
                if other:
                    grid[other] = here
                c = grid_cost(grid, edges, up)
                if c < best - 1e-9:
                    best = c; here = cell; improved = True
                    owner = {v: kk for kk, v in grid.items()}
                else:
                    grid[k] = here
                    if other:
                        grid[other] = cell
        if not improved:
            break
    return grid


def layout(classes, rels):
    cs = {c.name: c for c in classes}
    grid = {c.name: tuple(c.pos) for c in classes if c.pos}
    if len(grid) < len(classes):
        fixed = set(grid)
        grid = auto_grid(classes, rels, grid)
        grid = improve_grid(grid, rels, fixed)
    # bỏ cột/hàng trống hoàn toàn (nếu không sẽ thành khoảng trắng rộng ~270px giữa hai cụm)
    cmap = {c: i for i, c in enumerate(sorted({c for c, _ in grid.values()}))}
    rmap = {r: i for i, r in enumerate(sorted({r for _, r in grid.values()}))}
    grid = {n: (cmap[c], rmap[r]) for n, (c, r) in grid.items()}
    ncol = max(c for c, _ in grid.values()) + 1
    nrow = max(r for _, r in grid.values()) + 1
    col_w = [max([cs[n].w for n, (c, _) in grid.items() if c == i] or [MIN_W]) for i in range(ncol)]
    row_h = [max([cs[n].h for n, (_, r) in grid.items() if r == j] or [50]) for j in range(nrow)]
    xs = [MARGIN + sum(col_w[:i]) + GAP_X * i for i in range(ncol)]
    ys = [MARGIN + sum(row_h[:j]) + GAP_Y * j for j in range(nrow)]
    for n, (c, r) in grid.items():
        o = cs[n]
        o.x = round(xs[c] + (col_w[c] - o.w) / 2)
        o.y = round(ys[r])
    return cs


def is_straight(A, B):
    oy = min(A.y + A.h, B.y + B.h) - max(A.y, B.y)
    ox = min(A.x + A.w, B.x + B.w) - max(A.x, B.x)
    return oy > 20 or ox > 20


def free_port(ports, shape, side, want, lo, hi):
    """Chọn toạ độ trên cạnh `side` của `shape` gần `want` nhất mà không trùng cổng đã dùng (cách >= 18px)."""
    used = ports.setdefault((id(shape), side), [])
    for k in range(0, 12):
        for cand in ((want,) if k == 0 else (want + 22 * k, want - 22 * k)):
            if lo + 8 <= cand <= hi - 8 and all(abs(cand - u) >= 18 for u in used):
                used.append(cand)
                return round(cand)
    used.append(want)
    return round(want)


def route(A, B, ports):
    """Đường nối thẳng: ngang nếu hai hình chồng nhau theo chiều dọc, dọc nếu chồng theo chiều ngang;
    không thì gấp khúc vuông góc. Mỗi đường được một 'cổng' riêng trên cạnh class."""
    oy = (max(A.y, B.y), min(A.y + A.h, B.y + B.h))
    ox = (max(A.x, B.x), min(A.x + A.w, B.x + B.w))
    # Điểm đầu/cuối đặt lệch ra ngoài mép 1px như VP làm
    if oy[1] - oy[0] > 20:
        right = A.cx < B.cx
        y = free_port(ports, A, "R" if right else "L", (oy[0] + oy[1]) / 2, *oy)
        ports.setdefault((id(B), "L" if right else "R"), []).append(y)
        return ((A.x + A.w + 1, y), (B.x - 1, y)) if right else ((A.x - 1, y), (B.x + B.w + 1, y))
    if ox[1] - ox[0] > 20:
        down = A.cy < B.cy
        x = free_port(ports, A, "B" if down else "T", (ox[0] + ox[1]) / 2, *ox)
        ports.setdefault((id(B), "T" if down else "B"), []).append(x)
        return ((x, A.y + A.h + 1), (x, B.y - 1)) if down else ((x, A.y - 1), (x, B.y + B.h + 1))
    down = A.cy < B.cy
    x1 = free_port(ports, A, "B" if down else "T", A.cx, A.x, A.x + A.w)
    x2 = free_port(ports, B, "T" if down else "B", B.cx, B.x, B.x + B.w)
    p1 = (x1, A.y + A.h + 1 if down else A.y - 1)
    p2 = (x2, B.y - 1 if down else B.y + B.h + 1)
    mid = round((p1[1] + p2[1]) / 2)
    return (p1, (p1[0], mid), (p2[0], mid), p2)


def class_model(c: Cls):
    kids = []
    for m in c.attrs:
        kids.append(f'<Attribute Id={a(new_id())} Name={a(m["name"])} Type={a(m["type"])} '
                    f'Visibility="{m["vis"]}" Scope="instance" Multiplicity="Unspecified" Visible="true"/>')
    for m in c.ops:
        ps = "".join(f'<Parameter Direction="in" Id={a(new_id())} Name={a(n)} Type={a(t)} '
                     f'Multiplicity="Unspecified"/>' for n, t in m["params"])
        kids.append(f'<Operation Id={a(new_id())} Name={a(m["name"])} ReturnType={a(m["type"])} '
                    f'Visibility="{m["vis"]}" Scope="instance" Visible="true">'
                    + (f'<ModelChildren>{ps}</ModelChildren>' if ps else "") + '</Operation>')
    st = ""
    if c.stereotype:
        st = f'<Stereotypes><Stereotype Idref={a(c.st_id)} Name={a(c.stereotype)}/></Stereotypes>'
    return (f'<Class Abstract="{str(c.abstract).lower()}" Id={a(c.model_id)} Name={a(c.name)} Visibility="public">'
            f'{st}<ModelChildren>{"".join(kids)}</ModelChildren>'
            f'<MasterView><Class Idref={a(c.shape_id)} Name={a(c.name)}/></MasterView></Class>')


def class_shape(c: Cls):
    return (f'<Class Background="{FILL}" ConnectToPoint="true" ConnectionPointType="2" CoverConnector="false" '
            f'CreatorDiagramType="ClassDiagram" Foreground="rgb(0, 0, 0)" Height="{c.h}" Id={a(c.shape_id)} '
            f'MetaModelElement={a(c.model_id)} Model={a(c.model_id)} ModelElementNameAlignment="9" Name={a(c.name)} '
            f'PresentationOption="4" Selectable="true" ShowAttributeType="1" ShowOperationSignature="true" '
            f'ShowOperationType="1" ShowEmptyCompartments="0" ShowTypeOption="0" VisibilityStyle="1" '
            f'ShowParameterNameInOperationSignature="true" Width="{c.w}" X="{c.x}" Y="{c.y}">'
            f'{FONT}{LINE}<Caption Height="{30 if c.stereotype else 15}" Side="FreeMove" Visible="true" '
            f'Width="{c.w}" X="0" Y="0"/>'
            f'{FILLC}<CompartmentFont Value="none"/></Class>')


def conn_box(pts):
    # VP cắt (clip) mọi thứ ngoài khung này: phải nới 50px mỗi phía như VP, nếu không hình thoi/mũi tên bị bẹp
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (f'X="{min(xs) - 50}" Y="{min(ys) - 50}" '
            f'Width="{max(xs) - min(xs) + 100}" Height="{max(ys) - min(ys) + 100}"')


def points(pts):
    return "<Points>" + "".join(f'<Point X="{x}.0" Y="{y}.0"/>' for x, y in pts) + "</Points>"


def label_at(pts):
    """Giữa đoạn dài nhất của đường nối."""
    segs = list(zip(pts, pts[1:]))
    (x1, y1), (x2, y2) = max(segs, key=lambda s: abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))
    return (x1 + x2) // 2, (y1 + y2) // 2


def center_parents(cs, rels):
    """Lớp cha có >= 2 lớp con ở hàng dưới: dời cha ra giữa các con nếu không đè lên class khác."""
    kids = {}
    for r in rels:
        if r["type"] in ("inheritance", "realization"):
            kids.setdefault(r["to"], []).append(cs[r["from"]])
    for p, ch in kids.items():
        P = cs[p]
        if len(ch) < 2 or not all(c.y > P.y + P.h for c in ch):
            continue
        new_x = round((min(c.cx for c in ch) + max(c.cx for c in ch)) / 2 - P.w / 2)
        clash = any(o is not P and o.y < P.y + P.h and P.y < o.y + o.h
                    and o.x < new_x + P.w + 30 and new_x < o.x + o.w + 30 for o in cs.values())
        if not clash:
            P.x = new_x


def generate(spec) -> str:
    classes = [Cls(d) for d in spec["classes"]]
    rels = spec.get("relations", [])
    stereo = {}
    for c in classes:
        if c.stereotype:
            c.st_id = stereo.setdefault(c.stereotype, new_id())
    cs = layout(classes, rels)
    center_parents(cs, rels)
    models = [class_model(c) for c in classes]
    models += [f'<Stereotype BaseType="Class" Id={a(i)} Name={a(n)}/>' for n, i in stereo.items()]
    rel_models, conns = [], []
    common = (f'ConnectorStyle="Follow Diagram" Foreground="rgb(0, 0, 0)" '
              f'FromConnectType="0" ToConnectType="0" FromPinType="1" ToPinType="1" '
              f'FromShapeXDiff="0" FromShapeYDiff="0" ToShapeXDiff="0" ToShapeYDiff="0" '
              f'UseFromShapeCenter="true" UseToShapeCenter="true" ConnectorLabelOrientation="4" '
              f'ConnectorLineJumps="1" '
              f'ModelElementNameAlignment="9" PaintThroughLabel="2" Selectable="true" ShowConnectorName="2" ')

    # Đường thẳng giữ cổng trước, đường gấp khúc chọn cổng sau để né
    ports = {}
    def ends(r):   # inheritance/realization vẽ từ cha (From) -> con (To) trong VP
        A, B = cs[r["from"]], cs[r["to"]]
        return (B, A) if r["type"] not in ("association", "aggregation", "composition") else (A, B)
    # Định tuyến né hình + không trùng nét (router.py); không tìm được thì dùng route() cũ
    routes = dict(enumerate(route_all([ends(r) for r in rels], classes,
                                      fallback=lambda A, B: route(A, B, ports))))

    for i, r in enumerate(rels):
        A, B = cs[r["from"]], cs[r["to"]]
        mid, vid = new_id(), new_id()
        t = r["type"]
        pts = routes[i]
        lx, ly = label_at(pts)
        if t in ("association", "aggregation", "composition"):
            kind = {"association": "None", "aggregation": "Shared", "composition": "Composited"}[t]
            def end(c, agg, mult):
                return (f'<AssociationEnd AggregationKind="{agg}" EndModelElement={a(c.model_id)} Id={a(new_id())} '
                        f'Multiplicity={a(mult or "Unspecified")} Navigable="Navigable" Visibility="Unspecified">'
                        f'<Type><Class Idref={a(c.model_id)} Name={a(c.name)}/></Type></AssociationEnd>')
            rel_models.append(
                f'<Association Direction="From To" EndRelationshipFromMetaModelElement={a(A.model_id)} '
                f'EndRelationshipToMetaModelElement={a(B.model_id)} Id={a(mid)} Name={a(r.get("label", ""))} '
                f'Visibility="Unspecified"><FromEnd>{end(A, kind, r.get("from_mult"))}</FromEnd>'
                f'<ToEnd>{end(B, "None", r.get("to_mult"))}</ToEnd>'
                f'<MasterView><Association Idref={a(vid)}/></MasterView></Association>')
            # Background = màu tô đầu nối: trắng cho thoi rỗng (composition tự tô đen)
            conns.append(f'<Association Background="rgb(255, 255, 255)" {common}CreatorDiagramType="ClassDiagram" '
                         f'From={a(A.shape_id)} To={a(B.shape_id)} Id={a(vid)} MetaModelElement={a(mid)} Model={a(mid)} '
                         f'ShowFromMultiplicity="true" ShowToMultiplicity="true" ShowFromRoleName="true" '
                         f'ShowToRoleName="true" ShowNavigationArrows="0" ShowStereotypes="true" '
                         f'{conn_box(pts)}>{FONT}{LINE}'
                         f'<Caption Height="0" Side="None" Visible="true" Width="20" X="{lx}" Y="{ly}"/>'
                         f'{points(pts)}</Association>')
        else:
            tag = {"inheritance": "Generalization", "realization": "Realization", "dependency": "Dependency"}[t]
            # VP: From = lớp cha/nhà cung cấp, To = lớp con/khách (giống Extend) — kiểm chứng qua ảnh
            sup, sub = (B, A)
            rel_models.append(f'<{tag} From={a(sup.model_id)} To={a(sub.model_id)} Id={a(mid)} '
                              f'Name={a(r.get("label", ""))} Visibility="Unspecified">'
                              f'<MasterView><{tag} Idref={a(vid)}/></MasterView></{tag}>')
            q = pts
            qx, qy = label_at(q)
            # Background trắng -> tam giác rỗng màu trắng như chuẩn UML
            conns.append(f'<{tag} Background="rgb(255, 255, 255)" {common}From={a(sup.shape_id)} '
                         f'To={a(sub.shape_id)} Id={a(vid)} MetaModelElement={a(mid)} Model={a(mid)} '
                         f'{conn_box(q)}>{FONT}{LINE}'
                         f'<Caption Height="0" Side="None" Visible="true" Width="20" X="{qx}" Y="{qy}"/>'
                         f'{points(q)}</{tag}>')

    # ZOrder: đường nối vẽ đè lên class, nếu không class sẽ che mất hình thoi/mũi tên
    shapes = [s.replace(" ", f' ZOrder="{i + 1}" ', 1) for i, s in enumerate(class_shape(c) for c in classes)]
    conns = [s.replace(" ", f' ZOrder="{1000 + i}" ', 1) for i, s in enumerate(conns)]
    right = max(c.x + c.w for c in classes) + MARGIN
    bottom = max(c.y + c.h for c in classes) + MARGIN
    name = spec.get("name", "Class Diagram")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Project Author="vpgen" ExporterVersion="16.1.1" Name={a(name)} UmlVersion="2.x" Xml_structure="simple">'
        '<Models>' + "".join(models) +
        f'<ModelRelationshipContainer Id={a(new_id())} Name="relationships"><ModelChildren>'
        + "".join(rel_models) + '</ModelChildren></ModelRelationshipContainer></Models>'
        f'<Diagrams><ClassDiagram Id={a(new_id())} Name={a(name)} ConnectorStyle="1" '
        f'ConnectorLineJumps="0" ConnectorLineJumpsSize="0" DiagramBackground="rgb(255, 255, 255)" ShowAttributesType="1" ShowOperationsParameters="1" '
        f'ShowOperationsReturnType="1" ShowClassEmptyCompartments="2" ShowStereotypes="true" '
        f'Width="{right}" Height="{bottom}" X="0" Y="0" ZoomRatio="1.0">'
        '<Shapes>' + "".join(shapes) + '</Shapes>'
        '<Connectors>' + "".join(conns) + '</Connectors></ClassDiagram></Diagrams></Project>\n'
    )


def main(spec_file, out_dir="out", *image_types):
    spec = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    write_and_build(generate(spec), spec, spec_file, out_dir, list(image_types) or None)


if __name__ == "__main__":
    main(*sys.argv[1:])
