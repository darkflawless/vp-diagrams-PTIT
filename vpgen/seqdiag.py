"""Sinh XML Sequence Diagram cho Visual Paradigm từ file mô tả JSON.

Cách dùng:  python vpgen/seqdiag.py examples/hoa_don.json out/

  "lifelines": [{"name": "Dashboard.xml", "kind": "boundary"}, ...]
       kind: boundary | control | entity | (bỏ trống = hộp thường)
  "messages": [
       {"from": "A", "to": "B", "text": "login(user, pass)"},     # lời gọi: mũi tên đặc
       {"from": "B", "to": "A", "text": "ok", "return": true},    # trả về: nét đứt
       {"from": "B", "to": "B", "text": "validate()"},            # tự gọi
       {"from": "A", "to": "C", "text": "publish(topic)", "async": true}  # bất đồng bộ (fire-and-forget):
                                     # mũi tên mở, KHÔNG cần trả về (MQTT publish, đẩy SSE, UDP...)
  ]
Khối điều kiện / lặp (combined fragment) — đặt xen giữa các message:
       {"fragment": "alt", "operands": [
            {"guard": "hợp lệ", "messages": [...]},
            {"guard": "else",   "messages": [...]}]}
       {"fragment": "opt" | "loop" | "break" | "par" | "critical", "guard": "...", "messages": [...]}
  Khung tương tác lồng (sd = "sequence diagram", khung đặt tên cho một kịch bản con):
       {"frame": "Tên kịch bản", "messages": [...]}
  Các khối lồng nhau được; khối tự bao đủ các lifeline có message bên trong.
Activation tự tính: bắt đầu khi lifeline nhận lời gọi, kết thúc khi nó trả về
(hoặc khi luồng điều khiển quay lại lifeline gọi nó).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FONT, LINE, FILLC, FILL, a, new_id, write_and_build  # noqa: E402

CHAR_W = 6.3
TOP = 40              # đỉnh lifeline
FIRST_Y = 160         # message đầu tiên
STEP = 32             # khoảng cách dọc giữa các message
SELF_STEP = 50
ACT_W = 8
MIN_GAP = 160
MARGIN = 40


class Life:
    def __init__(self, d):
        self.name, self.kind = d["name"], d.get("kind")
        self.model_id, self.shape_id = new_id(), new_id()
        self.w = {"boundary": 90, "actor": 60}.get(self.kind, 70)
        self.w = max(self.w, round(len(self.name) * CHAR_W + 14) if not self.kind else self.w)
        self.cx = 0
        self.acts = []      # các activation gốc
        self.open = []      # activation đang mở (ngăn xếp, có thể lồng)


class Act:
    def __init__(self, life, start, parent=None):
        self.life, self.start, self.parent = life, start, parent
        self.end = start + 12
        self.last = start
        self.model_id, self.shape_id = new_id(), new_id()
        self.children = []
        self.depth = parent.depth + 1 if parent else 0
        (parent.children if parent else life.acts).append(self)

    @property
    def x(self):
        return round(self.life.cx - ACT_W / 2 + 4 * self.depth)

    def touch(self, y):
        self.last = max(self.last, y)

    def close(self, y=None):
        self.end = max(self.start + 12, y if y is not None else self.last + 12)


def label_w(text):
    # chữ hoa/số rộng hơn chữ thường; ước lượng thiếu thì VP cắt nhãn thành "..."
    w = sum(8.2 if (c.isupper() or c.isdigit() or c in "_%{}") else CHAR_W for c in text)
    return round(w + 30)


class Frag:
    """Combined fragment (alt/opt/loop...) hoặc khung sd lồng."""
    def __init__(self, kind, parent, is_sd=False):
        self.kind, self.parent, self.is_sd = kind, parent, is_sd
        self.model_id, self.shape_id = new_id(), new_id()
        self.operands = []
        self.lifes = []          # tên lifeline có message bên trong (giữ thứ tự)
        self.self_labels = []    # (tên lifeline, nhãn) của message tự gọi bên trong
        self.depth_below = 0
        self.top = self.bottom = 0


class Operand:
    def __init__(self, guard):
        self.guard = guard
        self.model_id, self.shape_id, self.guard_id = new_id(), new_id(), new_id()
        self.msgs = []           # message nằm TRỰC TIẾP trong operand này
        self.top = 0


def flatten(items, frags, stack=None, operand=None):
    """Trải phẳng danh sách message có lồng khối thành chuỗi message + dấu mốc ("_mark")."""
    stack = stack or []
    out = []
    for it in items:
        if "fragment" in it or "frame" in it:
            sd = "frame" in it
            f = Frag(it["frame"] if sd else it["fragment"], stack[-1] if stack else None, sd)
            frags.append(f)
            ops = it.get("operands") or [{"guard": it.get("guard", ""), "messages": it.get("messages", [])}]
            out.append({"_mark": ("fs", f)})
            for k, op in enumerate(ops):
                o = Operand(op.get("guard", ""))
                f.operands.append(o)
                out.append({"_mark": ("os", f, o, k)})
                out += flatten(op.get("messages", []), frags, stack + [f], o)
            out.append({"_mark": ("fe", f)})
            d, g = 1, f.parent
            while g:
                g.depth_below = max(g.depth_below, d)
                d += 1
                g = g.parent
        else:
            m = dict(it)
            m["_operand"] = operand
            for f in stack:
                for n in (m["from"], m["to"]):
                    if n not in f.lifes:
                        f.lifes.append(n)
                if m["from"] == m["to"]:
                    f.self_labels.append((m["from"], m.get("text", "")))
            out.append(m)
    return out


def simulate(lifes, msgs):
    """Đi lần lượt các message, tính y, activation gửi/nhận cho mỗi message."""
    L = {l.name: l for l in lifes}
    stack = []          # ngăn xếp (lifeline, activation) theo luồng điều khiển
    y = FIRST_Y
    out = []

    def ensure_active(l, y):
        if not l.open:
            act = Act(l, y)
            l.open.append(act)
            stack.append((l, act))
        return l.open[-1]

    def unwind_to(l, y):
        """Luồng quay lại lifeline l: đóng các activation phía trên nó."""
        if not any(s[0] is l for s in stack):
            return
        while stack and stack[-1][0] is not l:
            ll, act = stack.pop()
            act.close(); ll.open.remove(act)

    for m in msgs:
        if "_mark" in m:
            mk = m["_mark"]
            if mk[0] == "fs":
                y += 6
                mk[1].top = y
                y += 44 if mk[1].is_sd else 58
            elif mk[0] == "os":
                f, o, k = mk[1], mk[2], mk[3]
                if k == 0:
                    o.top = f.top + 18
                else:
                    o.top = y - 14
                    y += 46
            else:
                mk[1].bottom = y - 14
                y += 30
            continue
        A, B = L[m["from"]], L[m["to"]]
        if A is B:                                      # tự gọi
            unwind_to(A, y)
            src = ensure_active(A, y)
            src.touch(y)
            inner = Act(A, y + 20, parent=src)
            inner.close(y + 32)
            src.touch(y + 32)
            out.append(dict(m=m, A=A, B=B, y=y, src=src, dst=inner, kind="self"))
            y += SELF_STEP
            continue
        if m.get("return"):
            unwind_to(A, y)
            src = ensure_active(A, y)
            src.touch(y)
            # đóng activation của A ngay tại message trả về
            if stack and stack[-1][1] is src:
                stack.pop()
            src.close(y); A.open.remove(src) if src in A.open else None
            dst = B.open[-1] if B.open else ensure_active(B, y)
            dst.touch(y)
            out.append(dict(m=m, A=A, B=B, y=y, src=src, dst=dst, kind="return"))
        else:
            unwind_to(A, y)
            src = ensure_active(A, y)
            src.touch(y)
            parent = B.open[-1] if B.open else None
            dst = Act(B, y, parent=parent)
            B.open.append(dst); stack.append((B, dst))
            out.append(dict(m=m, A=A, B=B, y=y, src=src, dst=dst, kind="call"))
        y += STEP
    for l, act in reversed(stack):
        act.close()
    return out, y


def place(lifes, events):
    """Khoảng cách lifeline: đủ chỗ cho nhãn message dài nhất giữa chúng."""
    idx = {id(l): i for i, l in enumerate(lifes)}
    x = MARGIN + lifes[0].w / 2
    for i, l in enumerate(lifes):
        if i:
            x += max(MIN_GAP, (lifes[i - 1].w + l.w) / 2 + 40)
        l.cx = x
    # nới rộng cho nhãn
    for e in sorted(events, key=lambda e: abs(idx[id(e["A"])] - idx[id(e["B"])])):
        i, j = sorted((idx[id(e["A"])], idx[id(e["B"])]))
        text = f'{e["m"].get("text", "")}'
        if i == j:          # tự gọi: nhãn nằm bên phải vòng lặp
            need = 40 + label_w(text)
            if j + 1 < len(lifes):
                gap = lifes[j + 1].cx - lifes[j].cx
                if gap < need:
                    for l in lifes[j + 1:]:
                        l.cx += need - gap
            continue
        need = label_w(text) + 30
        gap = lifes[j].cx - lifes[i].cx
        if gap < need:
            for l in lifes[j:]:
                l.cx += need - gap
    for l in lifes:
        l.cx = round(l.cx)


def act_shape(act, z):
    return (f'<Activation Background="{FILL}" ConnectToPoint="true" ConnectionPointType="2" CoverConnector="false" '
            f'Foreground="rgb(0, 0, 0)" Height="{act.end - act.start}" Id={a(act.shape_id)} '
            f'MetaModelElement={a(act.model_id)} Model={a(act.model_id)} ModelElementNameAlignment="9" '
            f'Name="Activation" PresentationOption="4" Selectable="true" Width="{ACT_W}" X="{act.x}" '
            f'Y="{act.start}" ZOrder="{z}">{FONT}{LINE}'
            f'<Caption Height="{act.end - act.start}" Side="Invisible" Visible="false" Width="{ACT_W}" X="0" Y="0"/>'
            f'{FILLC}</Activation>')


def act_model(act):
    kids = "".join(act_model(c) for c in act.children)
    return (f'<Activation Id={a(act.model_id)} Name="Activation" OverlappingExecutionOccurrence="false">'
            + (f'<Activations>{kids}</Activations>' if kids else "")
            + f'<MasterView><Activation Idref={a(act.shape_id)} Name="Activation"/></MasterView></Activation>')


def all_acts(l):
    def walk(act):
        yield act
        for c in act.children:
            yield from walk(c)
    for act in l.acts:
        yield from walk(act)


def generate(spec) -> str:
    lifes = [Life(d) for d in spec["lifelines"]]
    frags = []
    flat = flatten(spec["messages"], frags)
    events, last_y = simulate(lifes, flat)
    place(lifes, events)
    L = {l.name: l for l in lifes}
    for f in frags:            # khung chữ nhật của khối: bao các lifeline liên quan
        pad = 40 + 12 * f.depth_below
        names = f.lifes or [lifes[0].name]
        left = min(L[n].cx for n in names) - pad
        right = max(L[n].cx for n in names) + pad
        for n, t in f.self_labels:
            right = max(right, L[n].cx + 70 + label_w(t) + 12 * f.depth_below)
        if f.is_sd:     # tab tên khung dài: đặt hẳn bên trái lifeline đầu, nếu không activation che chữ
            left = min(left, min(L[n].cx for n in names) - (len(f.kind) * 7 + 30) - 16)
            left = max(left, 2)   # không để khung tràn ra ngoài mép trái (chữ tab bị cắt)
        head = max([label_w("[" + o.guard + "]") + 20 for o in f.operands] + [label_w(f.kind) + 30])
        right = max(right, left + head)
        f.x, f.w = round(left), round(right - left)
        f.cover = [l.name for l in lifes if f.x < l.cx < f.x + f.w]
    height = last_y + 40 - TOP
    frame_id = new_id()
    kinds = sorted({l.kind for l in lifes if l.kind and l.kind != "actor"})
    st_ids = {k: new_id() for k in kinds}

    life_models, shapes, msg_models, conns = [], [], [], []
    z = 500      # như VP: lifeline nằm TRÊN activation (ZOrder cao hơn), nếu không nét đứt vẽ xuyên thanh
    for l in lifes:
        if l.kind == "actor":
            life_models.append(
                f'<InteractionActor Id={a(l.model_id)} Name={a(l.name)}>'
                f'<MasterView><InteractionActor Idref={a(l.shape_id)} Name={a(l.name)}/></MasterView>'
                  f'</InteractionActor>')
            cap_w = round(len(l.name) * CHAR_W + 10)
            shapes.append(f'<InteractionActor Background="{FILL}" ConnectToPoint="true" ConnectionPointType="2" '
                          f'Foreground="rgb(0, 0, 0)" Height="{height}" Id={a(l.shape_id)} '
                          f'MetaModelElement={a(l.model_id)} Model={a(l.model_id)} Name={a(l.name)} '
                          f'ParentFrame={a(frame_id)} PresentationOption="4" Selectable="true" Width="{l.w}" '
                          f'X="{round(l.cx - l.w / 2)}" Y="{TOP}" ZOrder="{z}">{FONT}{LINE}'
                          f'<Caption Height="15" Side="None" Visible="true" Width="{cap_w}" '
                          f'X="{round(l.cx - cap_w / 2)}" Y="{TOP + 35}"/>{FILLC}</InteractionActor>')
            # Ghi chú: VP tự vẽ actor kèm thanh dọc chạy hết chiều cao (đúng như bản gốc), không phải lỗi.
            z += 1
            continue
        st = (f'<Stereotypes><Stereotype Idref={a(st_ids[l.kind])} Name={a(l.kind)}/></Stereotypes>'
              if l.kind else "")
        acts = "".join(act_model(x) for x in l.acts)
        life_models.append(
            f'<InteractionLifeLine Active="false" Class="false" Id={a(l.model_id)} MultiObject="false" '
            f'Multiplicity="Unspecified" Name={a(l.name)} Stopped="false">{st}'
            + (f'<Activations>{acts}</Activations>' if acts else "")
            + f'<MasterView><InteractionLifeLine Idref={a(l.shape_id)} Name={a(l.name)}/></MasterView>'
              f'</InteractionLifeLine>')
        x = round(l.cx - l.w / 2)
        cap_w = round(len(l.name) * CHAR_W + 10)
        cap = (f'<Caption Height="15" Side="South" Visible="true" Width="{cap_w}" X="{round(l.cx - cap_w / 2)}" '
               f'Y="{TOP + 35}"/>' if l.kind else
               f'<Caption Height="15" Side="None" Visible="true" Width="{l.w}" X="{x}" Y="{TOP}"/>')
        shapes.append(f'<InteractionLifeLine Background="{FILL}" ConnectToPoint="true" ConnectionPointType="2" '
                      f'CoverConnector="false" Foreground="rgb(0, 0, 0)" Height="{height}" Id={a(l.shape_id)} '
                      f'MetaModelElement={a(l.model_id)} Model={a(l.model_id)} ModelElementNameAlignment="1" '
                      f'Name={a(l.name)} OverrideAppearanceWithStereotypeIcon="true" ParentFrame={a(frame_id)} '
                      f'PresentationOption="4" Selectable="true" ShowClassifier="true" Width="{l.w}" X="{x}" '
                      f'Y="{TOP}" ZOrder="{z}">{FONT}{LINE}{cap}{FILLC}</InteractionLifeLine>')
        z += 1
    za = 1
    for f in frags:
        cap_w = round(len(f.kind) * 7 + (30 if f.is_sd else 16))
        clear = '<FillColor Color="rgba(122, 207, 245, 0.0)" Style="1" Transparency="100" Type="1"/>'
        tag = "Frame" if f.is_sd else "CombinedFragment"
        common = (f'Background="{FILL}" ConnectToPoint="true" ConnectionPointType="2" CoverConnector="false" '
                  f'Foreground="rgb(0, 0, 0)" ModelElementNameAlignment="9" PresentationOption="4" Selectable="true" ')
        if not f.is_sd:
            for k, o in enumerate(f.operands):
                bot = f.operands[k + 1].top if k + 1 < len(f.operands) else f.bottom
                shapes.append(f'<InteractionOperand {common}Height="{bot - o.top}" Id={a(o.shape_id)} '
                              f'MetaModelElement={a(o.model_id)} Model={a(o.model_id)} Name="Operand" '
                              f'Width="{f.w}" X="{f.x}" Y="{o.top}" ZOrder="{za}">{FONT}{LINE}'
                              f'<Caption Height="{bot - o.top}" Side="Invisible" Visible="false" Width="{f.w}" '
                              f'X="{f.x}" Y="{o.top}"/>{FILLC}</InteractionOperand>')
                za += 1
        f.xml = (f'<{tag} {common}Height="{f.bottom - f.top}" Id={a(f.shape_id)} MetaModelElement={a(f.model_id)} '
                 f'Model={a(f.model_id)} Name={a(f.kind if f.is_sd else "")} Width="{f.w}" X="{f.x}" Y="{f.top}" '
                 f'ZOrder="ZZ">{FONT}{LINE}<Caption Height="{18 if f.is_sd else 19}" Side="FreeMove" Visible="true" '
                 f'Width="{cap_w}" X="0" Y="0"/>{clear}</{tag}>')
    for l in lifes:
        if l.kind == "actor":
            continue        # actor không vẽ activation
        for act in all_acts(l):
            shapes.append(act_shape(act, za)); za += 1
    # như VP: operand < activation < khung sd < combined fragment < actor/lifeline (khung trong suốt)
    for f in sorted(frags, key=lambda f: not f.is_sd):
        shapes.append(f.xml.replace('ZOrder="ZZ"', f'ZOrder="{za}"')); za += 1
    z = 1000

    ret_of = {}     # message gọi -> message trả về tương ứng (để VP liên kết ReturnMessage)
    for n, e in enumerate(events, 1):
        m, A, B, y, src, dst = e["m"], e["A"], e["B"], e["y"], e["src"], e["dst"]
        mid, vid = new_id(), new_id()
        e["mid"] = mid
        text = m.get("text", "")
        if e["kind"] == "self":
            right = src.x + ACT_W
            pts = [(right, y), (right + 30, y), (right + 30, y + 20), (dst.x + ACT_W, y + 20)]
            cap_x, cap_y = right + 40, y
            mtype = "Recursive Message"
        else:
            rightward = A.cx < B.cx
            x1 = src.x + ACT_W if rightward else src.x
            x2 = dst.x if rightward else dst.x + ACT_W
            # actor không có activation riêng; VP vẽ thanh dọc rộng 8 ngay giữa actor -> nối từ mép thanh đó
            if A.kind == "actor":
                x1 = A.cx + (ACT_W // 2 if rightward else -ACT_W // 2)
            if B.kind == "actor":
                x2 = B.cx + (-ACT_W // 2 if rightward else ACT_W // 2)
            pts = [(x1, y), (x2, y)]
            cw = label_w(text)
            cap_x, cap_y = round((x1 + x2) / 2 - cw / 2), y - 18
            mtype = "Message"
        if e["kind"] == "return":
            # tìm lời gọi gần nhất B -> A chưa có return
            for prev in reversed(events[:n - 1]):
                if prev["kind"] == "call" and prev["A"] is B and prev["B"] is A and "ret" not in prev:
                    prev["ret"] = mid
                    break
        action = ('<ActionType><ActionTypeReturn Asynchronous="false" Id=' + a(new_id())
                  + ' Iteration="false" Name="Return"/></ActionType>') if e["kind"] == "return" else ""
        e["xml"] = (mid, vid, mtype, text, A, B, src, dst, action, n)
        if m.get("_operand") is not None:
            m["_operand"].msgs.append(mid)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        conns.append(f'<Message Background="rgb(0, 0, 0)" ConnectorLabelOrientation="4" ConnectorLineJumps="4" '
                     f'ConnectorStyle="Follow Diagram" Folded="false" Foreground="rgb(0, 0, 0)" '
                     f'From={a(A.shape_id)} To={a(B.shape_id)} FromConnectType="0" ToConnectType="0" '
                     f'FromPinType="1" ToPinType="1" FromShapeXDiff="0" FromShapeYDiff="0" ToShapeXDiff="0" '
                     f'ToShapeYDiff="0" UseFromShapeCenter="true" UseToShapeCenter="true" Id={a(vid)} '
                     f'MetaModelElement={a(mid)} Model={a(mid)} ModelElementNameAlignment="9" Name={a(text)} '
                     f'PaintThroughLabel="2" Selectable="true" ShowConnectorName="2" '
                     f'X="{min(xs) - 50}" Y="{min(ys) - 50}" Width="{max(xs) - min(xs) + 100}" '
                     f'Height="{max(ys) - min(ys) + 100}" ZOrder="{z}">{FONT}{LINE}'
                     f'<Caption Height="15" Side="None" Visible="true" Width="{label_w(text)}" '
                     f'X="{cap_x}" Y="{cap_y}"/><Points>'
                     + "".join(f'<Point X="{px}.0" Y="{py}.0"/>' for px, py in pts) + '</Points></Message>')
        z += 1
    # Quy tắc người dùng: mọi lời gọi (trừ tự gọi, gọi tới actor) phải có message trả về nét đứt
    for n_, e in enumerate(events, 1):
        if e["kind"] == "call" and "ret" not in e and e["B"].kind != "actor" and not e["m"].get("async"):
            print(f'[sequence] cảnh báo: message {n_} "{e["m"].get("text", "")}" '
                  f'({e["A"].name} -> {e["B"].name}) chưa có trả về')
    for e in events:
        mid, vid, mtype, text, A, B, src, dst, action, n = e["xml"]
        ret = f' ReturnMessage={a(e["ret"])}' if "ret" in e else ""
        fa = f' FromActivation={a(src.model_id)}' if A.kind != "actor" else ""
        ta = f' ToActivation={a(dst.model_id)}' if B.kind != "actor" else ""
        msg_models.append(
            f'<Message Asynchronous="{"true" if e["m"].get("async") else "false"}" DurationHeight="30" EndRelationshipFromMetaModelElement={a(A.model_id)} '
            f'EndRelationshipToMetaModelElement={a(B.model_id)}{fa} Id={a(mid)} '
            f'Name={a(text)} SequenceNumber="{n}"{ta} Type="{mtype}"{ret}>{action}'
            f'<FromEnd><MessageEnd EndModelElement={a(A.model_id)} Id={a(new_id())}/></FromEnd>'
            f'<ToEnd><MessageEnd EndModelElement={a(B.model_id)} Id={a(new_id())}/></ToEnd>'
            f'<MasterView><Message Idref={a(vid)} Name={a(text)}/></MasterView></Message>')

    for f in frags:
        if f.is_sd:
            life_models.append(f'<Frame BaseY="40" Id={a(f.model_id)} Name={a(f.kind)} Type="sd">'
                               f'<MasterView><Frame Idref={a(f.shape_id)} Name={a(f.kind)}/></MasterView></Frame>')
            continue
        cov = "".join(f'<{"InteractionActor" if L[n].kind == "actor" else "InteractionLifeLine"} '
                      f'Idref={a(L[n].model_id)} Name={a(n)}/>' for n in f.cover)
        ops = "".join(
            f'<InteractionOperand Id={a(o.model_id)} Name="">'
            + ('<Messages>' + "".join(f'<Message Idref={a(i)} Name=""/>' for i in o.msgs) + '</Messages>'
               if o.msgs else "")
            + f'<Guard><InteractionConstraint Constraint={a(o.guard)} Id={a(o.guard_id)} Name=""/></Guard>'
              f'<MasterView><InteractionOperand Idref={a(o.shape_id)} Name="Operand"/></MasterView>'
              f'</InteractionOperand>' for o in f.operands)
        life_models.append(f'<CombinedFragment Id={a(f.model_id)} Name="" OperatorKind={a(f.kind)}>'
                           f'<CoveredLifeLines>{cov}</CoveredLifeLines>'
                           f'<MasterView><CombinedFragment Idref={a(f.shape_id)} Name=""/></MasterView>'
                           f'<ModelChildren>{ops}</ModelChildren></CombinedFragment>')

    name = spec.get("name", "Sequence Diagram")
    width = max([l.cx + l.w / 2 for l in lifes] + [f.x + f.w for f in frags]) + MARGIN + 150
    st_models = "".join(f'<Stereotype BaseType="InteractionLifeLine" IconPath="" Id={a(i)} Name={a(k)}/>'
                        for k, i in st_ids.items())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Project Author="vpgen" ExporterVersion="16.1.1" Name={a(name)} UmlVersion="2.x" Xml_structure="simple">'
        '<Models>'
        f'<ModelRelationshipContainer Id={a(new_id())} Name="relationships"><ModelChildren>'
        + "".join(msg_models) + '</ModelChildren></ModelRelationshipContainer>'
        f'<Frame BaseY="40" Id={a(frame_id)} Name={a(name)} Type="sd"><ModelChildren>'
        + "".join(life_models) + '</ModelChildren></Frame>' + st_models + '</Models>'
        f'<Diagrams><InteractionDiagram Id={a(new_id())} Name={a(name)} AutoExtendActivations="false" '
        f'ConnectorStyle="1" DiagramBackground="rgb(255, 255, 255)" ShowActivations="true" '
        f'ShowDiagramFrame="false" ShowMessageName="true" ShowSequenceNumbers="true" SequenceNumbering="1" '
        f'SequenceNumberHandling="0" ShowStereotypes="true" Width="{round(width)}" '
        f'Height="{last_y + 80}" X="0" Y="0" ZoomRatio="1.0" _rootFrame={a(frame_id)}>'
        '<Shapes>' + "".join(shapes) + '</Shapes><Connectors>' + "".join(conns) + '</Connectors>'
        '</InteractionDiagram></Diagrams></Project>\n'
    )


def main(spec_file, out_dir="out", *image_types):
    spec = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    write_and_build(generate(spec), spec, spec_file, out_dir, list(image_types) or None)


if __name__ == "__main__":
    main(*sys.argv[1:])
