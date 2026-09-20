import io
import os

try:
    from reportlab.pdfgen import canvas
except ImportError:
    canvas = None

CERTIFICATE_PAGE_SIZE = (1123, 794)

def get_certificate_pdf(
    cert_id: str,
    user_id: int,
    conn,
    course_title: str = "Diamond Education Course",
    student_name: str = "Student",
    issued_at: str = "",
    template_key: str = "english",
    layers: list[dict] | None = None
) -> bytes:
    if not canvas:
        # Fallback agar reportlab o'rnatilmagan bo'lsa
        return b"%PDF-1.4\n%ReportLab fallback\n"

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=CERTIFICATE_PAGE_SIZE)
    width, height = CERTIFICATE_PAGE_SIZE

    # Standard certificate palette matching artwork
    russian = str(template_key).lower() == "russian"

    bg_image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public", "learning-paths", f"certificate-{'russian' if russian else 'english'}.png")
    if os.path.exists(bg_image_path):
        try:
            c.drawImage(bg_image_path, 0, 0, width=width, height=height)
        except Exception:
            pass

    # Signature certificate palette matching artwork (#0C188B / Royal Sapphire Blue)
    CERT_COLOR_RGB = (12 / 255.0, 24 / 255.0, 139 / 255.0)

    # 1. Student Name right on the certificate line (y_svg = 354.5 -> y_pdf = 794 - 354.5 + 8 = 447.5)
    c.setFillColorRGB(*CERT_COLOR_RGB)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(width / 2.0, 447.5, student_name)

    # 2. Course / Track title directly below the line
    c.setFillColorRGB(*CERT_COLOR_RGB)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2.0, 395.0, course_title)

    # 3. Issued Date at the date placeholder line (x=147.5, y_svg=631 -> y_pdf = 794 - 631 + 6 = 169)
    date_str = str(issued_at)[:10] if issued_at else ""
    if date_str:
        c.setFillColorRGB(*CERT_COLOR_RGB)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(147.5, 169.0, date_str)

    # 4. Certificate ID footer
    c.setFillColorRGB(*CERT_COLOR_RGB)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2.0, 110.0, f"ID: {cert_id}")

    # 5. Teacher editor custom layers
    for layer in (layers or [])[:24]:
        if not isinstance(layer, dict):
            continue
        text = str(layer.get("text") or "").strip()[:300]
        if not text:
            continue
        try:
            x = max(0.05, min(0.95, float(layer.get("x", 0.5)))) * width
            # y in editor is from top (0.0 to 1.0) or normalized from bottom
            raw_y = float(layer.get("y", 0.5))
            y = max(0.05, min(0.95, raw_y)) * height
            size = max(8, min(42, float(layer.get("font_size", 14))))
        except (TypeError, ValueError):
            x, y, size = width / 2.0, height / 2.0, 14

        color = str(layer.get("color") or "blue").lower()
        c.setFillColorRGB(*(0.13, 0.22, 0.72) if color == "blue" else (0.12, 0.16, 0.30))
        c.setFont("Helvetica-Bold" if bool(layer.get("bold")) else "Helvetica", size)
        c.drawCentredString(x, y, text)

    c.showPage()
    c.save()

    return buffer.getvalue()
