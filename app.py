from __future__ import annotations

import io
import os
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from flask import Flask, Response, render_template, request, send_file
from PIL import Image

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

try:
    from pix2tex.cli import LatexOCR
except Exception:  # pragma: no cover
    LatexOCR = None

try:
    import latex2mathml.converter
except Exception:  # pragma: no cover
    latex2mathml = None
else:
    latex2mathml = latex2mathml.converter

app = Flask(__name__)


@dataclass
class Block:
    kind: str  # text | equation
    content: str


def _normalize_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _looks_like_equation(line: str) -> bool:
    equation_markers = ["=", "\\frac", "\\sqrt", "∑", "∫", "^", "_", "(", ")"]
    return any(m in line for m in equation_markers) and len(line.split()) <= 20


def extract_blocks_from_image(image: Image.Image) -> list[Block]:
    blocks: list[Block] = []

    text_output = ""
    if pytesseract:
        text_output = pytesseract.image_to_string(image, lang="kor+eng")

    lines = _normalize_lines(text_output)
    for line in lines:
        if _looks_like_equation(line):
            blocks.append(Block(kind="equation", content=line))
        else:
            blocks.append(Block(kind="text", content=line))

    if LatexOCR is not None:
        try:
            model = LatexOCR()
            latex = model(image)
            if latex and len(latex.strip()) > 2:
                blocks.append(Block(kind="equation", content=latex.strip()))
        except Exception:
            pass

    if not blocks:
        blocks.append(Block(kind="text", content="(인식된 텍스트가 없습니다)"))

    return blocks


def _latex_to_mathml(expr: str) -> str:
    if latex2mathml:
        try:
            return latex2mathml.convert(expr)
        except Exception:
            pass

    escaped = (
        expr.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"<math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mtext>{escaped}</mtext></math>"


def _escape_xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_hwpx_bytes(blocks: Iterable[Block]) -> bytes:
    section_parts: list[str] = []
    for idx, block in enumerate(blocks, start=1):
        if block.kind == "equation":
            mathml = _latex_to_mathml(block.content)
            para = f"""
            <hp:p id=\"p{idx}\"> 
              <hp:run><hp:equation>{mathml}</hp:equation></hp:run>
            </hp:p>
            """
        else:
            para = f"""
            <hp:p id=\"p{idx}\">
              <hp:run><hp:t>{_escape_xml(block.content)}</hp:t></hp:run>
            </hp:p>
            """
        section_parts.append(para)

    section_xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<hp:section xmlns:hp=\"http://www.hancom.co.kr/hwpml/2011/paragraph\">
{''.join(section_parts)}
</hp:section>
"""

    content_hpf = """<?xml version="1.0" encoding="UTF-8"?>
<opf:package xmlns:opf="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">
  <opf:metadata>
    <opf:title>수학 문제 변환 결과</opf:title>
    <opf:language>ko</opf:language>
    <opf:creator>Math Screenshot Converter</opf:creator>
    <opf:date>{date}</opf:date>
  </opf:metadata>
  <opf:manifest>
    <opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>
  </opf:manifest>
  <opf:spine>
    <opf:itemref idref="section0"/>
  </opf:spine>
</opf:package>
""".format(date=datetime.utcnow().isoformat())

    mimetype = "application/haansofthwpx"

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", mimetype)
        zf.writestr("Contents/section0.xml", section_xml)
        zf.writestr("content.hpf", content_hpf)
        zf.writestr("META-INF/manifest.xml", "<manifest></manifest>")
    output.seek(0)
    return output.read()


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.post("/convert")
def convert() -> Response:
    file = request.files.get("image")
    if not file or file.filename == "":
        return Response("이미지를 업로드해 주세요.", status=400)

    image = Image.open(file.stream).convert("RGB")
    blocks = extract_blocks_from_image(image)
    data = build_hwpx_bytes(blocks)

    return send_file(
        io.BytesIO(data),
        as_attachment=True,
        download_name="math_problem.hwpx",
        mimetype="application/haansofthwpx",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
