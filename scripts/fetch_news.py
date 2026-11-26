#!/usr/bin/env python3
"""Coleta as notícias do dia a partir dos feeds RSS/Atom em data/sources.json
e grava o resultado em data/news.json, que é lido pelo dashboard (index.html).

Só usa a biblioteca padrão do Python, então roda em qualquer runner sem instalar nada.

Uso:
    python scripts/fetch_news.py                 # coleta e grava data/news.json
    python scripts/fetch_news.py --max-age 72    # aceita notícias de até 72h
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources.json"
OUTPUT = ROOT / "data" / "news.json"

USER_AGENT = "Mozilla/5.0 (compatible; CafeEmCodigoNewsBot/1.0)"
TIMEOUT = 20
PER_FEED = 15        # itens lidos por feed
PER_CATEGORY = 30    # itens mantidos por categoria
SUMMARY_LEN = 260

ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"


def clean_text(raw: str | None, limit: int | None = None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        text = text[: limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return text


def parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = "&".join(
        p for p in parts.query.split("&") if p and not p.startswith(("utm_", "fbclid", "gclid"))
    )
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def find_image(item: ET.Element, html_blob: str) -> str | None:
    for tag in (f"{MEDIA}content", f"{MEDIA}thumbnail"):
        el = item.find(tag)
        if el is not None and el.get("url"):
            return el.get("url")
    enc = item.find("enclosure")
    if enc is not None and (enc.get("type") or "").startswith("image") and enc.get("url"):
        return enc.get("url")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', html_blob or "")
    return m.group(1) if m else None


def parse_feed(xml_bytes: bytes, feed: dict) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items: list[dict] = []

    if root.tag == f"{ATOM}feed":
        entries = root.findall(f"{ATOM}entry")
        for e in entries[:PER_FEED]:
            link = ""
            for l in e.findall(f"{ATOM}link"):
                if l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
                    break
            body = e.findtext(f"{ATOM}summary") or e.findtext(f"{ATOM}content") or ""
            items.append({
                "title": clean_text(e.findtext(f"{ATOM}title")),
                "link": link,
                "summary": clean_text(body, SUMMARY_LEN),
                "published": parse_date(e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated")),
                "image": find_image(e, body),
                "origin": None,
            })
    else:
        channel = root.find("channel")
        if channel is None:
            return []
        for it in channel.findall("item")[:PER_FEED]:
            body = it.findtext("description") or it.findtext(f"{CONTENT}encoded") or ""
            # Google Notícias informa o veículo original em <source>
            src = it.find("source")
            origin = clean_text(src.text) if src is not None and src.text else None
            title = clean_text(it.findtext("title"))
            if origin and title.endswith(f" - {origin}"):
                title = title[: -len(f" - {origin}")]
            summary = clean_text(body, SUMMARY_LEN)
            if "news.google.com" in feed["url"]:
                summary = ""  # a descrição do Google Notícias só repete o título
            items.append({
                "title": title,
                "link": (it.findtext("link") or "").strip(),
                "summary": summary,
                "published": parse_date(it.findtext("pubDate") or it.findtext(f"{DC}date")),
                "image": find_image(it, body),
                "origin": origin,
            })
    return [i for i in items if i["title"] and i["link"]]


def fetch(url: str, attempts: int = 3) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    })
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            # 429 (muitas requisições) e erros 5xx costumam ser passageiros: espera e tenta de novo
            if attempt == attempts - 1 or not (exc.code == 429 or exc.code >= 500):
                raise
            time.sleep(4 * (attempt + 1))
    raise RuntimeError("inalcançável")


def collect_feed(feed: dict) -> tuple[dict, list[dict], str | None]:
    try:
        return feed, parse_feed(fetch(feed["url"]), feed), None
    except Exception as exc:  # um feed com problema não derruba a coleta
        return feed, [], f"{type(exc).__name__}: {exc}"[:200]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age", type=int, default=48, help="idade máxima das notícias, em horas")
    args = ap.parse_args()

    config = json.loads(SOURCES.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=args.max_age)

    jobs = [(cat, feed) for cat in config["categories"] for feed in cat["feeds"]]
    google = [j for j in jobs if "news.google.com" in j[1]["url"]]
    others = [j for j in jobs if j not in google]

    def run_google() -> list:
        out = []
        for i, job in enumerate(google):  # um de cada vez, com pausa, para evitar o erro 429
            if i:
                time.sleep(2)
            out.append((job[0], *collect_feed(job[1])))
        return out

    with ThreadPoolExecutor(max_workers=8) as pool:
        google_future = pool.submit(run_google)
        other_results = list(pool.map(lambda job: (job[0], *collect_feed(job[1])), others))
        google_results = google_future.result()
    by_key = {(c["id"], f["url"]): r for r in google_results + other_results for c, f in [r[:2]]}
    results = [by_key[(c["id"], f["url"])] for c, f in jobs]

    # Se um feed falhar, reaproveita as notícias dele da coleta anterior (ainda dentro do prazo)
    previous: dict[tuple[str, str], list[dict]] = {}
    if OUTPUT.exists():
        try:
            old = json.loads(OUTPUT.read_text(encoding="utf-8"))
            for c in old.get("categories", []):
                for it in c.get("items", []):
                    previous.setdefault((c["id"], it.get("feed")), []).append(it)
        except (ValueError, KeyError):
            pass

    seen: set[str] = set()
    seen_titles: set[str] = set()
    out_categories = {c["id"]: {"id": c["id"], "label": c["label"], "items": []} for c in config["categories"]}
    source_status = []

    for cat, feed, items, error in results:
        kept = 0
        if error is not None:
            for old_item in previous.get((cat["id"], feed["name"]), []):
                pub = parse_date(old_item.get("published"))
                key = normalize_url(old_item["link"])
                if (pub and pub < cutoff) or key in seen:
                    continue
                seen.add(key)
                seen_titles.add(re.sub(r"\W+", "", old_item["title"].lower()))
                out_categories[cat["id"]]["items"].append(old_item)
                kept += 1
        for item in items:
            pub = item["published"]
            if pub and pub < cutoff:
                continue
            key = normalize_url(item["link"])
            tkey = re.sub(r"\W+", "", item["title"].lower())
            if key in seen or tkey in seen_titles:
                continue
            seen.add(key)
            seen_titles.add(tkey)
            out_categories[cat["id"]]["items"].append({
                "title": item["title"],
                "link": item["link"],
                "summary": item["summary"],
                "published": pub.isoformat() if pub else None,
                "image": item["image"],
                "source": item["origin"] or feed["name"],
                "feed": feed["name"],
                "lang": feed.get("lang", "pt"),
            })
            kept += 1
        source_status.append({
            "category": cat["id"],
            "name": feed["name"],
            "url": feed["url"],
            "lang": feed.get("lang", "pt"),
            "ok": error is None,
            "items": kept,
            "error": error,
        })
        status = "ok " if error is None else "ERR"
        print(f"[{status}] {cat['id']:<10} {feed['name']:<45} {kept:>3} itens {error or ''}", file=sys.stderr)

    for c in out_categories.values():
        c["items"].sort(key=lambda i: i["published"] or "", reverse=True)
        c["items"] = c["items"][:PER_CATEGORY]

    total = sum(len(c["items"]) for c in out_categories.values())
    if total == 0 and OUTPUT.exists():
        print("Nenhuma notícia coletada; mantendo o arquivo anterior.", file=sys.stderr)
        return 1

    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "max_age_hours": args.max_age,
        "categories": list(out_categories.values()),
        "sources": source_status,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{total} notícias gravadas em {OUTPUT.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
