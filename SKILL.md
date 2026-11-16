---
name: vp-diagrams
description: Vẽ sơ đồ UML (Use Case, Class, Sequence) và ERD đúng phong cách Visual Paradigm bằng chính Visual Paradigm CE trên máy — từ file mô tả JSON, tự bố cục, xuất SVG/PNG/PDF và file .vpp sửa tay được. Dùng khi người dùng cần sơ đồ cho báo cáo/đồ án theo kiểu Visual Paradigm (màu xanh, actor hình người, thoi đen/trắng, lifeline boundary/control/entity), hoặc muốn thêm loại sơ đồ mới vào bộ này.
---

# VP Diagrams — sơ đồ phong cách Visual Paradigm

Bộ này KHÔNG bắt chước hình vẽ: nó sinh XML đúng định dạng của Visual Paradigm, rồi gọi
`ImportXML` + `ExportDiagramImage` có sẵn trong VP CE (chạy ngầm, headless) để chính VP vẽ.
Nên phong cách là hàng thật, kèm logo "Powered By Visual Paradigm Community Edition" (người dùng
muốn GIỮ logo — giáo viên thích; không được gỡ hay che).

## Dùng

```
python "<skill>/vpgen/build.py" so_do.json [thu_muc_ra] [svg] [png_with_background] [pdf]
python "<skill>/vpgen/build.py" thu_muc_json/ [thu_muc_ra]     # build cả thư mục
```
`<skill>` = thư mục chứa file này. Mặc định xuất cả SVG (nét, dán Word được) và PNG nền trắng
(`style.json` → `image_type`). Mỗi lần build ~30–60 giây/sơ đồ (khởi động Java của VP).
Kết quả: ảnh + `.xml` + `.vpp` (mở bằng VP để chỉnh tay).

Quy trình với người dùng: hỏi/đọc nội dung sơ đồ → viết file JSON (copy mẫu trong `examples/`)
vào thư mục làm việc của họ → build → **luôn mở ảnh ra xem** trước khi báo xong → sửa JSON nếu cần.

**Luật đường nối (bắt buộc, người dùng yêu cầu):** nét không cắt vào trong hình, hai nét không trùng
nhau, chỗ cắt nhau có cầu nhảy. Class/ERD tự định tuyến bằng `vpgen/router.py`; sau khi build chạy
`python "<skill>/tools/check_routes.py" <file>.xml` — phải ra "OK, không lỗi" mới báo xong.

**Phong cách theo mẫu của giáo viên (ưu tiên cao nhất, người dùng duyệt 2026-11-16):**
- Sequence: xếp lifeline theo tầng trái→phải: actor → boundary (trang/màn hình) → control (Controller,
  Service, Repository) → entity; hệ thống ngoài (MQTT Broker, app điện thoại) để cuối bên phải. Nhãn ngắn:
  "gọi" / "trả về" / "hiển thị" / "click ..."; TÊN HÀM chỉ ghi trên mũi tên TỰ GỌI của bên được gọi
  (Controller tự gọi `startSimulation()`, Repository tự gọi `findById()`). Repository đọc dữ liệu thì
  Repository → Entity "gọi", Entity tự gọi hàm khởi tạo `Trip()`, trả về. Gộp lớp phụ (SseBroadcaster,
  ObjectMapper, HaversineUtil) thành self-call/mũi tên async. Không ghi "200 OK", dùng "trả về".
- Class: mỗi trường tham chiếu đối tượng ghi thành thuộc tính (`-trip : Trip`) và vẽ thoi trắng ở lớp giữ
  trường đó (aggregation from = lớp giữ). Tổng thể giữ danh sách bộ phận phụ thuộc → thêm `-dsX : X[]` + thoi đen.
  Kế thừa chỉ cho quan hệ is-a thật; không in nghiêng.
- Use case: khung hệ thống tô cùng màu xanh (`system_fill` trong style.json).

**Quy tắc sequence (bắt buộc, người dùng yêu cầu):**
1. Xử lý bên trong controller/service/view (validate, dựng entity, transaction, đóng gói response...) vẽ
   thành các mũi tên tự gọi — cứ gọi hàm gì là có một mũi tên.
2. Mọi lời gọi đều có trả về nét đứt (repository → "đã lưu"/dữ liệu, publish/broadcast → "đã phát",
   controller → "200 OK"). Build sẽ in cảnh báo "chưa có trả về" — phải hết cảnh báo mới báo xong.
   NGOẠI LỆ: giao thức fire-and-forget (MQTT publish, đẩy sự kiện SSE, UDP...) ghi `"async": true`
   → mũi tên đầu mở, không cần trả về. Lời gọi hàm Java đồng bộ (kể cả hàm void) vẫn cần trả về.
3. View nhận 200 → tự render → trả về cho user bằng nét đứt ("return view ...") → user mới thao tác tiếp.
   Chuyển trang: user mở trang → view gọi API → 200 → render → nét đứt trả trang cho user.
4. Repository là một lifeline riêng, cùng hình với controller/service (`"kind": "control"`): service → repo `findById(...)`/`save(...)`
   → repo TỰ GỌI "truy vấn SELECT bảng" / "INSERT bảng" → nét đứt trả về `Optional<X>` / "đã lưu".
5. Tạo entity: service → entity `«create» builder()...build()` (hoặc `new X(...)`) → nét đứt trả object;
   gán trường sau đó: service → entity `setX(...)`, mỗi setter một mũi tên. Entity chỉ xuất hiện khi
   được tạo/sửa; truy vấn thì chỉ cần repository.
6. Mặc định vẽ đúng code thật. Nếu người dùng bảo vẽ theo thiết kế ĐÍCH (code sắp bổ sung) thì bọc phần
   chưa có trong khung `{"frame": "... (sắp bổ sung)", ...}` để phân biệt.
7. Phía Android cũng có lớp Java riêng (MQTT client, Activity, SoundManager...), không chỉ "view".
8. Quá ~16 lifeline thì tách thành nhiều sequence nối tiếp (ghi "xem Sequence N" trên message nối).

## Định dạng JSON

Trường `"type"`: `usecase` | `class` | `sequence` | `erd` (bỏ trống thì tự đoán). Chi tiết đầy đủ ở docstring
đầu mỗi file trong `vpgen/`, mẫu chạy được trong `examples/`:

- **usecase** (`thu_vien.json`, `ten_dai.json`): `system`, `actors` (TẤT CẢ actor), `right_actors` (tập con của `actors` đặt bên phải), `usecases`,
  `links` [actor, uc], `include` [gốc, được include], `extend` [mở rộng, gốc]. `generalization` [con, cha] cho actor–actor hoặc uc–uc (tam giác rỗng). Mẫu thầy: 1 use case chính include các bước của kịch bản; actor con kế thừa "Người dùng" (Đăng nhập), "X đăng nhập" kế thừa "Đăng nhập". Sơ đồ đông: `ncol` (số cột), `uc_col` {use case: cột} để ghim cột, `actor_gap` (px giữa actor và khung); tổng quát hoá actor–actor ở hai phía tự đi vòng phía trên khung. Một actor nối >8 use case thì gom theo nhóm menu thật. `top_actors`/`bottom_actors`: actor đặt trên đỉnh/dưới đáy khung (như "Thành viên" của mẫu), tổng quát hoá tới nó tự đi gấp khúc; `uc_cell` {use case: [cột, hàng]} ghim cứng một ô. `show_extension_points` chưa hiện được ngăn extension points trong VP (cần XML mẫu) — để false. Tên dài tự xuống dòng.
- **class** (`gio_hang.json`, `thu_vien_class.json`): `classes` với `attributes` ("-id : Integer"),
  `operations` ("+tinh(a : Date) : Float"), `abstract`, `stereotype`, `pos` [cột, hàng] tuỳ chọn.
  `relations`: association | aggregation | composition (from = bên TỔNG THỂ, có hình thoi) |
  inheritance | realization (from = con, to = cha) | dependency; `from_mult`, `to_mult`.
  Bỏ `pos` thì tự bố cục: tham lam + ủ mô phỏng (seed cố định), kéo class nhiều liên kết vào GIỮA cụm
  của nó và đặt các class liên quan sát nhau (người dùng muốn vậy). Chỉ dùng `pos` khi cần ép vị trí.
- **sequence** (`hoa_don.json`, `dang_nhap.json`): `lifelines` (kind: boundary | control | entity |
  actor | bỏ trống), `messages` theo thứ tự thời gian (`"return": true` cho trả về, from = to là tự gọi).
  Activation tự tính. Khối `alt`/`opt`/`loop`/`break`/`par` (có guard [điều kiện], alt nhiều nhánh) và
  khung `sd` (khung đặt tên một kịch bản con) xen giữa các message, lồng nhau được — mẫu
  `dang_nhap_alt.json`. Muốn tham chiếu sang sơ đồ khác thì UML dùng `ref` (chưa hỗ trợ, cần XML mẫu).
- **erd** (`dat_phong.json`, `thu_vien_erd.json`): `tables` với `columns` dạng chuỗi
  `"ten kieu [pk] [notnull] [unique]"` (vd `"email varchar(255) unique"`); cột không ghi gì = cho phép
  NULL. `relations`: from = bảng CHA, to = bảng con, `fk` = tên cột khoá ngoại ở bảng con (chưa có thì
  tự thêm), `from_mult`/`to_mult` (mặc định 1 → 0..*), `identifying` (true = nét liền).
  Kiểu dữ liệu hỗ trợ: xem `TYPE_CODES` trong `vpgen/erd.py` (datetime hiện thành timestamp, text → clob).

## Đổi phong cách

Sửa `vpgen/style.json` (màu nền, font, nét, định dạng ảnh) — không sửa trong code.

## Thêm loại sơ đồ mới / sửa bộ sinh

Đọc `NOTES.md` TRƯỚC khi đụng vào XML: nó ghi các bẫy đã mất nhiều công mới tìm ra
(khung connector bị clip, ZOrder, chiều From/To, ...). Cách làm đã hiệu quả: xin người dùng vẽ
một sơ đồ nhỏ trong VP → Export → XML (kèm ảnh chụp bảng ký hiệu) → rút gọn XML để đọc
(`tools/slim.py`) → viết module `generate(spec) -> str` → đăng ký trong `GENERATORS` ở `build.py`
→ dựng lại đúng sơ đồ mẫu của họ để so với ảnh gốc.

## Trạng thái

- Xong: Use Case, Class, Sequence (kể cả actor — thanh dọc chạy hết chiều cao dưới actor là
  cách VP tự vẽ, đã đối chiếu với mẫu thật, KHÔNG phải lỗi), ERD.
- Có thể thêm sau: Activity, State, Component/Deployment (cùng quy trình xin XML mẫu ở trên).
- Đã biết: sơ đồ nhiều bảng/class nối thành chuỗi dài sẽ trải ngang; dùng `pos` để bẻ hàng.
- Use case và sequence chưa đi qua router (xem NOTES.md).
