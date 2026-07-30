"""Lector de EPUB con biblioteca estandar.

Sin dependencias externas a proposito: `zipfile`, `xml.etree` y `html.parser`
bastan, y evitan atarnos a una libreria de EPUB poco mantenida.

Nota legal: este modulo lee archivos que el usuario ya tiene en su maquina.
El repositorio no distribuye libros; distribuye la herramienta.
"""

from __future__ import annotations

import logging
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

log = logging.getLogger(__name__)

NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}

# Etiquetas tras las cuales hay que cortar parrafo.
BLOCK_TAGS = {
    "p", "div", "br", "li", "tr", "blockquote", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6", "hr", "figcaption", "td",
}
SKIP_TAGS = {"script", "style", "head", "title"}
HEADING_TAGS = {"h1", "h2", "h3"}


@dataclass
class EpubChapter:
    idx: int
    title: str | None
    # (texto, es_encabezado). El flag importa: segmentar un encabezado como
    # prosa produce oraciones falsas — «Chapter I. The Beginning» se parte en
    # dos — y esas oraciones acaban en la practica de lectura en voz alta.
    blocks: list[tuple[str, bool]] = field(default_factory=list)

    @property
    def paragraphs(self) -> list[str]:
        return [text for text, _ in self.blocks]

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)


@dataclass
class EpubBook:
    title: str
    author: str | None
    chapters: list[EpubChapter] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(len(p.split()) for ch in self.chapters for p in ch.paragraphs)


class _TextExtractor(HTMLParser):
    """XHTML -> parrafos. Tolerante con marcado sucio (convert_charrefs=True)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, bool]] = []
        self.heading: str | None = None
        self._buffer: list[str] = []
        self._skip_depth = 0
        self._heading_depth = 0

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self._buffer)).strip()
        self._buffer.clear()
        if not text:
            return

        is_heading = bool(self._heading_depth)
        if is_heading and self.heading is None:
            # El primer encabezado es el titulo del capitulo: se guarda ahi
            # y no se repite como contenido legible.
            self.heading = text
            return
        self.blocks.append((text, is_heading))

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif tag in BLOCK_TAGS:
            self._flush()
            if tag in HEADING_TAGS:
                self._heading_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in BLOCK_TAGS:
            self._flush()
            if tag in HEADING_TAGS:
                self._heading_depth = max(0, self._heading_depth - 1)

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def _extract(xhtml: str) -> tuple[str | None, list[tuple[str, bool]]]:
    parser = _TextExtractor()
    try:
        parser.feed(xhtml)
        parser.close()
    except Exception as exc:  # noqa: BLE001 - un capitulo roto no debe abortar el libro
        log.warning("epub: capitulo con marcado invalido (%s), se usa lo extraido", exc)
    return parser.heading, parser.blocks


# Marcas de la plantilla legal de Project Gutenberg. Un capitulo que las
# cumple son paginas de licencia, no del libro: nadie va a leer los terminos
# de uso en voz alta, y ensucian la lista de capitulos y el conteo de progreso.
_GUTENBERG_MARKERS = (
    "project gutenberg license",
    "www.gutenberg.org",
    "start of the project gutenberg",
    "end of the project gutenberg",
    "gutenberg literary archive foundation",
    "redistributing project gutenberg",
)


def _is_boilerplate(paragraphs: list[str]) -> bool:
    if not paragraphs:
        return True
    sample = " ".join(paragraphs[:60]).lower()
    if "gutenberg" not in sample:
        return False
    return sum(marker in sample for marker in _GUTENBERG_MARKERS) >= 2


def _opf_path(zf: zipfile.ZipFile) -> str:
    root = ET.fromstring(zf.read("META-INF/container.xml"))
    rootfile = root.find(".//container:rootfile", NS)
    if rootfile is None or not rootfile.get("full-path"):
        raise ValueError("EPUB invalido: falta rootfile en container.xml")
    return rootfile.attrib["full-path"]


def read_epub(path: Path, *, min_paragraphs: int = 2) -> EpubBook:
    """Lee un EPUB y devuelve capitulos en el orden del `spine`.

    Los capitulos con menos de `min_paragraphs` parrafos se descartan: suelen
    ser portadas, paginas de copyright o separadores sin contenido util.
    """
    with zipfile.ZipFile(path) as zf:
        opf_name = _opf_path(zf)
        opf_dir = posixpath.dirname(opf_name)
        opf = ET.fromstring(zf.read(opf_name))

        title_el = opf.find(".//dc:title", NS)
        author_el = opf.find(".//dc:creator", NS)
        title = (title_el.text or "").strip() if title_el is not None else path.stem
        author = (author_el.text or "").strip() if author_el is not None else None

        manifest = {
            item.attrib["id"]: item.attrib["href"]
            for item in opf.findall(".//opf:manifest/opf:item", NS)
            if "id" in item.attrib and "href" in item.attrib
        }
        spine = [
            ref.attrib["idref"]
            for ref in opf.findall(".//opf:spine/opf:itemref", NS)
            if "idref" in ref.attrib
        ]

        chapters: list[EpubChapter] = []
        for idref in spine:
            href = manifest.get(idref)
            if not href:
                continue
            name = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
            try:
                raw = zf.read(name)
            except KeyError:
                log.warning("epub: %s referenciado en el spine pero ausente del zip", name)
                continue

            heading, blocks = _extract(raw.decode("utf-8", errors="replace"))
            if len(blocks) < min_paragraphs:
                continue
            if _is_boilerplate([text for text, _ in blocks]):
                log.info("epub: descartado %s (plantilla legal de Gutenberg)", name)
                continue
            chapters.append(EpubChapter(idx=len(chapters), title=heading, blocks=blocks))

    if not chapters:
        raise ValueError("No se extrajo texto: revisa que el EPUB no este cifrado (DRM)")

    return EpubBook(title=title or path.stem, author=author, chapters=chapters)
