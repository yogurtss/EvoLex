#!/usr/bin/env python3
"""Render compact, portable Chinese patent figures from ``draft.json``.

The upstream patent package renderer intentionally uses conservative defaults,
but its fallback bitmap font does not contain CJK glyphs on a minimal Linux
host.  This renderer creates a small Noto CJK subset containing only characters
used by the formal figures, embeds that subset into every SVG, and uses it for
the corresponding 300-DPI PNG files.  It also fails early when figure topology,
claim-step coverage, drawing numbers, or font coverage is inconsistent.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import textwrap
from pathlib import Path


def figure_text(data: dict) -> str:
    parts: list[str] = []
    for figure in data.get("figures", []):
        parts.extend(
            [
                f"图{figure.get('number', '')}",
                str(figure.get("title", "")),
            ]
        )
        parts.extend(str(node.get("label", "")) for node in figure.get("nodes", []))
        parts.extend(str(edge.get("label", "")) for edge in figure.get("edges", []))
    parts.append("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789：—、（）- ")
    return "".join(parts)


def subset_font(source: Path, destination: Path, text: str) -> None:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    destination.parent.mkdir(parents=True, exist_ok=True)
    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.name_languages = ["*"]
    font = TTFont(str(source))
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    font.save(str(destination))


def missing_font_characters(font_path: Path, text: str) -> list[str]:
    """Return visible characters not covered by any Unicode cmap in ``font``."""

    from fontTools.ttLib import TTFont

    font = TTFont(str(font_path), lazy=True)
    try:
        codepoints: set[int] = set()
        for table in font["cmap"].tables:
            if table.isUnicode():
                codepoints.update(table.cmap)
    finally:
        font.close()
    return sorted(
        {character for character in text if not character.isspace()}
        - {chr(codepoint) for codepoint in codepoints},
        key=ord,
    )


def describe_characters(characters: list[str], limit: int = 12) -> str:
    shown = characters[:limit]
    description = ", ".join(
        f"{character!r} (U+{ord(character):04X})" for character in shown
    )
    if len(characters) > limit:
        description += f", ... and {len(characters) - limit} more"
    return description


def claim_steps(text: str) -> list[str]:
    """Extract ordered S-numbered steps from an independent method claim."""

    return re.findall(r"(?<![A-Za-z0-9])S\d+", text)


def validate_figure_structure(data: dict) -> None:
    """Validate formal-drawing structure against claims and the specification."""

    errors: list[str] = []
    figures = data.get("figures", [])
    if not figures:
        raise ValueError("draft contains no formal figures")

    try:
        numbers = [int(figure["number"]) for figure in figures]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("every figure must have an integer number") from exc
    if len(numbers) != len(set(numbers)):
        errors.append("figure numbers are not unique")
    expected_numbers = list(range(1, len(figures) + 1))
    if sorted(numbers) != expected_numbers:
        errors.append(
            f"figure numbers must be consecutive {expected_numbers}, got {sorted(numbers)}"
        )

    claims: dict[int, dict] = {}
    for claim in data.get("claims", []):
        try:
            claims[int(claim["number"])] = claim
        except (KeyError, TypeError, ValueError):
            errors.append("every claim must have an integer number")

    for figure in figures:
        number = int(figure["number"])
        title = str(figure.get("title", "")).strip()
        if not title:
            errors.append(f"figure {number} has no title")

        nodes = figure.get("nodes", [])
        if not nodes:
            errors.append(f"figure {number} has no nodes")
            continue
        node_ids = [str(node.get("id", "")).strip() for node in nodes]
        if any(not node_id for node_id in node_ids):
            errors.append(f"figure {number} has a node without an id")
        if len(node_ids) != len(set(node_ids)):
            errors.append(f"figure {number} has duplicate node ids")
        node_id_set = set(node_ids)

        adjacency = {node_id: set() for node_id in node_ids}
        indegree = {node_id: 0 for node_id in node_ids}
        edge_pairs: set[tuple[str, str]] = set()
        for edge in figure.get("edges", []):
            source = str(edge.get("from", "")).strip()
            target = str(edge.get("to", "")).strip()
            if source not in node_id_set or target not in node_id_set:
                errors.append(
                    f"figure {number} edge {source!r}->{target!r} references an unknown node"
                )
                continue
            if source == target:
                errors.append(f"figure {number} contains self-loop {source!r}")
            if (source, target) in edge_pairs:
                errors.append(
                    f"figure {number} contains duplicate edge {source!r}->{target!r}"
                )
            edge_pairs.add((source, target))
            adjacency[source].add(target)
            indegree[target] += 1

        roots = [node_id for node_id in node_ids if indegree[node_id] == 0]
        if len(roots) != 1:
            errors.append(
                f"figure {number} must have one entry node, found {len(roots)}"
            )
        elif roots:
            reachable: set[str] = set()
            stack = [roots[0]]
            while stack:
                node_id = stack.pop()
                if node_id in reachable:
                    continue
                reachable.add(node_id)
                stack.extend(adjacency[node_id] - reachable)
            unreachable = node_id_set - reachable
            if unreachable:
                errors.append(
                    f"figure {number} has unreachable nodes {sorted(unreachable)}"
                )

        # Kahn's algorithm also catches cyclic flowcharts that happen to be reachable.
        remaining_indegree = dict(indegree)
        queue = [node_id for node_id in node_ids if remaining_indegree[node_id] == 0]
        visited = 0
        while queue:
            node_id = queue.pop()
            visited += 1
            for target in adjacency[node_id]:
                remaining_indegree[target] -= 1
                if remaining_indegree[target] == 0:
                    queue.append(target)
        if visited != len(node_ids):
            errors.append(f"figure {number} contains a directed cycle")

        claim_number = figure.get("claim_number")
        if claim_number is not None:
            try:
                claim_number = int(claim_number)
            except (TypeError, ValueError):
                errors.append(f"figure {number} has an invalid claim_number")
                continue
            claim = claims.get(claim_number)
            if claim is None:
                errors.append(
                    f"figure {number} references missing claim {claim_number}"
                )
                continue
            drawing_steps = [
                str(node.get("claim_step", "")).strip() for node in nodes
            ]
            expected_steps = claim_steps(str(claim.get("text", "")))
            if drawing_steps != expected_steps:
                errors.append(
                    f"figure {number} claim steps {drawing_steps} do not match "
                    f"claim {claim_number} steps {expected_steps}"
                )
            for source, target in zip(node_ids, node_ids[1:]):
                if (source, target) not in edge_pairs:
                    errors.append(
                        f"figure {number} claim flow lacks edge {source!r}->{target!r}"
                    )

    descriptions = data.get("specification", {}).get("figure_descriptions", [])
    described_numbers: list[int] = []
    for description in descriptions:
        match = re.match(r"^图(\d+)", str(description).strip())
        if match is None:
            errors.append(f"drawing description lacks a 图N prefix: {description!r}")
        else:
            described_numbers.append(int(match.group(1)))
    if sorted(described_numbers) != expected_numbers:
        errors.append(
            "drawing descriptions must cover each formal figure exactly once; "
            f"got {sorted(described_numbers)}"
        )

    try:
        abstract_number = int(data["abstract_figure_number"])
    except (KeyError, TypeError, ValueError):
        errors.append("abstract_figure_number is missing or invalid")
    else:
        abstract_figure = next(
            (figure for figure in figures if int(figure["number"]) == abstract_number),
            None,
        )
        if abstract_figure is None:
            errors.append(f"abstract figure {abstract_number} does not exist")
        elif int(abstract_figure.get("claim_number", 0)) != 1:
            errors.append("the abstract figure must be the complete claim-1 method flow")

    if errors:
        raise ValueError("; ".join(errors))


def wrap_label(value: str, width: int = 26) -> list[str]:
    lines: list[str] = []
    for paragraph in str(value).splitlines() or [""]:
        lines.extend(
            textwrap.wrap(
                paragraph,
                width=width,
                break_long_words=True,
                break_on_hyphens=False,
            )
            or [""]
        )
    return lines


def label_wrap_width(box_width: int) -> int:
    """Scale the deterministic character wrap limit to a node's box width."""

    return max(8, round(26 * box_width / 600))


def graph_layers(figure: dict) -> list[list[str]]:
    """Return stable longest-path layers for an already validated DAG."""

    node_ids = [str(node["id"]) for node in figure.get("nodes", [])]
    order = {node_id: index for index, node_id in enumerate(node_ids)}
    adjacency = {node_id: [] for node_id in node_ids}
    indegree = {node_id: 0 for node_id in node_ids}
    depth = {node_id: 0 for node_id in node_ids}
    for edge in figure.get("edges", []):
        source = str(edge["from"])
        target = str(edge["to"])
        adjacency[source].append(target)
        indegree[target] += 1

    queue = sorted(
        (node_id for node_id in node_ids if indegree[node_id] == 0),
        key=order.__getitem__,
    )
    while queue:
        source = queue.pop(0)
        for target in sorted(adjacency[source], key=order.__getitem__):
            depth[target] = max(depth[target], depth[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
                queue.sort(key=order.__getitem__)

    layers: list[list[str]] = []
    for node_id in node_ids:
        while len(layers) <= depth[node_id]:
            layers.append([])
        layers[depth[node_id]].append(node_id)
    return layers


def layout(figure: dict) -> tuple[dict[str, tuple[int, int, int, int]], int, int]:
    width = 720
    margin_x = 60
    horizontal_gap = 36
    title_height = 72
    margin_y = 35
    vertical_gap = 58
    y = title_height
    positions: dict[str, tuple[int, int, int, int]] = {}
    nodes = {str(node["id"]): node for node in figure.get("nodes", [])}
    for layer in graph_layers(figure):
        box_width = (
            width - 2 * margin_x - horizontal_gap * (len(layer) - 1)
        ) // len(layer)
        heights = {
            node_id: max(
                68,
                38
                + 25
                * len(
                    wrap_label(
                        nodes[node_id].get("label", ""),
                        label_wrap_width(box_width),
                    )
                ),
            )
            for node_id in layer
        }
        layer_height = max(heights.values())
        for index, node_id in enumerate(layer):
            x = margin_x + index * (box_width + horizontal_gap)
            positions[node_id] = (x, y, box_width, heights[node_id])
        y += layer_height + vertical_gap
    height = y - vertical_gap + margin_y
    return positions, width, height


def anchors(
    source: tuple[int, int, int, int],
    target: tuple[int, int, int, int],
) -> tuple[float, float, float, float]:
    sx, sy, sw, sh = source
    tx, ty, tw, _ = target
    return sx + sw / 2, sy + sh, tx + tw / 2, ty


def validate_text_layout(data: dict, font_path: Path) -> None:
    """Fail rather than emit a formal drawing with clipped or overflowing text."""

    from PIL import ImageFont

    title_font = ImageFont.truetype(str(font_path), 24)
    body_font = ImageFont.truetype(str(font_path), 20)
    edge_font = ImageFont.truetype(str(font_path), 15)
    errors: list[str] = []

    def text_width(font: ImageFont.FreeTypeFont, value: str) -> int:
        bounds = font.getbbox(value)
        return bounds[2] - bounds[0]

    for figure in data.get("figures", []):
        number = int(figure["number"])
        positions, width, _ = layout(figure)
        title = f"图{number} {figure.get('title', '')}"
        if text_width(title_font, title) > width - 40:
            errors.append(f"figure {number} title exceeds the drawing width")

        for node in figure.get("nodes", []):
            node_id = str(node["id"])
            _, _, box_width, _ = positions[node_id]
            lines = wrap_label(
                node.get("label", ""), label_wrap_width(box_width)
            )
            for line in lines:
                if text_width(body_font, line) > box_width - 32:
                    errors.append(
                        f"figure {number} node {node_id!r} text exceeds its box"
                    )

        for edge in figure.get("edges", []):
            label = str(edge.get("label", "")).strip()
            if not label:
                continue
            x1, _, x2, _ = anchors(
                positions[str(edge["from"])], positions[str(edge["to"])]
            )
            label_x = (x1 + x2) / 2 + 12
            if label_x + text_width(edge_font, label) > width - 10:
                errors.append(
                    f"figure {number} edge {edge['from']!r}->{edge['to']!r} "
                    "label exceeds the drawing width"
                )

    if errors:
        raise ValueError("; ".join(errors))


def render_svg(figure: dict, font_bytes: bytes) -> str:
    positions, width, height = layout(figure)
    font_data = base64.b64encode(font_bytes).decode("ascii")
    title = f"图{figure['number']} {figure.get('title', '')}"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="{html.escape(title)}">'
        ),
        "<defs>",
        "<style>",
        (
            "@font-face{font-family:EvoLexPatentCJK;"
            f"src:url(data:font/otf;base64,{font_data}) format('opentype');}}"
        ),
        "text{font-family:EvoLexPatentCJK,sans-serif;fill:#000}",
        "</style>",
        (
            '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="8" markerHeight="8" orient="auto">'
        ),
        '<path d="M0 0 L10 5 L0 10 z" fill="#000"/>',
        "</marker>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#fff"/>',
        (
            f'<text x="{width / 2}" y="30" text-anchor="middle" '
            f'font-size="24">{html.escape(title)}</text>'
        ),
    ]
    for edge in figure.get("edges", []):
        x1, y1, x2, y2 = anchors(
            positions[str(edge["from"])],
            positions[str(edge["to"])],
        )
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            'stroke="#000" stroke-width="2" marker-end="url(#arrow)"/>'
        )
        label = str(edge.get("label", "")).strip()
        if label:
            parts.append(
                f'<text x="{(x1 + x2) / 2 + 12}" y="{(y1 + y2) / 2 - 5}" '
                f'font-size="15">{html.escape(label)}</text>'
            )
    for node in figure.get("nodes", []):
        x, y, box_width, box_height = positions[str(node["id"])]
        parts.append(
            f'<rect x="{x}" y="{y}" width="{box_width}" height="{box_height}" '
            'fill="#fff" stroke="#000" stroke-width="2"/>'
        )
        lines = wrap_label(
            node.get("label", ""), label_wrap_width(box_width)
        )
        start_y = y + box_height / 2 - (len(lines) - 1) * 12.5
        for index, line in enumerate(lines):
            parts.append(
                f'<text x="{x + box_width / 2}" '
                f'y="{start_y + index * 25}" text-anchor="middle" '
                f'dominant-baseline="middle" font-size="20">'
                f"{html.escape(line)}</text>"
            )
    parts.append("</svg>")
    return "\n".join(parts)


def render_png(figure: dict, font_path: Path, output: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    positions, width, height = layout(figure)
    scale = 3
    image = Image.new("RGB", (width * scale, height * scale), "white")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(str(font_path), 24 * scale)
    body_font = ImageFont.truetype(str(font_path), 20 * scale)
    edge_font = ImageFont.truetype(str(font_path), 15 * scale)

    def point(value: float) -> int:
        return int(round(value * scale))

    title = f"图{figure['number']} {figure.get('title', '')}"
    title_box = draw.textbbox((0, 0), title, font=title_font)
    title_x = (width * scale - (title_box[2] - title_box[0])) / 2
    draw.text((title_x, point(5)), title, fill="black", font=title_font)

    for edge in figure.get("edges", []):
        x1, y1, x2, y2 = anchors(
            positions[str(edge["from"])],
            positions[str(edge["to"])],
        )
        draw.line(
            (point(x1), point(y1), point(x2), point(y2)),
            fill="black",
            width=6,
        )
        draw.polygon(
            [
                (point(x2), point(y2)),
                (point(x2 - 8), point(y2 - 14)),
                (point(x2 + 8), point(y2 - 14)),
            ],
            fill="black",
        )
        label = str(edge.get("label", "")).strip()
        if label:
            draw.text(
                (point((x1 + x2) / 2 + 12), point((y1 + y2) / 2 - 18)),
                label,
                fill="black",
                font=edge_font,
            )

    for node in figure.get("nodes", []):
        x, y, box_width, box_height = positions[str(node["id"])]
        draw.rectangle(
            (point(x), point(y), point(x + box_width), point(y + box_height)),
            fill="white",
            outline="black",
            width=6,
        )
        lines = wrap_label(
            node.get("label", ""), label_wrap_width(box_width)
        )
        line_height = 25 * scale
        text_y = point(y + box_height / 2) - line_height * len(lines) / 2
        for line in lines:
            text_box = draw.textbbox((0, 0), line, font=body_font)
            text_width = text_box[2] - text_box[0]
            text_x = point(x + box_width / 2) - text_width / 2
            draw.text((text_x, text_y), line, fill="black", font=body_font)
            text_y += line_height

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", dpi=(300, 300), optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--font-output",
        type=Path,
        default=Path(__file__).resolve().parent
        / "assets"
        / "EvoLexPatentCJK-Subset.otf",
    )
    parser.add_argument("--source-font", type=Path)
    args = parser.parse_args()

    data = json.loads(args.draft.read_text(encoding="utf-8"))
    try:
        validate_figure_structure(data)
    except ValueError as exc:
        parser.error(f"formal-figure validation failed: {exc}")

    if args.source_font is not None:
        if not args.source_font.is_file():
            parser.error(f"source font does not exist: {args.source_font}")
        subset_font(args.source_font, args.font_output, figure_text(data))
    if not args.font_output.is_file():
        parser.error(
            "font subset is missing; provide --source-font with a Noto CJK OTF"
        )
    missing = missing_font_characters(args.font_output, figure_text(data))
    if missing:
        instruction = (
            "regenerate it with --source-font"
            if args.source_font is None
            else "the supplied source font does not cover the required text"
        )
        parser.error(
            "font subset lacks required glyphs: "
            f"{describe_characters(missing)}; {instruction}"
        )
    try:
        validate_text_layout(data, args.font_output)
    except ValueError as exc:
        parser.error(f"formal-figure text-layout validation failed: {exc}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    font_bytes = args.font_output.read_bytes()
    for figure in data.get("figures", []):
        number = int(figure["number"])
        svg_path = args.output_dir / f"figure-{number}.svg"
        png_path = args.output_dir / f"figure-{number}.png"
        svg_path.write_text(render_svg(figure, font_bytes), encoding="utf-8")
        render_png(figure, args.font_output, png_path)
        print(svg_path)
        print(png_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
