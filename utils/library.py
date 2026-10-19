"""Build and serve the GISD reference library: a single HTML page for finding and collecting PDFs.

The page (`references.html`, next to the PDFs) holds one entry per GISD reference with search
links, the PDF filename to save it as, whether that PDF is present, and the URL it came from.
The reference data is embedded in the page as JSON, so the page itself is the manifest that
`batch.py` and `eval/gisd_eval.py` read.

    uv run utils/library.py build --gisd gisd_data/gisd_clean.csv --output gisd_data/references.html
    uv run utils/library.py serve gisd_data/references.html     # live availability + fetch from URL
    uv run utils/library.py download gisd_data/references.html  # check saved URLs, fetch missing PDFs
    uv run utils/library.py mark gisd_data/references.html lever_2005.pdf --by ai --source URL

Opened directly from disk the page shows availability as of the last build or save. Served, it
checks the folder live and downloads a PDF into it when you enter the URL it can be found at.
Each source URL is marked by whether it actually downloaded a PDF (`source_ok`), so the page
can show which PDFs could be re-collected automatically. References the researcher could not find
can be marked `unavailable` from the served page. Each searched reference (PDF present or marked
unavailable) records who searched for it in `collected_by`: `human` for the page and PDFs saved
by hand, `ai` for an AI assistant recording its results with `mark`. Rebuilding keeps each
reference's filename, source URL and marks, so the page can be regenerated
whenever GISD changes. Standard library only, so eval/ can import `load_library`.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import threading
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TEMPLATE = Path(__file__).with_name("library_template.html")
DATA_RE = re.compile(r'(<script id="library-data" type="application/json">)(.*?)(</script>)', re.S)
CAT_SEVERITY = {"MV": 5, "MR": 4, "MO": 3, "MN": 2, "MC": 1, "DD": 0}
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s,;\"<>]+")
URL_RE = re.compile(r"https?://[^\s\"<>]+")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
MAX_PDF_BYTES = 200 * 1024 * 1024


# ── filenames ─────────────────────────────────────────────────────────────────


def pdf_stem(reference: str) -> str:
    """first_author_year, e.g. 'Lever C (2005) ...' -> 'lever_2005'."""
    surname = re.match(r"^([A-Za-z'][A-Za-z'-]+)", reference)
    year = re.search(r"\b(19|20)\d{2}\b", reference)
    return f"{surname.group(1).lower() if surname else 'unknown'}_{year.group() if year else 'unknown'}"


def suffix(i: int) -> str:
    """0 -> 'a', 25 -> 'z', 26 -> 'aa', ..."""
    label, n = "", i + 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        label = chr(ord("a") + r) + label
    return label


def assign_filenames(refs: list[str], existing: dict[str, str]) -> dict[str, str]:
    """Keep existing names; give new references first_author_year.pdf, suffixed (_a, _b, ...)
    when several references share it, so each PDF maps to exactly one reference."""
    names = {r: existing[r] for r in refs if r in existing}
    taken = set(names.values())
    stem_counts = Counter(pdf_stem(r) for r in refs)
    for ref in refs:
        if ref in names:
            continue
        stem = pdf_stem(ref)
        name, i = f"{stem}.pdf", 0
        if stem_counts[stem] > 1 or name in taken:
            while (name := f"{stem}_{suffix(i)}.pdf") in taken:
                i += 1
        names[ref] = name
        taken.add(name)
    return names


# ── page I/O ──────────────────────────────────────────────────────────────────


def read_data(page: Path) -> dict:
    match = DATA_RE.search(page.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"{page} has no embedded library data")
    return json.loads(match.group(2))


def write_page(page: Path, data: dict) -> None:
    """Render the template with `data` embedded, refreshing each entry's availability."""
    for entry in data["references"]:
        entry["available"] = (page.parent / entry["file"]).is_file()
        searched = entry["available"] or entry.get("unavailable")
        # unmarked searched entries were collected by hand (e.g. a PDF saved straight into the folder)
        entry["collected_by"] = (entry.get("collected_by") or "human") if searched else None
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    payload = json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")
    html = DATA_RE.sub(lambda m: m.group(1) + payload + m.group(3), TEMPLATE.read_text(encoding="utf-8"))
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(html, encoding="utf-8")


def load_library(page: Path) -> list[dict]:
    """Entries of a library page, with `available` checked against the PDFs next to it now."""
    entries = read_data(page)["references"]
    for entry in entries:
        entry["available"] = (page.parent / entry["file"]).is_file()
    return entries


# ── build ─────────────────────────────────────────────────────────────────────


def build(gisd: Path, output: Path) -> None:
    with open(gisd, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("Reference") or "").strip()]
    by_ref: dict[str, list[dict]] = {}
    for row in rows:
        by_ref.setdefault(row["Reference"].strip(), []).append(row)
    refs = sorted(by_ref)

    previous = {e["reference"]: e for e in read_data(output)["references"]} if output.exists() else {}
    names = assign_filenames(refs, {r: e["file"] for r, e in previous.items()})

    entries = []
    for ref in refs:
        group = by_ref[ref]
        doi = DOI_RE.search(ref)
        url = URL_RE.search(ref)
        entries.append({
            "reference": ref,
            "file": names[ref],
            "species": sorted({r["Species"] for r in group if r["Species"]}),
            "categories": sorted({r["EICAT Category"] for r in group if r["EICAT Category"]}, key=lambda c: -CAT_SEVERITY.get(c, 0)),
            "mechanisms": [m for m, _ in Counter(r["Impact mechanism"] for r in group if r["Impact mechanism"]).most_common()],
            "doi": doi.group().rstrip(".)") if doi else None,
            "url": url.group().rstrip(".,);") if url else None,
            "source": previous.get(ref, {}).get("source"),
            "source_ok": previous.get(ref, {}).get("source_ok"),
            "unavailable": previous.get(ref, {}).get("unavailable", False),
            "collected_by": previous.get(ref, {}).get("collected_by"),
        })  # fmt: skip

    write_page(output, {"gisd": gisd.name, "references": entries})
    new, dropped = len(set(by_ref) - set(previous)), len(set(previous) - set(by_ref))
    available = sum(e["available"] for e in entries)
    print(f"References: {len(entries):,}  ({available:,} PDFs present, {new:,} new, {dropped:,} no longer in GISD)")
    print(f"Saved:      {output}")


# ── downloading ───────────────────────────────────────────────────────────────


def fetch_pdf(url: str) -> bytes:
    """Download `url`, refusing anything that is not a PDF (e.g. a paywall page)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read(MAX_PDF_BYTES + 1)
        content_type = response.headers.get("Content-Type", "unknown")
    if not body.startswith(b"%PDF"):
        raise ValueError(f"not a PDF (got {content_type}); the URL may be a landing or login page, try the direct PDF link")
    if len(body) > MAX_PDF_BYTES:
        raise ValueError("larger than 200 MB")
    return body


def download(page: Path) -> None:
    """Try every saved source URL: record whether it gives a PDF, and save it where the PDF is missing.
    PDFs already in the folder are never overwritten."""
    data = read_data(page)
    todo = [e for e in data["references"] if e.get("source")]
    print(f"Checking {len(todo)} saved source URLs")
    for entry in todo:
        dest = page.parent / entry["file"]
        try:
            body = fetch_pdf(entry["source"])
            entry["source_ok"] = True
            if dest.is_file():
                print(f"  ok      {entry['file']} (already present, kept)")
            else:
                dest.write_bytes(body)
                print(f"  saved   {entry['file']}")
        except Exception as e:  # report and carry on with the rest
            entry["source_ok"] = False
            print(f"  failed  {entry['file']}: {e}")
    write_page(page, data)


def mark(page: Path, file: str, by: str, unavailable: bool, source: str | None, blocked: bool = False) -> None:
    """Record a search result for one reference: its PDF (already saved next to the page) and
    the URL it came from, or that it could not be found. `blocked` records a URL where the PDF was
    located but could not be downloaded automatically, leaving the reference for a human to fetch."""
    data = read_data(page)
    entry = next((e for e in data["references"] if e["file"] == file), None)
    if entry is None:
        raise SystemExit(f"{file} is not in the library")
    if blocked:
        if not source:
            raise SystemExit("--blocked needs --source")
        entry["source"], entry["source_ok"], entry["unavailable"] = source, False, False
        write_page(page, data)
        print(f"{file}: located at {source} but not downloadable, left for a human")
        return
    if not unavailable and not (page.parent / file).is_file():
        raise SystemExit(f"{file} is not in {page.parent}; save the PDF first or pass --unavailable")
    entry["unavailable"], entry["collected_by"] = unavailable, by
    if source:
        entry["source"], entry["source_ok"] = source, True
    write_page(page, data)
    print(f"{file}: {'unavailable' if unavailable else 'available'}, collected by {by}")


# ── serve ─────────────────────────────────────────────────────────────────────


def make_handler(page: Path):
    lock = threading.Lock()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(page.parent), **kwargs)

        def send_json(self, status: HTTPStatus, body: dict) -> None:
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/":
                self.send_response(HTTPStatus.FOUND)
                self.send_header("Location", "/" + urllib.parse.quote(page.name))
                self.end_headers()
            elif path == "/api/files":
                self.send_json(HTTPStatus.OK, {"files": sorted(p.name for p in page.parent.glob("*.pdf"))})
            else:
                super().do_GET()

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
            if path == "/api/source":
                self.set_source(body)
            elif path == "/api/unavailable":
                self.set_unavailable(body)
            else:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def set_unavailable(self, body: dict) -> None:
            with lock:
                data = read_data(page)
                entry = next((e for e in data["references"] if e["file"] == body.get("file")), None)
                if entry is None:
                    return self.send_json(HTTPStatus.NOT_FOUND, {"error": f"{body.get('file')} is not in the library"})
                entry["unavailable"] = bool(body.get("unavailable"))
                entry["collected_by"] = "human" if entry["unavailable"] else None
                write_page(page, data)
            self.send_json(HTTPStatus.OK, {"unavailable": entry["unavailable"], "collected_by": entry["collected_by"]})

        def set_source(self, body: dict) -> None:
            file, url = body.get("file"), (body.get("url") or "").strip()
            if url and urllib.parse.urlparse(url).scheme not in ("http", "https"):
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "enter an http(s) URL"})
            with lock:
                data = read_data(page)
                entry = next((e for e in data["references"] if e["file"] == file), None)
                if entry is None:
                    return self.send_json(HTTPStatus.NOT_FOUND, {"error": f"{file} is not in the library"})
                entry["source"], entry["source_ok"] = url or None, None
                error = None
                if url:
                    try:
                        (page.parent / file).write_bytes(fetch_pdf(url))
                        entry["source_ok"], entry["collected_by"] = True, "human"
                    except Exception as e:
                        entry["source_ok"], error = False, str(e)
                write_page(page, data)
            self.send_json(HTTPStatus.OK, {
                "available": (page.parent / file).is_file(), "source": entry["source"], "source_ok": entry["source_ok"],
                "collected_by": entry["collected_by"], "error": error,
            })  # fmt: skip

        def log_message(self, format, *args):
            if not self.path.startswith("/api/files"):
                super().log_message(format, *args)

    return Handler


def serve(page: Path, port: int) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(page.resolve()))
    print(f"Serving {page} at http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build", help="Create or refresh the library page from the cleaned GISD CSV.")
    p.add_argument("--gisd", type=Path, required=True, help="Cleaned GISD CSV (filter_clean.py output)")
    p.add_argument("--output", type=Path, required=True, help="Library page to write, in the folder the PDFs go in")
    p = sub.add_parser("serve", help="Serve the page with live availability and download-from-URL.")
    p.add_argument("page", type=Path)
    p.add_argument("--port", type=int, default=8765)
    p = sub.add_parser("download", help="Check every saved source URL and download the PDFs that are missing.")
    p.add_argument("page", type=Path)
    p = sub.add_parser("mark", help="Record who searched for a reference and whether its PDF was found.")
    p.add_argument("page", type=Path)
    p.add_argument("file", help="The reference's PDF filename")
    p.add_argument("--by", choices=["human", "ai"], required=True)
    p.add_argument("--unavailable", action="store_true", help="The PDF could not be found")
    p.add_argument("--source", help="URL the PDF was downloaded from")
    p.add_argument("--blocked", action="store_true", help="The PDF is at --source but couldn't be downloaded; leave it for a human")
    args = parser.parse_args()

    if args.command == "build":
        build(args.gisd, args.output)
    elif args.command == "serve":
        serve(args.page, args.port)
    elif args.command == "download":
        download(args.page)
    else:
        mark(args.page, args.file, args.by, args.unavailable, args.source, args.blocked)


if __name__ == "__main__":
    main()
