"""Bộ định tuyến đường nối vuông góc (orthogonal) cho Class / ERD.

Luật (theo yêu cầu người dùng, áp dụng cho MỌI sơ đồ có đường nối giữa các hình):
  1. Đường nối KHÔNG được cắt vào trong hình (class/bảng nào cũng vậy, kể cả hai đầu của chính nó).
  2. Hai đường nối KHÔNG được trùng nhau (chạy chồng lên cùng một đoạn), không dùng chung cổng.
  3. Được phép cắt nhau vuông góc — VP vẽ chỗ cắt thành "cầu nhảy" (line jump), như mẫu người dùng.
     Hai đường không được rẽ tại cùng một điểm.

Cách làm: lưới bước STEP px phủ toàn sơ đồ; ô nằm trong hình (nới thêm PAD) bị chặn. Mỗi đường
nối tìm bằng A* trên trạng thái (ô, hướng): chi phí = độ dài + phạt góc rẽ + phạt cắt ngang đường
khác + phạt chạy sát song song. Ô đã có đường đi theo cùng phương thì cấm (chống trùng), ô có góc rẽ
hay cổng của đường khác thì cấm hoàn toàn. Điểm đầu/cuối là "cổng" trên cạnh hình (cách mép PAD),
mỗi cổng cách nhau >= 2 ô; từ cổng kẻ thêm một đoạn ngắn vuông góc vào sát mép hình (lệch 1px như VP).
"""
import heapq
import math

STEP = 10        # bước lưới (px)
PAD = 20         # khoảng trống quanh hình mà đường khác không được đi vào (đủ chỗ cho thoi/mũi tên)
BEND = 8         # phạt mỗi góc rẽ (tính theo số ô)
CROSS = 5        # phạt mỗi lần cắt ngang đường khác
NEAR = 0.6       # phạt đi sát song song (cách 1 ô) với đường khác
PORT_OFF = 0.08  # phạt cổng lệch khỏi giữa cạnh (mỗi ô)

DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]      # 0 phải, 1 xuống, 2 trái, 3 lên
FREE, H, V, X = 0, 1, 2, 3                     # trạng thái ô: trống / đường ngang / dọc / góc-cổng


class Router:
    def __init__(self, shapes):
        """shapes: các object có x, y, w, h."""
        self.shapes = shapes
        x0 = min(s.x for s in shapes) - 6 * STEP
        y0 = min(s.y for s in shapes) - 6 * STEP
        x1 = max(s.x + s.w for s in shapes) + 6 * STEP
        y1 = max(s.y + s.h for s in shapes) + 6 * STEP
        self.X0, self.Y0 = x0, y0
        self.W = int((x1 - x0) // STEP) + 1
        self.H = int((y1 - y0) // STEP) + 1
        self.blocked = bytearray(self.W * self.H)
        self.use = bytearray(self.W * self.H)
        for s in shapes:
            i0, i1, j0, j1 = self._span(s)
            for j in range(max(j0, 0), min(j1, self.H - 1) + 1):
                for i in range(max(i0, 0), min(i1, self.W - 1) + 1):
                    self.blocked[j * self.W + i] = 1
        self.used_ports = set()

    # ---- lưới ----
    def gx(self, i): return self.X0 + i * STEP
    def gy(self, j): return self.Y0 + j * STEP

    def _span(self, s):
        """Chỉ số ô bị hình s (đã nới PAD) che."""
        i0 = math.ceil((s.x - PAD - self.X0) / STEP)
        i1 = math.floor((s.x + s.w + PAD - self.X0) / STEP)
        j0 = math.ceil((s.y - PAD - self.Y0) / STEP)
        j1 = math.floor((s.y + s.h + PAD - self.Y0) / STEP)
        return i0, i1, j0, j1

    def ports(self, s):
        """Cổng trên 4 cạnh: (i, j, hướng-đi-ra, toạ độ điểm trên mép hình, phạt lệch tâm)."""
        i0, i1, j0, j1 = self._span(s)
        out = []
        ia = math.ceil((s.x + 8 - self.X0) / STEP); ib = math.floor((s.x + s.w - 8 - self.X0) / STEP)
        ja = math.ceil((s.y + 8 - self.Y0) / STEP); jb = math.floor((s.y + s.h - 8 - self.Y0) / STEP)
        cx, cy = s.x + s.w / 2, s.y + s.h / 2
        for i in range(ia, ib + 1):
            off = abs(self.gx(i) - cx) / STEP * PORT_OFF
            out.append((i, j0 - 1, 3, (self.gx(i), s.y - 1), off))           # trên
            out.append((i, j1 + 1, 1, (self.gx(i), s.y + s.h + 1), off))     # dưới
        for j in range(ja, jb + 1):
            off = abs(self.gy(j) - cy) / STEP * PORT_OFF
            out.append((i0 - 1, j, 2, (s.x - 1, self.gy(j)), off))           # trái
            out.append((i1 + 1, j, 0, (s.x + s.w + 1, self.gy(j)), off))     # phải
        return [p for p in out if self._port_ok(p[0], p[1], p[2])]

    def _port_ok(self, i, j, d):
        if not (0 <= i < self.W and 0 <= j < self.H):
            return False
        k = j * self.W + i
        if self.blocked[k] or self.use[k] != FREE:
            return False
        # cổng cách cổng đã dùng ít nhất 2 ô dọc theo cạnh
        along = (0, 1) if d in (0, 2) else (1, 0)
        for t in (-1, 1):
            if (i + along[0] * t, j + along[1] * t) in self.used_ports:
                return False
        return (i, j) not in self.used_ports

    # ---- tìm đường ----
    def route(self, A, B):
        """Trả về danh sách điểm (x, y) từ mép A tới mép B, hoặc None nếu không tìm được."""
        W = self.W
        src = self.ports(A)
        dst = {(p[0], p[1]): p for p in self.ports(B)}
        if not src or not dst:
            return None
        bi0, bi1, bj0, bj1 = self._span(B)

        def hfun(i, j):
            dx = bi0 - i if i < bi0 else (i - bi1 if i > bi1 else 0)
            dy = bj0 - j if j < bj0 else (j - bj1 if j > bj1 else 0)
            return dx + dy

        INF = float("inf")
        best = {}
        prev = {}
        heap = []
        for i, j, d, edge, off in src:
            if (i, j) in dst:         # hai hình sát nhau — bỏ qua cổng trùng
                continue
            st = (i, j, d)
            g = off
            if g < best.get(st, INF):
                best[st] = g; prev[st] = ("SRC", edge)
                heapq.heappush(heap, (g + hfun(i, j), g, st))
        goal = None
        while heap:
            f, g, st = heapq.heappop(heap)
            if st == "GOAL":
                goal = True
                break
            if g > best.get(st, INF):
                continue
            i, j, d = st
            if (i, j) in dst:
                pi, pj, pd, edge, off = dst[(i, j)]
                inward = (pd + 2) % 4
                g2 = g + off + (0 if d == inward else BEND)
                # rẽ tại cổng đích: ô phải trống (không có đường khác đi qua)
                if d == inward or self.use[j * W + i] == FREE:
                    if g2 < best.get("GOAL", INF):
                        best["GOAL"] = g2; prev["GOAL"] = (st, edge)
                        heapq.heappush(heap, (g2, g2, "GOAL"))
            for nd in (d, (d + 1) % 4, (d + 3) % 4):
                turn = nd != d
                if turn and self.use[j * W + i] != FREE:
                    continue        # không rẽ tại ô đã có đường khác
                dx, dy = DIRS[nd]
                ni, nj = i + dx, j + dy
                if not (0 <= ni < W and 0 <= nj < self.H):
                    continue
                k = nj * W + ni
                if self.blocked[k] and (ni, nj) not in dst:
                    continue
                u = self.use[k]
                horiz = nd in (0, 2)
                if u == X or (u == H and horiz) or (u == V and not horiz):
                    continue        # trùng đường / đè lên góc hoặc cổng của đường khác
                if (ni, nj) in self.used_ports:
                    continue
                c = 1 + (BEND if turn else 0) + (CROSS if u != FREE else 0)
                # đi sát song song đường khác
                for sx, sy in ((dy, dx), (-dy, -dx)):
                    ai, aj = ni + sx, nj + sy
                    if 0 <= ai < W and 0 <= aj < self.H:
                        ua = self.use[aj * W + ai]
                        if (ua == H and horiz) or (ua == V and not horiz):
                            c += NEAR
                ns = (ni, nj, nd)
                g2 = g + c
                if g2 < best.get(ns, INF):
                    best[ns] = g2; prev[ns] = (st, None)
                    heapq.heappush(heap, (g2 + hfun(ni, nj), g2, ns))
        if not goal:
            return None

        # Lần ngược đường đi
        st, end_edge = prev["GOAL"]
        cells = []
        while True:
            cells.append(st)
            p, info = prev[st]
            if p == "SRC":
                start_edge = info
                break
            st = p
        cells.reverse()
        self._commit(cells)
        pts = [start_edge] + [(self.gx(i), self.gy(j)) for i, j, _ in cells] + [end_edge]
        return simplify(pts)

    def _commit(self, cells):
        W = self.W
        n = len(cells)
        for idx, (i, j, d) in enumerate(cells):
            k = j * W + i
            nxt = cells[idx + 1][2] if idx + 1 < n else d
            if idx == 0 or idx == n - 1 or nxt != d:
                self.use[k] = X                         # cổng hoặc góc rẽ
            else:
                cur = H if d in (0, 2) else V
                if self.use[k] == FREE:
                    self.use[k] = cur
                elif self.use[k] != cur:
                    self.use[k] = X                     # điểm giao cắt: không cho đường thứ ba qua
        for i, j, _ in (cells[0], cells[-1]):
            self.used_ports.add((i, j))


def simplify(pts):
    """Bỏ điểm thẳng hàng, làm tròn về số nguyên."""
    pts = [(round(x), round(y)) for x, y in pts]
    out = [pts[0]]
    for p in pts[1:]:
        if p == out[-1]:
            continue
        if len(out) >= 2:
            (ax, ay), (bx, by) = out[-2], out[-1]
            if (ax == bx == p[0]) or (ay == by == p[1]):
                out[-1] = p
                continue
        out.append(p)
    return out


def route_all(pairs, shapes, fallback=None):
    """pairs: [(A, B)] theo thứ tự quan hệ. Đường ngắn được định tuyến trước (đi thẳng, ít cắt),
    đường dài đi sau để né. Trả về danh sách điểm theo đúng thứ tự `pairs`."""
    r = Router(shapes)
    order = sorted(range(len(pairs)),
                   key=lambda k: abs(pairs[k][0].x + pairs[k][0].w / 2 - pairs[k][1].x - pairs[k][1].w / 2)
                   + abs(pairs[k][0].y + pairs[k][0].h / 2 - pairs[k][1].y - pairs[k][1].h / 2))
    res = [None] * len(pairs)
    for k in order:
        A, B = pairs[k]
        res[k] = r.route(A, B)
        if res[k] is None:
            print(f"[router] không tìm được đường né cho {getattr(A, 'name', A)} -> "
                  f"{getattr(B, 'name', B)}, dùng đường thẳng thay thế")
            res[k] = fallback(A, B) if fallback else [(A.x, A.y), (B.x, B.y)]
    return res
