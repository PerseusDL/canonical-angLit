#!/usr/bin/env python3
"""Convert the legacy Perseus Beowulf files to self-contained TEI P5/CTS.

The source files are TEI P4 and depend on obsolete remote DTD entities.  This
importer expands those entities to Unicode, preserves page breaks, supplies
complete verse numbering for Klaeber's Old English text, and creates modern
citeStructure declarations used by Perseus MVP.
"""

from __future__ import annotations

import argparse
import html.entities
import re
import unicodedata
from copy import deepcopy
from pathlib import Path

from lxml import etree

TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = f"{{{TEI}}}"

CUSTOM_ENTITIES = {
    "aeligmacr": "æ\u0304", "AEligmacr": "Æ\u0304",
    "amacr": "ā", "Amacr": "Ā", "emacr": "ē", "Emacr": "Ē",
    "imacr": "ī", "Imacr": "Ī", "omacr": "ō", "Omacr": "Ō",
    "umacr": "ū", "Umacr": "Ū", "ymacr": "ȳ", "Ymacr": "Ȳ",
    "rmacr": "r\u0304", "ebreve": "ĕ", "gacute": "ǵ",
    "ecedil": "ȩ", "ohbr": "ǫ", "yogh": "ȝ",
    "dot": "·", "acute": "´", "breve": "˘", "macr": "¯",
    "Dagger": "‡", "dagger": "†", "sect": "§", "pound": "£",
    # Header boilerplate is supplied afresh below.
    "responsibility": "", "Perseus.publish": "", "Perseus.DE": "",
}


def expand_entities(value: str) -> str:
    """Expand every legacy named entity without consulting the network."""
    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in {"amp", "lt", "gt", "quot", "apos"}:
            return match.group(0)
        if name in CUSTOM_ENTITIES:
            return CUSTOM_ENTITIES[name]
        cp = html.entities.name2codepoint.get(name)
        if cp is not None:
            return chr(cp)
        html5 = html.entities.html5.get(name + ";")
        if html5 is not None:
            return html5
        raise ValueError(f"Unknown legacy entity &{name};")

    value = re.sub(r"&([A-Za-z][A-Za-z0-9_.-]*);", repl, value)
    return unicodedata.normalize("NFC", value)


def parse_p4(path: Path) -> etree._Element:
    raw = path.read_text(encoding="utf-8", errors="strict")
    raw = re.sub(r"<!DOCTYPE\s+TEI\.2.*?\]>\s*", "", raw, flags=re.S)
    raw = expand_entities(raw)
    parser = etree.XMLParser(remove_blank_text=False, recover=False, no_network=True)
    return etree.fromstring(raw.encode("utf-8"), parser)


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def p5_copy(source: etree._Element) -> etree._Element:
    """Deep-copy P4 content while applying the small P4-to-P5 vocabulary map."""
    names = {"TEI.2": "TEI", "div1": "div", "div2": "div", "div3": "div",
             "caesura": "seg", "tr": "gloss", "trans": "seg"}
    node = etree.Element(NS + names.get(local(source.tag), local(source.tag)))
    for key, value in source.attrib.items():
        k = local(key)
        if k == "lang":
            node.set(f"{{{XML}}}lang", value)
        elif k == "id":
            node.set(f"{{{XML}}}id", value)
        elif k in {"targOrder", "anchored"}:
            continue
        else:
            node.set(k, value)
    if local(source.tag) == "caesura":
        node.set("type", "caesura")
    if local(source.tag) == "trans":
        node.set("type", "translation")
    node.text = source.text
    for child in source:
        new_child = p5_copy(child)
        new_child.tail = child.tail
        node.append(new_child)
    return node


def header(title: str, role: str, editor: str, year: str, languages: list[tuple[str, str]],
           cite_levels: list[tuple[str, str]]) -> etree._Element:
    h = etree.Element(NS + "teiHeader")
    fd = etree.SubElement(h, NS + "fileDesc")
    ts = etree.SubElement(fd, NS + "titleStmt")
    etree.SubElement(ts, NS + "title").text = title
    etree.SubElement(ts, NS + "editor", role=role).text = editor
    rs = etree.SubElement(ts, NS + "respStmt")
    etree.SubElement(rs, NS + "resp").text = "Legacy Perseus transcription normalized to TEI P5 and CTS"
    etree.SubElement(rs, NS + "name").text = "Perseus Digital Library"
    ps = etree.SubElement(fd, NS + "publicationStmt")
    etree.SubElement(ps, NS + "publisher").text = "Trustees of Tufts University"
    etree.SubElement(ps, NS + "pubPlace").text = "Medford, MA"
    sd = etree.SubElement(fd, NS + "sourceDesc")
    b = etree.SubElement(sd, NS + "bibl")
    b.text = f"{editor}, {title}, Boston: D. C. Heath, {year}."
    enc = etree.SubElement(h, NS + "encodingDesc")
    refs = etree.SubElement(enc, NS + "refsDecl")
    refs.set(f"{{{XML}}}id", "CTS")
    wrapper = etree.SubElement(refs, NS + "citeStructure", match="/TEI/text/body", use="@xml:base")
    parent = wrapper
    for i, (unit, match) in enumerate(cite_levels):
        attrs = {"unit": unit, "match": match, "use": "@n", "delim": ":" if i == 0 else "."}
        if i == 0:
            attrs["n"] = "chunk"
        parent = etree.SubElement(parent, NS + "citeStructure", **attrs)
    profile = etree.SubElement(h, NS + "profileDesc")
    usage = etree.SubElement(profile, NS + "langUsage")
    for ident, label in languages:
        etree.SubElement(usage, NS + "language", ident=ident).text = label
    rev = etree.SubElement(h, NS + "revisionDesc")
    etree.SubElement(rev, NS + "change", when="2026-09-22").text = (
        "Converted from legacy TEI P4; expanded character entities and added CTS citations."
    )
    return h


def document(title: str, version_urn: str, text_lang: str, role: str, editor: str,
             languages: list[tuple[str, str]], cite_levels: list[tuple[str, str]],
             body_children: list[etree._Element]) -> etree._ElementTree:
    root = etree.Element(NS + "TEI", nsmap={None: TEI})
    root.append(header(title, role, editor, "1922", languages, cite_levels))
    text = etree.SubElement(root, NS + "text")
    text.set(f"{{{XML}}}lang", text_lang)
    body = etree.SubElement(text, NS + "body")
    body.set(f"{{{XML}}}base", version_urn)
    for child in body_children:
        body.append(child)
    return etree.ElementTree(root)


def source_body(root: etree._Element) -> etree._Element:
    return next(e for e in root.iter() if local(e.tag) == "body")


def normalize_cards(body: etree._Element, outer_type: str, number_all_lines: bool) -> list[etree._Element]:
    children = [p5_copy(c) for c in body]
    wrapper = etree.Element(NS + "div", type=outer_type)
    for child in children:
        if local(child.tag) == "div":
            child.set("type", "textpart")
            child.set("subtype", "card")
        wrapper.append(child)
    if number_all_lines:
        lines = [e for e in wrapper.iter() if local(e.tag) == "l"]
        first_i, first_n = next(
            (i, int(line.get("n"))) for i, line in enumerate(lines)
            if (line.get("n") or "").isdigit()
        )
        n = first_n - first_i
        for line in lines:
            explicit = line.get("n")
            if explicit and explicit.isdigit() and int(explicit) != n:
                raise ValueError(f"Non-continuous source line anchor: expected {n}, found {explicit}")
            line.set("n", str(n))
            line.set(f"{{{XML}}}id", f"line-{n}")
            n += 1
    return [wrapper]


def anchor_parallel_cards(
    normalized: list[etree._Element], card_starts: list[str]
) -> list[etree._Element]:
    """Anchor a parallel version by card order, independent of bad line OCR.

    Garnett has the same 43 physical text cards as Klaeber, but a handful of
    card and every-fifth-line numbers are corrupt.  Explicit card milestones
    let PMV use the reliable structural correspondence without interpreting
    values such as ``040`` and ``8025`` as real passage boundaries.  The
    printed line labels remain untouched for diplomatic display.
    """
    cards = [e for e in normalized[0] if local(e.tag) == "div"]
    if len(cards) != len(card_starts):
        raise ValueError(
            f"Parallel card mismatch: {len(cards)} translation cards, "
            f"{len(card_starts)} edition cards"
        )
    for card, start in zip(cards, card_starts):
        card.set("n", start)
        card.insert(0, etree.Element(NS + "milestone", unit="card", n=start))
    return normalized


def normalize_commentary(body: etree._Element) -> list[etree._Element]:
    wrapper = etree.Element(NS + "div", type="commentary")
    for card_src in body:
        card = p5_copy(card_src)
        if local(card.tag) != "div":
            wrapper.append(card); continue
        card.set("type", "textpart"); card.set("subtype", "card")
        for item in card:
            if local(item.tag) == "div":
                item.set("type", "textpart"); item.set("subtype", "commline")
                n = item.get("n", "")
                if n:
                    item.set("corresp", f"urn:cts:angLit:anon.beowulf.perseus-ang1:{n}")
        wrapper.append(card)
    return [wrapper]


def add_commentary_links(tree: etree._ElementTree) -> None:
    """Index each commentary paragraph against its Beowulf line range.

    MVP discovers commentary through a TEI standOff/linkGrp.  The legacy
    Klaeber file carries the targets only as commline div/@n values, so give
    every paragraph a stable comment segment and materialize those links.
    Existing lemma elements become the linked lemma segments expected by the
    commentary renderer; the prose and inline markup remain in place.
    """
    root = tree.getroot()
    stand_off = etree.SubElement(root, NS + "standOff")
    link_group = etree.SubElement(
        stand_off,
        NS + "linkGrp",
        type="commentary",
        corresp="urn:cts:angLit:anon.beowulf",
    )
    number = 0
    for div in root.iter(NS + "div"):
        if div.get("subtype") != "commline" or not div.get("n"):
            continue
        for paragraph in list(div.findall(NS + "p")):
            number += 1
            anchor = f"klaeber-comment-{number}"
            comment = etree.Element(NS + "seg", type="comment")
            comment.set(f"{{{XML}}}id", anchor)
            comment.text = paragraph.text
            paragraph.text = None
            for child in list(paragraph):
                paragraph.remove(child)
                comment.append(child)
            paragraph.append(comment)
            lemmas = comment.findall(".//" + NS + "lemma")
            if lemmas:
                lemma = lemmas[0]
                lemma.tag = NS + "seg"
                lemma.set("type", "lemma")
                lemma.set("ana", f"#{anchor}")
            etree.SubElement(
                link_group,
                NS + "link",
                target=(
                    "urn:cts:angLit:anon.beowulf:"
                    f"{div.get('n')} #{anchor}"
                ),
            )


def normalize_glossary(body: etree._Element) -> list[etree._Element]:
    wrapper = etree.Element(NS + "div", type="edition")
    for group_src in body:
        group = p5_copy(group_src)
        if local(group.tag) != "div":
            wrapper.append(group); continue
        group.set("type", "textpart"); group.set("subtype", "card")
        group.set("n", (group.get("n") or "misc").strip().lower())
        for entry in list(e for e in group if local(e.tag) == "entryFree"):
            key = entry.get("key") or "entry"
            entry.set("n", re.sub(r"[^A-Za-z0-9_.-]+", "_", key).strip("_") or "entry")
            entry.set(f"{{{XML}}}id", "entry-" + entry.get("n"))
            index = group.index(entry)
            group.remove(entry)
            p = etree.Element(NS + "p")
            p.append(entry)
            group.insert(index, p)
        wrapper.append(group)
    return [wrapper]


def write(tree: etree._ElementTree, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(path), encoding="utf-8", xml_declaration=True, pretty_print=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, default=Path("data/anon/beowulf"))
    args = ap.parse_args()
    src, out = args.source_dir, args.output_dir

    old = parse_p4(src / "beowulf_text.xml")
    card_starts = [
        child.get("n") for child in source_body(old)
        if local(child.tag) in {"div", "div1"} and child.get("n")
    ]
    write(document("Beowulf", "urn:cts:angLit:anon.beowulf.perseus-ang1", "ang",
                   "editor", "Fr. Klaeber", [("ang", "Old English")],
                   [("card", "div/div[@subtype='card']"), ("line", "l")],
                   normalize_cards(source_body(old), "edition", True)),
          out / "anon.beowulf.perseus-ang1.xml")

    eng = parse_p4(src / "garnett.beowulf_eng.xml")
    write(document("Beowulf", "urn:cts:angLit:anon.beowulf.perseus-eng1", "eng",
                   "translator", "James M. Garnett", [("eng", "English")],
                   [("card", "div/div[@subtype='card']"), ("line", "l")],
                   anchor_parallel_cards(
                       normalize_cards(source_body(eng), "translation", False),
                       card_starts,
                   )),
          out / "anon.beowulf.perseus-eng1.xml")

    com = parse_p4(src / "klaeber.beowulf.xml")
    commentary = document(
        "Commentary on Beowulf",
        "urn:cts:angLit:anon.beowulf.perseus-com-eng1",
        "eng", "commentator", "Fr. Klaeber",
        [("eng", "English"), ("ang", "Old English")],
        [("card", "div/div[@subtype='card']"),
         ("line", "div[@subtype='commline']")],
        normalize_commentary(source_body(com)),
    )
    add_commentary_links(commentary)
    write(commentary, out / "anon.beowulf.perseus-com-eng1.xml")

    # klaeber.glossary.xml is preferred: its literal Unicode thorn is clearer
    # and is semantically equivalent to the test file's mass &thorn; rewrite.
    glo = parse_p4(src / "klaeber.glossary.xml")
    write(document("Klaeber's Beowulf Glossary", "urn:cts:angLit:anon.klaeber_glossary.perseus-mul1", "eng",
                   "editor", "Fr. Klaeber", [("eng", "English"), ("ang", "Old English")],
                   [("letter", "div/div[@subtype='card']"), ("entry", "p/entryFree")],
                   normalize_glossary(source_body(glo))),
          out.parent / "klaeber_glossary" / "anon.klaeber_glossary.perseus-mul1.xml")


if __name__ == "__main__":
    main()
