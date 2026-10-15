"""Validate source-linked crosswalk data and render its static reading page."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "crosswalk.json"
PAGE = ROOT / "index.html"
STATUSES = {"proposal", "guidance", "roadmap", "draft", "licensed_published", "voluntary", "regulation"}
SCHEMA_PINS = (
    {
        "name": "Aviation ML Assurance Card",
        "file": "aviation-ml-card.schema.json",
        "commit": "e90bc740afa8588431d6be51b8667ef32e414557",
        "sha256": "2d8b05ad494edef96ca663539c4d31d66b9412947846973f6e698e3b468d8d34",
    },
    {
        "name": "MRO AI Sign-off Card",
        "file": "mro-ai-signoff-card.schema.json",
        "commit": "09095ea2bd1c0abd9fe8454be743711fcc835912",
        "sha256": "c9572c0ea4175679021c33ffa232dc244435159323c67c5eb91cc734418ae4da",
    },
)


def load_data() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def load_pinned_schemas() -> dict[str, dict]:
    """Read checked-in upstream schemas only after verifying their pinned bytes."""
    schemas = {}
    for pin in SCHEMA_PINS:
        raw = (ROOT / "schemas" / pin["file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != pin["sha256"]:
            raise ValueError(f"Pinned schema hash mismatch: {pin['name']}")
        schema = json.loads(raw)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or not isinstance(schema.get("properties"), dict):
            raise ValueError(f"Unsupported pinned schema: {pin['name']}")
        schemas[pin["name"]] = schema
    return schemas


def field_path_exists(schema: dict, path: str) -> bool:
    """Follow explicit JSON Schema properties; unsupported compositions fail closed."""
    node = schema
    for segment in path.split("."):
        properties = node.get("properties")
        if not isinstance(properties, dict) or segment not in properties:
            return False
        node = properties[segment]
        if not isinstance(node, dict):
            return False
    return True


def validate_field_paths(paths: list[str], schemas: dict[str, dict], row_id: str) -> None:
    if not isinstance(paths, list) or not paths or any(not isinstance(path, str) for path in paths):
        raise ValueError(f"Invalid field paths in row: {row_id}")
    if len(paths) != len(set(paths)):
        raise ValueError(f"Duplicate field path in row: {row_id}")
    for path in paths:
        if not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", path):
            raise ValueError(f"Invalid field path in row: {row_id}: {path}")
        root = path.split(".", 1)[0]
        owners = [schema for schema in schemas.values() if root in schema["properties"]]
        if len(owners) != 1 or not field_path_exists(owners[0], path):
            raise ValueError(f"Unknown or ambiguous field path in row: {row_id}: {path}")


def validate(data: dict, *, schemas: dict[str, dict] | None = None) -> None:
    schemas = load_pinned_schemas() if schemas is None else schemas
    if data.get("status") != "draft_informative" or not data.get("claim_boundary"):
        raise ValueError("Crosswalk must retain its draft status and claim boundary")
    date.fromisoformat(data["reviewed_on"])
    if not data.get("sources") or not data.get("rows"):
        raise ValueError("Sources and rows are required")

    source_ids: set[str] = set()
    for source in data["sources"]:
        source_id = source["id"]
        if source_id in source_ids or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source_id):
            raise ValueError(f"Duplicate or invalid source ID: {source_id}")
        source_ids.add(source_id)
        parsed = urlsplit(source["url"])
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError(f"Source requires an HTTPS public URL: {source_id}")
        if source["status"] not in STATUSES:
            raise ValueError(f"Unknown source status: {source_id}")
        if source["published_on"] is not None:
            date.fromisoformat(source["published_on"])
        for key in ("title", "publisher", "status_note"):
            if not source.get(key):
                raise ValueError(f"Missing source {key}: {source_id}")

    row_ids: set[str] = set()
    used_sources: set[str] = set()
    for row in data["rows"]:
        row_id = row["id"]
        if row_id in row_ids or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", row_id):
            raise ValueError(f"Duplicate or invalid row ID: {row_id}")
        row_ids.add(row_id)
        if row["source_id"] not in source_ids:
            raise ValueError(f"Unknown source in row: {row_id}")
        used_sources.add(row["source_id"])
        paths = row["field_paths"]
        validate_field_paths(paths, schemas, row_id)
        for key in ("title", "reference_id", "applicability", "connection", "limit"):
            if not row.get(key):
                raise ValueError(f"Missing row {key}: {row_id}")
    if source_ids != used_sources:
        raise ValueError(f"Unused sources: {sorted(source_ids - used_sources)}")


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def render(data: dict) -> str:
    validate(data)
    sources = {source["id"]: source for source in data["sources"]}
    articles = []
    for row in data["rows"]:
        source = sources[row["source_id"]]
        fields = ", ".join(f"<code>{escape(path)}</code>" for path in row["field_paths"])
        articles.append(
            f'<li id="{escape(row["id"])}"><article aria-labelledby="title-{escape(row["id"])}">'
            f'<p class="eyebrow">{escape(source["publisher"])} · {escape(source["status"].replace("_", " "))}</p>'
            f'<h3 id="title-{escape(row["id"])}">{escape(row["title"])}</h3>'
            f'<p><strong>Card fields:</strong> {fields}</p>'
            f'<p><strong>Reference:</strong> <a href="{escape(source["url"])}">{escape(row["reference_id"])} <span class="sr-only">at {escape(source["publisher"])}</span></a></p>'
            f'<p><strong>Applies when:</strong> {escape(row["applicability"])}</p>'
            f'<p><strong>Why linked:</strong> {escape(row["connection"])}</p>'
            f'<p class="limit"><strong>Limit:</strong> {escape(row["limit"])}</p>'
            "</article></li>"
        )
    source_items = []
    for source in data["sources"]:
        publication = source["published_on"] or "date not stated on linked page"
        source_items.append(
            f'<li><a href="{escape(source["url"])}">{escape(source["title"])}</a>'
            f' <span class="source-meta">{escape(source["publisher"])} · {escape(source["status"].replace("_", " "))} · {escape(publication)}</span>'
            f'<p>{escape(source["status_note"])}</p></li>'
        )

    checked_date = escape(data["reviewed_on"])
    checked_time = f'<time datetime="{checked_date}">{checked_date}</time>'

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <meta name="description" content="Draft aviation ML assurance disclosure crosswalk with source status and applicability notes.">
  <title>Aerospace assurance crosswalk | Kinetic Gain</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <a class="skip" href="#main">Skip to crosswalk</a>
  <header>
    <p class="brand">Kinetic Gain / Protocol Suite</p>
    <p class="eyebrow">Aerospace vertical · draft reference</p>
    <h1>Aerospace assurance crosswalk</h1>
    <p class="intro">A traceable map from proposed aviation card fields to public source topics. It helps reviewers ask better questions; it does not approve a system or maintenance release.</p>
    <p class="date">Source status checked """ + checked_time + """</p>
    <nav aria-label="Related resources" class="related"><a href="https://suite.kineticgain.com/">Protocol Suite</a><a href="https://github.com/mizcausevic-dev/aero-assurance-crosswalk">Source repository and data</a></nav>
  </header>
  <main id="main">
    <section aria-labelledby="boundary-heading" class="boundary">
      <h2 id="boundary-heading">What this map cannot prove</h2>
      <p>""" + escape(data["claim_boundary"]) + """</p>
      <p>EASA material here is proposed, the FAA roadmap is guidance for future methods, ED-324 is draft, NIST AI RMF is voluntary, and licensed aviation standards are referenced by identifier only. Every row states its scope and limit.</p>
    </section>
    <section aria-labelledby="map-heading">
      <h2 id="map-heading">Field-to-source map</h2>
      <p class="section-lede">These are review prompts. Follow the primary source and the applicable certification or maintenance process before making a real-world decision.</p>
      <ol class="rows">""" + "".join(articles) + """</ol>
    </section>
    <section aria-labelledby="source-heading" class="sources">
      <h2 id="source-heading">Source register</h2>
      <ol>""" + "".join(source_items) + """</ol>
    </section>
  </main>
  <footer><p>Draft reference · Original crosswalk content MIT licensed · External standards retain their publishers' terms.</p></footer>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail if index.html differs from rendered data")
    mode.add_argument("--write", action="store_true", help="regenerate index.html")
    args = parser.parse_args()
    content = render(load_data())
    if args.check:
        if not PAGE.exists() or PAGE.read_text(encoding="utf-8") != content:
            raise SystemExit("index.html is missing or stale; run --write")
        print("Crosswalk data valid; index.html matches source data")
    else:
        with PAGE.open("w", encoding="utf-8", newline="\n") as page:
            page.write(content)
        print("Rendered index.html")


if __name__ == "__main__":
    main()
