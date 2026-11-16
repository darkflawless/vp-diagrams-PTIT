# Ghi chú kỹ thuật — XML của Visual Paradigm (đã kiểm chứng trên VP CE 18.1)

## Chạy VP từ dòng lệnh
- VP ở `C:\Program Files\Visual Paradigm CE 18.1` (đổi bằng biến môi trường `VP_HOME`).
- Gọi thẳng `jre\bin\java.exe` của VP với classpath như trong `scripts\*.bat`, cwd = `bin`,
  `-Djava.awt.headless=true`. Lớp: `com.vp.cmd.ImportXML`, `com.vp.cmd.ExportDiagramImage`.
  (Các file .bat bị môi trường chặn khi gọi qua cmd — vp.py tự ghép lệnh java.)
- `-diagram "*"`: dấu `*` PHẢI còn ngoặc kép trên dòng lệnh, nếu không Java tự bung wildcard
  → "Diagram not found". vp.py ghép dòng lệnh tay vì lý do này.
- `-type png` cho nền TRONG SUỐT (dán Word trông xám). Dùng `png_with_background` hoặc `svg`.
- Ảnh xuất được VP tự cắt theo vùng nội dung; Width/Height của diagram không ảnh hưởng.
- PNG xuất ở tỉ lệ 1:1 (font 11px) → phóng to bị mờ. SVG là vector, giữ được logo và chữ Việt.
- Import chấp nhận XML tối giản (không cần hàng trăm thuộc tính Pm*/Quality*); id tự đặt dạng
  `GEN0000000000001` (16 ký tự) dùng được.

## Bẫy đã gặp (mất nhiều thời gian nhất)
1. **Khung connector bị clip**: X/Y/Width/Height của mọi connector phải bao quanh đường nối và
   nới thêm 50px mỗi phía (VP làm vậy). Khung sát đường → VP cắt nét vẽ → hình thoi/mũi tên bẹp.
2. **ZOrder**: Class: connector phải có ZOrder cao hơn class. Sequence: lifeline phải cao hơn
   activation (như VP), ngược lại thì nét đứt của lifeline vẽ xuyên qua thanh activation.
3. **Background của connector** = màu tô đầu mũi tên/hình thoi. Đặt trắng cho tam giác kế thừa
   và thoi aggregation; composition VP tự tô đen.
4. Điểm đầu/cuối connector trong VP nằm lệch ra ngoài mép hình 1px.
5. Thiếu `UseFromShapeCenter/UseToShapeCenter="true"` thì VP có thể tự tính lại đầu nối.
6. Caption của use case: VP bỏ qua Caption Width → tự chèn "\n" vào tên để xuống dòng.

## Chiều From/To
- Use case Include: From = use case gốc, To = được include (mũi tên ở To).
- Use case Extend: From = use case GỐC (đầu mũi tên), To = use case mở rộng.
- Class Generalization / Realization: From = cha / interface, To = con.
- Association: `AggregationKind` Shared (thoi trắng) / Composited (thoi đen) đặt ở AssociationEnd
  của bên TỔNG THỂ; bội số ở `Multiplicity` của AssociationEnd (không phải `Name` = role).

## Sequence
- Model: `Frame` (Type="sd") chứa các `InteractionLifeLine` trong ModelChildren; diagram có
  `_rootFrame` = id frame; shape lifeline có `ParentFrame`.
- Biểu tượng boundary/control/entity = Stereotype (BaseType="InteractionLifeLine") tên đó.
- Activation lồng trong model lifeline (`Activations`), activation con lồng trong cha; shape
  activation rộng 8, X = tâm lifeline − 4 (+4 mỗi cấp lồng).
- Message: `Type="Message"` hoặc `"Recursive Message"` (4 điểm), trả về có
  `ActionType/ActionTypeReturn`; lời gọi trỏ tới trả về qua `ReturnMessage`; cần FromActivation/ToActivation.
- Actor (đã kiểm chứng bằng mẫu thật): model `InteractionActor` trong ModelChildren của Frame, KHÔNG có
  Activations; shape `InteractionActor` rộng 60, Caption Side="None" Y = đỉnh + 35. VP tự vẽ thanh dọc
  rộng 8 chạy hết chiều cao dưới actor — đúng như VP, không phải lỗi. Message tới actor không có
  ToActivation (từ actor thì không có FromActivation); đầu mũi tên nối vào mép thanh (tâm ± 4).

## ERD
- Model: `DBTable` (DataModel="Physical") chứa `DBColumn` trong ModelChildren; quan hệ `DBForeignKey`
  nằm trong ModelRelationshipContainer "DBForeignKey" con của "relationships".
- `DBForeignKey` From = bảng CHA (được tham chiếu), To = bảng con; `FromMultiplicity`/`ToMultiplicity`
  quyết định ký hiệu chân chim; `Identifying="true"` nét liền, "false" nét đứt.
- Cột khoá ngoại ở bảng con: `<ForeignKeyConstraints><DBForeignKeyConstraint ForeignKey=<id quan hệ>
  RefColumn=<id cột khoá chính bảng cha>/>` → VP tự in nghiêng + icon khoá ngoại.
- Bảng: `FromSimpleRelationships` (bảng cha) / `ToSimpleRelationships` (bảng con) trỏ tới id quan hệ.
- **Kiểu cột**: VP BỎ QUA thuộc tính `Type="..."`, chỉ đọc `Type_internalValue` (mã số). Dò bằng cách
  sinh 70 bảng, bảng i có cột mang mã i, xuất SVG rồi đọc thẻ <text>. Một bảng có mã hỏng (0, 49,
  >= 63) làm bảng đó trống trơn — vì vậy phải dò mỗi mã một bảng. Kết quả (CSDL chung):
  1-3 bit, 4 float, 5 real, 6 double, 7 tinyint, 8 smallint, 9-10 integer, 11-14 decimal,
  15 numeric, 16 bigint, 17-18 date, 19 time, 20-22 timestamp, 23-26 blob, 27-30 varchar,
  31-33 char, 34-38 clob, 39 binary, 40-41 varbinary. Bảng ánh xạ tên → mã: `TYPE_CODES` trong erd.py.
- Màu bảng `rgb(245, 182, 122)` (`erd_fill` trong style.json).

## Phong cách mặc định (từ XML mẫu của người dùng)
Nền `rgb(122, 207, 245)`, font Dialog 11 đen, nét đen 1.0, FillColor Style=1 Type=1.

## Đường nối: né hình, không trùng nét, cầu nhảy (router.py — yêu cầu bắt buộc của người dùng)
- Luật cho MỌI sơ đồ: nét KHÔNG cắt vào trong hình, hai nét KHÔNG chạy trùng nhau; cắt nhau vuông
  góc thì được nhưng phải có "cầu nhảy" (line jump) như VP vẽ.
- Class và ERD dùng `router.route_all`: A* trên lưới 10px, hình được nới 20px làm vùng cấm, phạt
  góc rẽ/cắt ngang/đi sát song song; ô đã có nét cùng phương bị cấm, góc rẽ và cổng không dùng chung.
  Đường ngắn được định tuyến trước. Không tìm được đường thì quay về `route()` cũ (có in cảnh báo).
- Cầu nhảy (đối chiếu XML mẫu người dùng vẽ tay trong VP 16.1): connector `ConnectorLineJumps="1"`,
  diagram `ConnectorLineJumps="0" ConnectorLineJumpsSize="0"`. Giá trị cũ "4" KHÔNG vẽ cầu nhảy.
- Kiểm tra sau khi build: `python tools/check_routes.py <file>.xml` → báo CẮT HÌNH / TRÙNG NÉT.
- Sơ đồ rất dày (30 class, 37 quan hệ) định tuyến mất vài giây; bố cục `pos` hợp lý vẫn quyết định
  độ đẹp — đặt các class nối nhiều với nhau gần nhau để nét ngắn, ít vòng.
- Use case (nét chéo actor→use case) và sequence chưa đi qua router.

## Bố cục class tự động (classdiag.layout)
- `auto_grid` (tham lam) → `improve_grid`: ủ mô phỏng 4 lần × 40k bước, seed 42, rồi leo đồi đổi chỗ.
  Chi phí `grid_cost`: 10×khoảng cách ô + 6 nếu không thẳng hàng + 40 mỗi class chắn giữa + luật cha ở trên.
  Khung lưới ~sqrt(1.8n) cột. Người dùng muốn: class trung tâm (Trip, Driver...) ở GIỮA cụm, cụm sát nhau.

## Sequence: combined fragment (alt/opt/loop...) và khung sd — đối chiếu XML mẫu VP 16.1
- Model: `CombinedFragment OperatorKind="alt"` trong ModelChildren của Frame gốc, có `CoveredLifeLines`
  (InteractionLifeLine / InteractionActor Idref) và ModelChildren `InteractionOperand` (mỗi nhánh): `Messages`
  liệt kê message nằm trực tiếp trong nhánh, `Guard/InteractionConstraint Constraint="..."` = chữ [điều kiện].
- Shape: CombinedFragment (FillColor trong suốt Transparency=100, Caption H19) + mỗi nhánh một
  `InteractionOperand` cùng X/Width, Y nối tiếp nhau, nhánh đầu = đỉnh khối + 18; VP tự kẻ nét đứt phân cách.
- Khung sd lồng: model `Frame Type="sd"` trong ModelChildren của Frame gốc; shape `Frame` trong suốt.
- ZOrder như VP: operand < activation < khung sd < fragment < actor/lifeline.
- VP vẽ guard ở góc trái nhánh, ngay cạnh lifeline đầu tiên → để trống 66px đầu khối, 46px sau mỗi
  đường phân cách, nếu không nhãn message đè lên guard.

## Bổ sung 2026-11-13
- Sequence: `CoveredLifeLines` của fragment phải gồm MỌI lifeline nằm dưới bề ngang khối. Lifeline
  không có trong danh sách thì VP ẩn đoạn nét đứt bị khối đè lên (lifeline "đứt giữa chừng").
- Nhãn message: chữ hoa/số rộng ~8.2px, chữ thường ~6.3px; ước lượng thiếu thì VP cắt nhãn thành "...".
- Use case: bố cục bằng ủ mô phỏng trên lưới ô (`place_grid`). Nét thẳng đi xuyên use case/actor khác
  bị phạt 1000, hai nét cắt nhau bị phạt 60. Còn nét xuyên hình thì in cảnh báo khi build.
- Người dùng: đã có SVG thì không cần PNG 3x/4x → `png_scales: []` trong style.json.
