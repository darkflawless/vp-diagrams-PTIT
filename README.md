# Góc hỗ trợ — VP Diagrams

Công cụ vẽ sơ đồ UML (**Use Case, Class, Sequence**) và **ERD** đúng phong cách Visual Paradigm cho
báo cáo/đồ án — viết nội dung sơ đồ bằng file JSON, công cụ tự bố cục, tự đi đường nối (né hình,
không trùng nét, có cầu nhảy) rồi gọi chính **Visual Paradigm CE** trên máy để vẽ. Kết quả:

- ảnh **SVG** (nét, dán Word không vỡ) + **PNG** nền trắng
- file **.vpp** mở bằng Visual Paradigm để sửa tay tiếp

Dùng tốt nhất như một *skill* của [Claude Code](https://claude.com/claude-code): bạn chỉ cần mô tả
sơ đồ bằng lời, Claude tự viết JSON, build và mở ảnh kiểm tra. Cũng chạy tay được bằng Python.

## Cần có

- Windows
- [Visual Paradigm Community Edition](https://www.visual-paradigm.com/download/community.jsp)
  (đã thử với bản 18.1, cài ở `C:\Program Files\Visual Paradigm CE 18.1`).
  Cài chỗ khác thì đặt biến môi trường `VP_HOME` trỏ tới thư mục cài.
- Python 3.9+ (không cần cài thêm thư viện nào)

## Cài đặt

### Cách 1 — làm skill cho Claude Code (khuyên dùng)

```bash
git clone https://github.com/darkflawless/vp-diagrams-PTIT.git "%USERPROFILE%\.claude\skills\vp-diagrams"
```

Mở lại Claude Code rồi nói kiểu: *"vẽ giúp mình use case cho hệ thống quản lý thư viện"* hoặc gõ
`/vp-diagrams`.

### Cách 2 — chạy tay

```bash
python vpgen/build.py examples/thu_vien.json out/
python vpgen/build.py thu_muc_json/ out/          # build cả thư mục
```

Mỗi sơ đồ mất ~30–60 giây (VP khởi động Java). Sau khi build class/ERD nên chạy
`python tools/check_routes.py out/<ten>.xml` — ra "OK, không lỗi" là đường nối sạch.

## Định dạng JSON

Xem các mẫu chạy được trong [`examples/`](examples/) và phần *Định dạng JSON* trong
[`SKILL.md`](SKILL.md):

| Loại       | Mẫu                                   |
|------------|---------------------------------------|
| Use case   | `thu_vien.json`, `ten_dai.json`       |
| Class      | `gio_hang.json`, `thu_vien_class.json`|
| Sequence   | `hoa_don.json`, `dang_nhap.json`, `dang_nhap_alt.json` (alt/opt/loop) |
| ERD        | `dat_phong.json`, `thu_vien_erd.json` |

Đổi màu/font/định dạng ảnh: sửa [`vpgen/style.json`](vpgen/style.json).
Ghi chú kỹ thuật về XML của VP (cho ai muốn thêm loại sơ đồ): [`NOTES.md`](NOTES.md).

## Góp ý (feedback)

Đây là bản dùng thử. Gặp lỗi hay muốn thêm tính năng, hãy mở **Issue** trong repo này, ghi kèm:

1. file JSON bạn dùng (hoặc mô tả sơ đồ),
2. ảnh kết quả / thông báo lỗi,
3. bản Visual Paradigm và Python đang cài.

Logo "Powered By Visual Paradigm Community Edition" trên ảnh là của VP CE — giữ nguyên nhé.
