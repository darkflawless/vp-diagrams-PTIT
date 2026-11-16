"""Sinh XML ERD (sơ đồ CSDL màu cam) cho Visual Paradigm từ file mô tả JSON, tự bố cục.

Cách dùng:  python vpgen/build.py examples/dat_phong.json out/

  "tables": [
    {"name": "BookingTBL", "pos": [cột, hàng],          # pos tuỳ chọn
     "columns": [
        "id integer(10) pk",                            # chuỗi: tên kiểu [pk] [notnull] [unique]
        "Time time(7)",
        {"name": "paid", "type": "integer(10)", "nullable": false}   # hoặc dạng đầy đủ
     ]}
  ]
  "relations": [
    {"from": "BookingTBL", "to": "RoomBookedTBL",       # from = bảng CHA (được tham chiếu)
     "fk": "Bookingid",                                 # cột khoá ngoại ở bảng con (chưa có thì tự thêm)
     "from_mult": "1", "to_mult": "0..*",               # mặc định 1 -> 0..*
     "identifying": false}                              # true = nét liền, false = nét đứt
  ]
Cột không ghi gì: cho phép NULL (hiện chữ N), trừ khoá chính.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FONT, LINE, STYLE, a, fill_xml, new_id  # noqa: E402
from classdiag import layout, route, conn_box, points, label_at  # noqa: E402
from router import route_all  # noqa: E402

ERD_FILL = STYLE.get("erd_fill", "rgb(245, 182, 122)")

# VP KHÔNG đọc tên kiểu trong Type="...", mà đọc mã Type_internalValue. Bảng mã dò bằng cách cho VP
# vẽ từng mã rồi đọc lại SVG (xem NOTES.md). Mã 0, 49, >= 63 làm hỏng bảng — không dùng.
TYPE_CODES = {
    "bit": 1, "bool": 1, "boolean": 1,
    "float": 4, "real": 5, "double": 6,
    "tinyint": 7, "smallint": 8, "int": 9, "integer": 9, "bigint": 16,
    "decimal": 11, "numeric": 15, "number": 15, "money": 11,
    "date": 17, "time": 19, "datetime": 20, "timestamp": 20,
    "blob": 23, "varchar": 27, "nvarchar": 27, "string": 27, "varchar2": 27,
    "char": 31, "nchar": 31, "text": 34, "clob": 34, "longtext": 34,
    "binary": 39, "varbinary": 40,
}
NO_LENGTH = {"bit", "bool", "boolean", "blob", "text", "clob", "longtext"}
CHAR_W = 6.6
ROW_H = 18
HEAD_H = 20


def parse_type(t):
    m = re.match(r"^\s*([A-Za-z_ ]+?)\s*(?:\((\d+)(?:\s*,\s*(\d+))?\))?\s*$", t or "")
    if not m:
        return t, 0, 0
    return m.group(1), int(m.group(2) or 0), int(m.group(3) or 0)


def parse_col(c):
    if isinstance(c, dict):
        d = dict(c)
    else:
        parts = c.split()
        d = {"name": parts[0], "type": parts[1] if len(parts) > 1 and parts[1].lower() not in
             ("pk", "notnull", "nn", "unique") else "integer(10)"}
        flags = {p.lower() for p in parts[1:]}
        d["pk"] = "pk" in flags
        if flags & {"notnull", "nn"}:
            d["nullable"] = False
        d["unique"] = "unique" in flags
    d.setdefault("pk", False)
    d.setdefault("nullable", not d["pk"])
    d.setdefault("unique", d["pk"])
    d["base"], d["length"], d["scale"] = parse_type(d.get("type", "integer(10)"))
    d["id"] = new_id()
    d["fk"] = None
    return d


class Table:
    def __init__(self, d):
        self.name = d["name"]
        self.pos = d.get("pos")
        self.cols = [parse_col(c) for c in d.get("columns", [])]
        self.model_id, self.shape_id = new_id(), new_id()
        self.x = self.y = 0
        self.from_rels, self.to_rels = [], []

    def size(self):
        name_w = max([len(c["name"]) for c in self.cols] + [4]) * CHAR_W
        type_w = max([len(c.get("type", "")) for c in self.cols] + [4]) * CHAR_W
        self.w = round(max(len(self.name) * CHAR_W + 30, 30 + name_w + 20 + type_w + 40))
        self.h = round(HEAD_H + max(1, len(self.cols)) * ROW_H + 10)

    @property
    def cx(self): return self.x + self.w / 2

    @property
    def cy(self): return self.y + self.h / 2

    def pk(self):
        return next((c for c in self.cols if c["pk"]), None)


def col_xml(c):
    fk = ""
    if c["fk"]:
        fk_id, ref_col = c["fk"]
        fk = (f'<ForeignKeyConstraints><DBForeignKeyConstraint ForeignKey={a(fk_id)} Id={a(new_id())} '
              f'Name="" RefColumn={a(ref_col)}/></ForeignKeyConstraints>')
    base = c["base"].strip().lower()
    code = TYPE_CODES.get(base)
    if code is None:
        print(f'  ! Kiểu "{c["base"]}" (cột {c["name"]}) chưa có trong TYPE_CODES — dùng varchar.')
        code = 27
    length = 0 if base in NO_LENGTH else c["length"]
    return (f'<DBColumn Id={a(c["id"])} Name={a(c["name"])} Type={a(base)} Type_internalValue="{code}" '
            f'Length="{length}" '
            f'Scale="{c["scale"]}" PrimaryKey="{str(c["pk"]).lower()}" Nullable="{str(c["nullable"]).lower()}" '
            f'Unique="{str(c["unique"]).lower()}" Index="{str(c["pk"]).lower()}" Generated="Unspecified" '
            f'IdGenerator="native" IdentityIncrement="-1" IdentitySeed="-1" SequenceAllocationSize="-1" '
            f'SyncToAttribute="Yes" SyncType="Not Sync">{fk}</DBColumn>')


def generate(spec) -> str:
    tables = [Table(d) for d in spec["tables"]]
    T = {t.name: t for t in tables}
    rels = []
    for r in spec.get("relations", []):
        P, C = T[r["from"]], T[r["to"]]
        pk = P.pk()
        if pk is None:
            raise SystemExit(f'Bảng {P.name} chưa có khoá chính (thêm "pk" vào một cột).')
        fk_name = r.get("fk") or f'{P.name}{pk["name"]}'
        col = next((c for c in C.cols if c["name"] == fk_name), None)
        if col is None:     # tự thêm cột khoá ngoại, cùng kiểu với khoá chính của bảng cha
            col = parse_col({"name": fk_name, "type": pk.get("type", "integer(10)"), "nullable": True})
            C.cols.insert(0, col)
        rid = new_id()
        col["fk"] = (rid, pk["id"])
        rels.append(dict(r, id=rid, view=new_id(), P=P, C=C))
        P.from_rels.append(rid); C.to_rels.append(rid)
    for t in tables:
        t.size()

    # Bố cục: dùng lại thuật toán lưới của Class diagram
    layout(tables, [{"from": r["from"], "to": r["to"], "type": "association"} for r in rels])

    models, shapes, conns, fk_models = [], [], [], []
    for z, t in enumerate(tables, 1):
        frm = "".join(f'<DBForeignKey Idref={a(i)} Name=""/>' for i in t.from_rels)
        to = "".join(f'<DBForeignKey Idref={a(i)} Name=""/>' for i in t.to_rels)
        models.append(
            f'<DBTable DataModel="Physical" Id={a(t.model_id)} Name={a(t.name)} OrmSyncState="Not Sync" '
            f'PrimaryKeyClustered="Unspecified" SyncType="Not Sync" Temporal="false" Type="0" Unlogged="false">'
            f'<ModelChildren>{"".join(col_xml(c) for c in t.cols)}</ModelChildren>'
            + (f'<FromSimpleRelationships>{frm}</FromSimpleRelationships>' if frm else "")
            + (f'<ToSimpleRelationships>{to}</ToSimpleRelationships>' if to else "")
            + f'<MasterView><DBTable Idref={a(t.shape_id)} Name={a(t.name)}/></MasterView></DBTable>')
        shapes.append(
            f'<DBTable Background="{ERD_FILL}" ColSortType="0" ConnectToPoint="true" ConnectionPointType="2" '
            f'CoverConnector="false" CreatorDiagramType="ERDiagram" Foreground="rgb(0, 0, 0)" Height="{t.h}" '
            f'Id={a(t.shape_id)} MetaModelElement={a(t.model_id)} Model={a(t.model_id)} '
            f'ModelElementNameAlignment="9" Name={a(t.name)} PresentationOption="4" Selectable="true" '
            f'ShowColumnStereotypes="0" ShowColumnsMode="0" Width="{t.w}" X="{t.x}" Y="{t.y}" ZOrder="{z}">'
            f'{FONT}{LINE}<Caption Height="15" Side="FreeMove" Visible="true" Width="{t.w}" X="0" Y="0"/>'
            f'{fill_xml(ERD_FILL)}<CompartmentFont Value="none"/></DBTable>')

    ports = {}
    all_pts = route_all([(r["P"], r["C"]) for r in rels], tables,
                        fallback=lambda A, B: route(A, B, ports))
    for z, r in enumerate(rels, 1000):
        P, C = r["P"], r["C"]
        pts = all_pts[z - 1000]
        lx, ly = label_at(pts)
        fk_models.append(
            f'<DBForeignKey DataModel="Physical" From={a(P.model_id)} To={a(C.model_id)} '
            f'FromMultiplicity={a(r.get("from_mult", "1"))} ToMultiplicity={a(r.get("to_mult", "0..*"))} '
            f'Id={a(r["id"])} Identifying="{str(r.get("identifying", False)).lower()}" Name={a(r.get("label", ""))} '
            f'OnDelete="" OnUpdate="" Subtype="false" SyncToAssociation="Yes" SyncType="Not Sync">'
            f'<MasterView><DBForeignKey Idref={a(r["view"])} Name=""/></MasterView></DBForeignKey>')
        conns.append(
            f'<DBForeignKey Background="rgb(255, 255, 255)" ConnectorLabelOrientation="4" ConnectorLineJumps="1" '
            f'ConnectorStyle="Follow Diagram" CreatorDiagramType="ERDiagram" Foreground="rgb(0, 0, 0)" '
            f'From={a(P.shape_id)} To={a(C.shape_id)} FromConnectType="0" ToConnectType="0" FromPinType="1" '
            f'ToPinType="1" FromShapeXDiff="0" FromShapeYDiff="0" ToShapeXDiff="0" ToShapeYDiff="0" '
            f'HasFromLabel="false" HasToLabel="false" Id={a(r["view"])} MetaModelElement={a(r["id"])} '
            f'Model={a(r["id"])} ModelElementNameAlignment="9" Name={a(r.get("label", ""))} PaintThroughLabel="2" '
            f'Selectable="true" ShowConnectorName="2" UseFromShapeCenter="true" UseToShapeCenter="true" '
            f'{conn_box(pts)} ZOrder="{z}">{FONT}{LINE}'
            f'<Caption Height="0" Side="None" Visible="true" Width="20" X="{lx}" Y="{ly}"/>{points(pts)}'
            f'</DBForeignKey>')

    name = spec.get("name", "Entity Relationship Diagram")
    right = max(t.x + t.w for t in tables) + 60
    bottom = max(t.y + t.h for t in tables) + 60
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Project Author="vpgen" ExporterVersion="16.1.1" Name={a(name)} UmlVersion="2.x" Xml_structure="simple">'
        '<Models>'
        f'<ModelRelationshipContainer Id={a(new_id())} Name="relationships"><ModelChildren>'
        f'<ModelRelationshipContainer Id={a(new_id())} Name="DBForeignKey"><ModelChildren>'
        + "".join(fk_models) + '</ModelChildren></ModelRelationshipContainer>'
        '</ModelChildren></ModelRelationshipContainer>' + "".join(models) + '</Models>'
        f'<Diagrams><ERDiagram Id={a(new_id())} Name={a(name)} ConnectorStyle="1" DataModel="2" '
        f'ConnectorLineJumps="0" ConnectorLineJumpsSize="0" '
        f'DiagramBackground="rgb(255, 255, 255)" ForeignKeyArrowHeadSize="3" ShowSchemaName="true" '
        f'ShowStereotypes="true" Width="{right}" Height="{bottom}" X="0" Y="0" ZoomRatio="1.0" '
        f'_alignColumnProperties="true" _columnConstraintsDisplayOption="2" _pointForeignKeyEndToColumn="false" '
        f'_showColumnTypes="true" _showDBTableColumnsMode="1" _showExtraColumnProperties="true">'
        '<Shapes>' + "".join(shapes) + '</Shapes><Connectors>' + "".join(conns) + '</Connectors>'
        '</ERDiagram></Diagrams></Project>\n'
    )
