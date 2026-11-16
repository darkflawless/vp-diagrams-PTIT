"""Sinh XML Use Case Diagram cho Visual Paradigm từ file mô tả JSON, tự tính bố cục.

Cách dùng:  python vpgen/usecase.py examples/thu_vien.json out/
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import STYLE, FILL, FONT, LINE, FILLC, a, new_id, write_and_build  # noqa: E402

# ---- Thông số bố cục ----
CHAR_W = 6.6          # bề rộng trung bình 1 ký tự Dialog 11
UC_H = 46             # chiều cao use case
UC_H_EXT = 62         # use case có ngăn extension points
ROW = 78              # khoảng cách dọc giữa các use case
COL_GAP = 130         # khoảng cách giữa các cột
ACTOR_W, ACTOR_H = 30, 60
MARGIN = 40

class Node:
    def __init__(self, name, kind):
        self.key, self.kind = name, kind
        # Use case: tự ngắt dòng để chữ nằm gọn giữa bầu dục
        self.name = "\n".join(wrap(name)) if kind == "uc" else name
        self.model_id, self.shape_id = new_id(), new_id()
        self.x = self.y = self.w = self.h = 0
        self.ext_points: list[str] = []

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def border(self, tx, ty):
        """Điểm trên biên hình theo hướng tới (tx, ty)."""
        dx, dy = tx - self.cx, ty - self.cy
        if dx == dy == 0:
            return self.cx, self.cy
        if self.kind == "actor":   # hình chữ nhật bao quanh hình người
            s = min((self.w / 2) / abs(dx) if dx else math.inf, (self.h / 2) / abs(dy) if dy else math.inf)
        else:                      # ellipse
            rx, ry = self.w / 2, self.h / 2
            s = 1 / math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
        return round(self.cx + dx * s), round(self.cy + dy * s)


WRAP = 22             # số ký tự tối đa mỗi dòng trong use case
LINE_H = 14


def wrap(text, n=WRAP):
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur] if cur else lines


def uc_size(name, has_ext):
    """Kích thước bầu dục vừa chữ: chữ nằm trong hình chữ nhật nội tiếp (~0.7 trục)."""
    lines = wrap(name)
    text_w = max(len(l) for l in lines) * CHAR_W
    text_h = len(lines) * LINE_H + (2 * LINE_H if has_ext else 0)
    return max(140, text_w / 0.72 + 16), max(UC_H, text_h / 0.6 + 14)


def layout(spec):
    actors = {n: Node(n, "actor") for n in spec["actors"]}
    ucs = {n: Node(n, "uc") for n in spec["usecases"]}
    links = spec.get("links", [])
    includes = spec.get("include", [])          # [base, included]
    extends = spec.get("extend", [])            # [extension, base]
    gens = spec.get("generalization", [])       # [con, cha] (actor-actor hoặc usecase-usecase)
    for ext, base in extends:
        if spec.get("show_extension_points", False):
            ucs[base].ext_points.append(ext)

    for n in spec["usecases"]:
        ucs[n].want_w, ucs[n].h = uc_size(n, bool(ucs[n].ext_points))
    tb = {n: "top" for n in spec.get("top_actors", [])} | {n: "bottom" for n in spec.get("bottom_actors", [])}
    left = [n for n in spec["actors"] if n not in spec.get("right_actors", []) and n not in tb]
    right = [n for n in spec["actors"] if n in spec.get("right_actors", [])]
    place_grid(spec, actors, ucs, links, includes + [g for g in gens if g[0] in ucs], extends, left, right, tb)

    everything = [*actors.values(), *ucs.values()]
    top = min(o.y_center - o.h / 2 for o in everything)
    cross = any(c in actors and p in actors and c not in tb and p not in tb and ((c in left) != (p in left)) for c, p in gens)
    extra = 60 if cross else 0    # chừa chỗ cho nét tổng quát hoá đi vòng phía trên khung
    for o in everything:          # mọi hình căn theo tâm
        o.y = round(MARGIN + 30 + extra + (o.y_center - o.h / 2 - top))
        o.x = round(o.x); o.w = round(o.w); o.h = round(o.h)
    return actors, ucs, links, includes, extends, gens


# ---- Bố cục bằng tối ưu: nét thẳng KHÔNG được cắt qua use case/actor khác, ít cắt nhau ----
def seg_hits_ellipse(p, q, cx, cy, rx, ry):
    """Đoạn p-q có đi vào trong ellipse (tâm cx,cy; bán trục rx,ry) không."""
    x1, y1 = (p[0] - cx) / rx, (p[1] - cy) / ry
    x2, y2 = (q[0] - cx) / rx, (q[1] - cy) / ry
    dx, dy = x2 - x1, y2 - y1
    aa = dx * dx + dy * dy
    if aa == 0:
        return x1 * x1 + y1 * y1 < 1
    t = max(0.0, min(1.0, -(x1 * dx + y1 * dy) / aa))
    px, py = x1 + t * dx, y1 + t * dy
    return px * px + py * py < 1


def seg_cross(p1, p2, p3, p4):
    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2, d3, d4 = o(p3, p4, p1), o(p3, p4, p2), o(p1, p2, p3), o(p1, p2, p4)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def place_grid(spec, actors, ucs, links, includes, extends, left, right, tb=None):
    tb = tb or {}
    """Đặt use case vào lưới ô (cột x hàng) bằng ủ mô phỏng (seed cố định).
    Chi phí: nét đi xuyên use case/actor khác (rất nặng), hai nét cắt nhau, độ dài nét.
    Actor trái/phải đứng ngang tầm trung bình các use case nó nối tới."""
    import random
    names = list(ucs)
    n = len(names)
    ncol = 3 if n >= 7 else 2
    if n <= 3:
        ncol = 1
    ncol = spec.get("ncol", ncol)
    fixed = spec.get("uc_col", {})               # {use case: cột} ép use case vào một cột
    pinned = {k: tuple(v) for k, v in spec.get("uc_cell", {}).items()}   # {use case: [cột, hàng]} ghim cứng
    nrow = math.ceil(n / ncol) + 1
    if pinned:
        nrow = max(nrow, max(r for _, r in pinned.values()) + 1)
    if fixed:
        per = [sum(1 for k in names if fixed.get(k) == c) for c in range(ncol)]
        free = n - sum(per)
        nrow = max(nrow, max(per) + 1, math.ceil((sum(per) + free) / ncol) + 1)
    colw = max([150] + [ucs[k].want_w for k in names])
    rowh = max([UC_H] + [ucs[k].h for k in names]) + 64   # đủ chỗ cho nhãn <<include>> và đầu mũi tên giữa hai hàng
    x_actor_l = MARGIN + 20
    x0 = x_actor_l + ACTOR_W + spec.get("actor_gap", COL_GAP)
    xs = [x0 + c * (colw + 70) for c in range(ncol)]
    x_actor_r = xs[-1] + colw + spec.get("actor_gap", COL_GAP)
    for k in names:
        ucs[k].w = colw
    for k in left + right + list(tb):
        actors[k].w, actors[k].h = ACTOR_W, ACTOR_H
        actors[k].x = x_actor_l if k in left else x_actor_r

    segs = [(ac, u) for ac, u in links] + [(b, i) for b, i in includes] + [(e, b) for e, b in extends]

    def apply(g):
        for k, (c, r) in g.items():
            u = ucs[k]
            u.x = xs[c]
            u.y_center = r * rowh
        for group in (left, right):
            items = []
            for ac in group:
                ys = [ucs[u].y_center for a_, u in links if a_ == ac] or [0]
                items.append((sum(ys) / len(ys), ac))
            last = -math.inf
            for want, ac in sorted(items):
                yc = max(want, last + ACTOR_H + 50)
                actors[ac].y_center = yc
                last = yc
        # actor đặt trên đỉnh / dưới đáy khung (như "Thành viên" trong mẫu): ngang tâm các use case nó nối
        maxrow = max(r for _, r in g.values())
        for ac, side in tb.items():
            xs_ = [ucs[u].x + ucs[u].w / 2 for a_, u in links if a_ == ac] or [(xs[0] + xs[-1] + colw) / 2]
            actors[ac].x = sum(xs_) / len(xs_) - ACTOR_W / 2
            actors[ac].y_center = -1.5 * rowh if side == "top" else (maxrow + 1.5) * rowh

    def center(k):
        o = actors.get(k) or ucs[k]
        return (o.x + o.w / 2, o.y_center)

    def cost(g):
        apply(g)
        pts = [(center(a_), center(b), a_, b) for a_, b in segs]
        c = 0.0
        for p, q, a_, b in pts:
            c += 0.02 * math.dist(p, q)
            for k in names:
                if k in (a_, b):
                    continue
                u = ucs[k]
                if seg_hits_ellipse(p, q, u.x + u.w / 2, u.y_center, u.w / 2 + 10, u.h / 2 + 10):
                    c += 1000
            for k in left + right + list(tb):
                if k in (a_, b):
                    continue
                ax, ay = center(k)
                if seg_hits_ellipse(p, q, ax, ay, ACTOR_W, ACTOR_H / 2 + 15):
                    c += 1000
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                if {pts[i][2], pts[i][3]} & {pts[j][2], pts[j][3]}:
                    continue
                if seg_cross(pts[i][0], pts[i][1], pts[j][0], pts[j][1]):
                    c += 60
        # actor bên trái nên nối use case cột trái, bên phải nối cột phải
        for ac, u in links:
            col = g[u][0]
            c += 25 * (col if ac in left else (ncol - 1 - col))
        return c

    cells = [(c, r) for r in range(nrow) for c in range(ncol)]
    rnd = random.Random(7)
    g, used = dict(pinned), set(pinned.values())
    for k in sorted((k for k in names if k not in pinned), key=lambda k: k not in fixed):
        cell = next(c for c in cells if c not in used and (k not in fixed or c[0] == fixed[k]))
        g[k] = cell
        used.add(cell)
    cur = cost(g)
    best, best_c = dict(g), cur
    iters = 4000
    for it in range(iters):
        T = 300 * (0.5 / 300) ** (it / iters)
        k = rnd.choice(names)
        cell = rnd.choice(cells)
        other = next((kk for kk, v in g.items() if v == cell), None)
        if other == k:
            continue
        here = g[k]
        if (k in fixed and cell[0] != fixed[k]) or (other in fixed and here[0] != fixed[other]):
            continue
        if k in pinned or other in pinned:
            continue
        g[k] = cell
        if other:
            g[other] = here
        c = cost(g)
        if c <= cur or rnd.random() < math.exp((cur - c) / T):
            cur = c
            if c < best_c:
                best, best_c = dict(g), c
        else:
            g[k] = here
            if other:
                g[other] = cell
    # dồn hàng trống
    rows = sorted({r for _, r in best.values()})
    rmap = {r: i for i, r in enumerate(rows)}
    best = {k: (c, rmap[r]) for k, (c, r) in best.items()}
    apply(best)
    if best_c >= 1000:
        print(f"[usecase] cảnh báo: còn nét đi qua hình (chi phí {best_c:.0f}) — thử đổi tên/bớt quan hệ")


# ------------------------------------------------------------------ XML
def shape_xml(o: Node):
    common = (f'Background="{FILL}" ConnectToPoint="true" ConnectionPointType="2" CoverConnector="false" '
              f'DisplayOption="3" Foreground="rgb(0, 0, 0)" Height="{o.h}" Id={a(o.shape_id)} '
              f'MetaModelElement={a(o.model_id)} Model={a(o.model_id)} ModelElementNameAlignment="9" '
              f'Name={a(o.name)} OverrideAppearanceWithStereotypeIcon="true" PresentationOption="4" '
              f'Selectable="true" Width="{o.w}" X="{o.x}" Y="{o.y}"')
    if o.kind == "actor":
        cap_w = max(46, round(len(o.name) * CHAR_W + 10))
        cap = (f'<Caption Height="15" Side="South" Visible="true" Width="{cap_w}" '
               f'X="{round(o.cx - cap_w / 2)}" Y="{o.y + o.h}"/>')
        return f'<Actor {common} CreatorDiagramType="UseCaseDiagram">{FONT}{LINE}{cap}{FILLC}</Actor>'
    # Vùng chữ = hình chữ nhật nội tiếp bầu dục, để chữ không chạm mép
    cw = round(o.w * 0.74)
    cap = f'<Caption Height="{o.h}" Side="Center" Visible="true" Width="{cw}" X="{round((o.w - cw) / 2)}" Y="0"/>'
    show_ep = "true" if o.ext_points else "false"
    return f'<UseCase {common} ShowExtensionPoint="{show_ep}">{FONT}{LINE}{cap}{FILLC}</UseCase>'


def connector_xml(tag, rel_id, model_id, frm: Node, to: Node, extra="", label=True, bg=None, pts=None):
    p1 = frm.border(to.cx, to.cy)
    p2 = to.border(frm.cx, frm.cy)
    if pts:
        p1, p2 = pts[0], pts[-1]
    # actor có nhãn tên nằm dưới hình: nét đi xuống thì bắt đầu dưới nhãn, kẻo nhãn che đầu mũi tên
    if frm.kind == "actor" and to.cy > frm.cy + frm.h and abs(to.cx - frm.cx) < frm.w:
        p1 = (p1[0], p1[1] + 18)
    if to.kind == "actor" and frm.cy > to.cy + to.h and abs(to.cx - frm.cx) < to.w:
        p2 = (p2[0], p2[1] + 18)
    # khung bao nới 50px mỗi phía như VP (VP clip nét vẽ theo khung này)
    allp = pts or [p1, p2]     # khung bao phải chứa MỌI điểm gấp, nếu không VP cắt mất đoạn nét
    x, y = min(q[0] for q in allp) - 50, min(q[1] for q in allp) - 50
    w = max(q[0] for q in allp) - min(q[0] for q in allp) + 100
    h = max(q[1] for q in allp) - min(q[1] for q in allp) + 100
    return (f'<{tag} Background="{bg or FILL}" ConnectorStyle="Follow Diagram" Foreground="rgb(0, 0, 0)" '
            f'From={a(frm.shape_id)} To={a(to.shape_id)} FromConnectType="0" ToConnectType="0" '
            f'FromPinType="1" ToPinType="1" UseFromShapeCenter="true" UseToShapeCenter="true" '
            f'Id={a(rel_id)} MetaModelElement={a(model_id)} Model={a(model_id)} ModelElementNameAlignment="9" '
            f'PaintThroughLabel="2" Selectable="true" ShowConnectorName="2" {extra}'
            f'X="{x}" Y="{y}" Width="{w}" Height="{h}">{FONT}{LINE}'
            f'<Caption Height="{15 if label else 0}" Side="None" Visible="true" Width="{82 if label else 20}" '
            f'X="{round((p1[0] + p2[0]) / 2 - 41)}" Y="{round((p1[1] + p2[1]) / 2 - 18)}"/>'
            '<Points>' + "".join(f'<Point X="{q[0]}.0" Y="{q[1]}.0"/>' for q in (pts or [p1, p2])) + f'</Points></{tag}>')


def generate(spec) -> str:
    actors, ucs, links, includes, extends, gens = layout(spec)
    st_inc, st_ext = new_id(), new_id()
    models, rels, shapes, conns = [], [], [], []

    for o in actors.values():
        models.append(f'<Actor Id={a(o.model_id)} Name={a(o.name)} Visibility="public">'
                      f'<MasterView><Actor Idref={a(o.shape_id)} Name={a(o.name)}/></MasterView></Actor>')
    for o in ucs.values():
        eps = "".join(f'<ExtensionPoint Id={a(new_id())} Name={a(e)}/>' for e in o.ext_points)
        models.append(f'<UseCase Id={a(o.model_id)} Name={a(o.name)}>'
                      + (f'<ExtensionPoints>{eps}</ExtensionPoints>' if eps else "")
                      + f'<MasterView><UseCase Idref={a(o.shape_id)} Name={a(o.name)}/></MasterView></UseCase>')
    models.append(f'<Stereotype BaseType="Include" Id={a(st_inc)} Name="include"/>')
    models.append(f'<Stereotype BaseType="Extend" Id={a(st_ext)} Name="extend"/>')

    for ac, u in links:
        mid, vid = new_id(), new_id()
        A, U = actors[ac], ucs[u]
        end = lambda e: (f'<AssociationEnd AggregationKind="None" EndModelElement={a(e.model_id)} Id={a(new_id())} '
                         f'Multiplicity="Unspecified" Navigable="Navigable" Visibility="Unspecified">'
                         f'<Type><{"Actor" if e.kind == "actor" else "UseCase"} Idref={a(e.model_id)} Name={a(e.name)}/></Type>'
                         f'</AssociationEnd>')
        rels.append(f'<Association Direction="From To" EndRelationshipFromMetaModelElement={a(A.model_id)} '
                    f'EndRelationshipToMetaModelElement={a(U.model_id)} Id={a(mid)} Visibility="Unspecified">'
                    f'<FromEnd>{end(A)}</FromEnd><ToEnd>{end(U)}</ToEnd>'
                    f'<MasterView><Association Idref={a(vid)}/></MasterView></Association>')
        conns.append(connector_xml("Association", vid, mid, A, U,
                                   'ShowFromMultiplicity="false" ShowToMultiplicity="false" ShowNavigationArrows="0" ',
                                   label=False))

    for base, inc in includes:
        mid, vid = new_id(), new_id()
        B, I = ucs[base], ucs[inc]
        rels.append(f'<Include From={a(B.model_id)} To={a(I.model_id)} Id={a(mid)} Visibility="Unspecified">'
                    f'<Stereotypes><Stereotype Idref={a(st_inc)} Name="include"/></Stereotypes>'
                    f'<MasterView><Include Idref={a(vid)}/></MasterView></Include>')
        conns.append(connector_xml("Include", vid, mid, B, I))

    for ext, base in extends:
        mid, vid = new_id(), new_id()
        E, B = ucs[ext], ucs[base]
        # Trong VP: Extend From = use case gốc (đầu mũi tên), To = use case mở rộng
        rels.append(f'<Extend From={a(B.model_id)} To={a(E.model_id)} Id={a(mid)} Visibility="Unspecified">'
                    f'<Stereotypes><Stereotype Idref={a(st_ext)} Name="extend"/></Stereotypes>'
                    f'<MasterView><Extend Idref={a(vid)}/></MasterView></Extend>')
        conns.append(connector_xml("Extend", vid, mid, B, E, 'ShowCondition="0" '))

    for child, parent in gens:
        mid, vid = new_id(), new_id()
        C = actors.get(child) or ucs[child]
        P = actors.get(parent) or ucs[parent]
        # VP: Generalization From = cha, To = con (giống class); tam giác rỗng nền trắng
        rels.append(f'<Generalization From={a(P.model_id)} To={a(C.model_id)} Id={a(mid)} Visibility="Unspecified">'
                    f'<MasterView><Generalization Idref={a(vid)}/></MasterView></Generalization>')
        route = None
        side = {n: "top" for n in spec.get("top_actors", [])} | {n: "bottom" for n in spec.get("bottom_actors", [])}
        if C.kind == P.kind == "actor" and parent in side and child not in side:
            # nét gấp khúc: từ cạnh bên của actor đỉnh/đáy đi ngang rồi thẳng xuống/lên tới actor con
            px = P.x if C.cx < P.cx else P.x + P.w
            pcy = round(P.y + P.h / 2)
            # các actor con cùng phía, xếp theo khoảng cách tới actor cha: actor gần nhất đi thẳng,
            # actor xa hơn đi lệch ra ngoài rồi vào cạnh bên, kẻo nét chạy xuyên qua actor đứng giữa
            same = sorted((actors[c_] for c_, p_ in gens if p_ == parent and c_ in actors
                           and (actors[c_].cx < P.cx) == (C.cx < P.cx)),
                          key=lambda o: abs(o.cy - P.cy))
            i = same.index(C)
            if i == 0:
                cy_end = C.y if side[parent] == "top" else C.y + C.h + 18
                route = [(round(px), pcy), (round(C.cx), pcy), (round(C.cx), cy_end)]
            else:
                out = -1 if C.cx < P.cx else 1
                vx = round(C.cx + out * (C.w / 2 + 16 * i))
                ex = C.x if out < 0 else C.x + C.w
                route = [(round(px), pcy - 16 * i), (vx, pcy - 16 * i), (vx, round(C.cy)), (round(ex), round(C.cy))]
        elif C.kind == P.kind == "actor" and abs(C.cx - P.cx) > 200:
            # actor ở hai phía khung hệ thống: đi vòng phía trên khung, không cắt qua use case
            ytop = min(u.y for u in ucs.values()) - 80
            route = [(round(P.cx), P.y), (round(P.cx), ytop), (round(C.cx), ytop), (round(C.cx), C.y)]
        conns.append(connector_xml("Generalization", vid, mid, P, C, label=False, bg="rgb(255, 255, 255)", pts=route))

    shapes = [shape_xml(o) for o in [*ucs.values(), *actors.values()]]
    sys_name = spec.get("system")
    if sys_name:
        pad, title = 30, 22
        sx = min(u.x for u in ucs.values()) - pad
        sy = min(u.y for u in ucs.values()) - pad - title
        sw = max(u.x + u.w for u in ucs.values()) + pad - sx
        sh = max(u.y + u.h for u in ucs.values()) + pad + 30 - sy
        sm, ss = new_id(), new_id()
        children = "".join(f'<UseCase Idref={a(u.model_id)} Name={a(u.name)}/>' for u in ucs.values())
        models.append(f'<System Id={a(sm)} Name={a(sys_name)}><MasterView><System Idref={a(ss)} Name={a(sys_name)}/>'
                      f'</MasterView></System>')
        sys_fill = STYLE.get("system_fill", FILL)
        shapes.insert(0, f'<System Background="{sys_fill}" Foreground="rgb(0, 0, 0)" Id={a(ss)} '
                         f'MetaModelElement={a(sm)} Model={a(sm)} Name={a(sys_name)} Selectable="true" '
                         f'X="{sx}" Y="{sy}" Width="{sw}" Height="{sh}">{FONT}{LINE}'
                         f'<Caption Height="20" Side="Top" Visible="true" Width="{sw}" X="0" Y="0"/>'
                         f'<FillColor Color="{sys_fill}" Style="1" Transparency="0" Type="1"/></System>')
    right = max(o.x + o.w for o in [*actors.values(), *ucs.values()]) + MARGIN + 60
    bottom = max(o.y + o.h for o in [*actors.values(), *ucs.values()]) + MARGIN + 120
    name = spec.get("name", "Use Case Diagram")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Project Author="vpgen" ExporterVersion="16.1.1" Name={a(name)} UmlVersion="2.x" Xml_structure="simple">'
        '<Models>' + "".join(models) +
        f'<ModelRelationshipContainer Id={a(new_id())} Name="relationships"><ModelChildren>'
        + "".join(rels) + '</ModelChildren></ModelRelationshipContainer></Models>'
        f'<Diagrams><UseCaseDiagram Id={a(new_id())} Name={a(name)} ConnectorStyle="1" '
        f'DiagramBackground="rgb(255, 255, 255)" ShowDiagramFrame="false" ShowStereotypes="true" '
        f'ShowUseCaseExtensionPoint="true" Width="{right}" Height="{bottom}" X="0" Y="0" ZoomRatio="1.0">'
        '<Shapes>' + "".join(shapes) + '</Shapes><Connectors>' + "".join(conns) + '</Connectors>'
        '</UseCaseDiagram></Diagrams></Project>\n'
    )


def main(spec_file, out_dir="out", *image_types):
    spec = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    write_and_build(generate(spec), spec, spec_file, out_dir, list(image_types) or None)


if __name__ == "__main__":
    main(*sys.argv[1:])
