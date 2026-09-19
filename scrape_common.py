#!/usr/bin/env python3
"""Shared DB + storage helpers for Amazon / BuyWhere / Shopee / Lazada importers."""

from __future__ import annotations

import os
import re
import sqlite3
import time
from datetime import datetime
from urllib.parse import quote, urlencode

import requests

DB_PATH = "./diskprices.db"

# Shared HDD/SSD keyword list (same as Amazon scraper).
STORAGE_QUERIES = [
    "internal hard drive",
    "internal hdd",
    "wd gold",
    "wd red",
    "wd red plus",
    "wd red pro",
    "wd purple",
    "wd purple pro",
    "wd blue",
    "wd black",
    "seagate barracuda",
    "seagate ironwolf",
    "seagate ironwolf pro",
    "seagate skyhawk",
    "seagate skyhawk ai",
    "seagate exos",
    "toshiba n300",
    "toshiba x300",
    "enterprise hard drive",
    "enterprise sas",
    "nas hard drive",
    "nas hdd",
    "external hard drive",
    "external hdd",
    "portable hard drive",
    "wd elements",
    "wd my book",
    "wd my passport",
    "seagate expansion",
    "seagate one touch",
    "toshiba canvio",
    "internal ssd",
    "nvme ssd",
    "m.2 ssd",
    "sata ssd",
    "samsung 870",
    "samsung 870 evo",
    "samsung 870 qvo",
    "samsung 980",
    "samsung 990",
    "samsung 990 pro",
    "crucial mx500",
    "crucial p3",
    "crucial p3 plus",
    "crucial t500",
    "wd blue ssd",
    "wd black sn850x",
    "wd black sn770",
    "kingston nv2",
    "kingston kc3000",
    "kingston nv3",
    "external ssd",
    "portable ssd",
    "samsung t5",
    "samsung t7",
    "samsung t7 shield",
    "samsung t9",
    "sandisk extreme",
    "sandisk extreme pro",
    "hard drive",
    "ssd",
]


# Absurd $/TB floor (SGD). Empty enclosures / fake high-TB listings often
# land well under ~S$5/TB. Typical new enterprise HDD floors on Amazon.sg
# are ~S$15+/TB; S$4 leaves headroom for deep used/refurb deals. Only
# applied to claims of 4TB+ so small legitimate SSDs/HDDs are untouched.
ABSURD_MIN_COST_PER_TB_SGD = 4.0
ABSURD_MIN_CAPACITY_TB = 4.0


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT UNIQUE NOT NULL,
        image_url TEXT,
        price REAL NOT NULL,
        original_price REAL,
        capacity_gb REAL NOT NULL,
        capacity_tb REAL NOT NULL,
        is_ssd BOOLEAN NOT NULL,
        cost_per_tb REAL NOT NULL,
        rating REAL DEFAULT 0,
        review_count INTEGER DEFAULT 0,
        seller TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )""")
    # Existing checked-in DBs predate first_seen/last_seen/is_active;
    # CREATE TABLE IF NOT EXISTS will not add columns to an old schema.
    cols = {row[1] for row in c.execute("PRAGMA table_info(products)")}
    for name, decl in (
        ("first_seen", "TIMESTAMP"),
        ("last_seen", "TIMESTAMP"),
        ("is_active", "BOOLEAN DEFAULT 1"),
    ):
        if name not in cols:
            c.execute(f"ALTER TABLE products ADD COLUMN {name} {decl}")
            print(f"Migrated products: added column {name}")
    c.execute("""UPDATE products SET first_seen = COALESCE(first_seen, timestamp, CURRENT_TIMESTAMP)
                 WHERE first_seen IS NULL""")
    c.execute("""UPDATE products SET last_seen = COALESCE(last_seen, timestamp, CURRENT_TIMESTAMP)
                 WHERE last_seen IS NULL""")
    c.execute("""UPDATE products SET is_active = COALESCE(is_active, 1)
                 WHERE is_active IS NULL""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_url ON products(url)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_capacity ON products(capacity_tb)")
    conn.commit()
    conn.close()


def parse_capacity(title):
    tl = title.lower()
    m = re.search(r'(\d+(?:\.\d+)?)\s*tb(?!w)', tl)
    if m:
        tb = float(m.group(1))
        return tb * 1000, tb
    m = re.search(r'(\d+(?:\.\d+)?)\s*gb(?!w)', tl)
    if m:
        gb = float(m.group(1))
        return gb, gb / 1000
    return 0, 0


def is_ssd(title):
    tl = title.lower()
    for kw in ['ssd', 'solid state', 'nvme', 'm.2', 'pcie']:
        if kw in tl:
            return True
    for kw in ['hdd', 'hard drive', 'hard disk', 'mechanical']:
        if kw in tl:
            return False
    return False



# --- Interface / protocol tags (diskprices.com-style) ---
#
# Emitted into data/products.json by export_json.py.
# `protocols`: all matched tags in stable canonical order.
# `protocol`: single primary for UI filters / badges.
#
# Primary preference when multiple match (first wins):
#   NVMe > SAS > PCIe > SATA > Thunderbolt > USB > M.2
# Rationale:
#   - NVMe implies PCIe; prefer NVMe when both appear in the title.
#   - SAS > SATA for enterprise dual-protocol wording.
#   - Thunderbolt > USB when a drive lists both (e.g. TB3 + USB-C).
#   - M.2 is a form-factor; keep it in `protocols` alongside NVMe/SATA/PCIe,
#     but use M.2 as primary only when no bus protocol was inferred.
#
# False-positive notes:
#   - Never treat bare "TB" capacity as Thunderbolt (require thunderbolt / tb3 / tb4).
#   - USB4 is grouped with Thunderbolt (common portable-SSD marketing).

PROTOCOL_TAGS = ("NVMe", "SAS", "PCIe", "SATA", "Thunderbolt", "USB", "M.2")

# Detection patterns (title, case-insensitive). Order of checks does not
# affect emission order — PROTOCOL_TAGS is the stable array order.
_PROTOCOL_PATTERNS = {
    "NVMe": re.compile(r"\bnvme\b", re.I),
    "SAS": re.compile(r"\bsas\b", re.I),
    "PCIe": re.compile(r"\bpcie\b|\bpci-e\b|\bpci\s*express\b", re.I),
    "SATA": re.compile(r"\bsata(?:\b|[\s\-]?[0-9])|serial\s*ata", re.I),
    # thunderbolt / tb3 / tb4 / usb4 — not bare "TB" (capacity).
    "Thunderbolt": re.compile(
        r"thunderbolt|\btb\s*[34]\b|\btb[34]\b|\busb[\s-]?4\b", re.I
    ),
    # usb / usb-c / usb3.0 / … (usb4 also matches; both tags may appear).
    "USB": re.compile(r"\busb(?:\b|[\s\-]?[0-9a-z])", re.I),
    # m.2 / m2 / m-2 form factor (avoid matching mid-token like "1M2").
    "M.2": re.compile(r"\bm\.2\b|\bm-2\b|(?<![a-z0-9])m2(?![a-z0-9])", re.I),
}


def infer_protocols(title: str, asin: str | None = None) -> list[str]:
    """Infer interface/protocol tags from a product title.

    Optional ``asin`` is reserved for future heuristics; unused for now.
    Returns matched tags in stable ``PROTOCOL_TAGS`` order.
    """
    if not title:
        return []
    # asin reserved for clearly useful ASIN heuristics (none yet).
    _ = asin
    found: set[str] = set()
    for tag, pat in _PROTOCOL_PATTERNS.items():
        if pat.search(title):
            found.add(tag)
    return [tag for tag in PROTOCOL_TAGS if tag in found]


def primary_protocol(protocols) -> str:
    """Pick UI primary protocol from an ``infer_protocols`` result.

    Preference: NVMe > SAS > PCIe > SATA > Thunderbolt > USB > M.2.
    Empty string when nothing matched.
    """
    if not protocols:
        return ""
    have = set(protocols)
    for tag in PROTOCOL_TAGS:
        if tag in have:
            # M.2 is last in PROTOCOL_TAGS — only chosen if nothing else matched.
            return tag
    return ""


KNOWN_ACCESSORY_ASINS = frozenset({
    "B0BV5V4TVS",  # MAIWO enclosure + SD/CD box reader
    "B0BJV2Q8JD",  # MAIWO enclosure
    "B08RVC6F9Y",  # Sabrent enclosure
    "B0GRVR1WDM",  # Hard drive enclosure
    "B07Y9BLTBP",  # UGREEN HDD case
    "B0F9W6HHGL",  # Crucial SSD carrying case
    "B0G532FXPV",  # SanDisk case
    "B0GGYLC272",  # T7/Passport case
    "B0F594GGD9",  # Capacity sticker labels / tray caddy
    "B09NN1MMDY",  # Kurojin SSD/HDD stand + cloner
    "B0BDLZQCJY",  # M.2 docking station / adapter
    "B0GK746VBQ",  # SSK cloner / dual bay dock
})


def _asin_from_url(url: str) -> str | None:
    m = re.search(r"/dp/([A-Z0-9]{10})", url or "", re.I)
    return m.group(1).upper() if m else None


def is_real_storage(title):
    """Return True only for actual HDD/SSD products (not accessories).

    Prefer phrase / word-boundary denies so short tokens like box/bay/cable do
    not false-negative real drives (WD My Book, multi-bay NAS, cable-included
    SSDs, Xbox game drives). Stale accessory rows are also purged on export.
    """
    t = title.lower()
    if not re.search(r'\d+\s*tb|\d+\s*gb', t):
        return False

    strong = bool(re.search(
        r'\b(hdd|ssds?|nvme|hard\s*drives?|hard\s*disks?|solid\s*state)\b', t
    ))

    always_deny = [
        r'\benclosure\b',
        r'\bdock(?:ing)?(?:\s*station)?\b',
        r'\bcaddy\b',
        r'\bclon(?:e|er|ing)\b',
        r'\bduplicator\b',
        r'\bcard\s*reader\b',
        r'\busb\s*flash(?:\s*drive)?\b',
        r'\bflash\s*drive\b',
        r'\bpendrive\b',
        r'\bpen\s*drive\b',
        r'\bthumb\s*drive\b',
        r'\bmemory\s*stick\b',
        r'\bmicrosd\b',
        r'\bmicro[\s-]?sd\b',
        r'\bsd\s*cards?\b',
        r'\bmemory\s*cards?\b',
        r'\btf\s*cards?\b',
        r'\bddr[345]\b',
        r'\b(?:so)?dimm\b',
        r'\boptical\b',
        r'\b(?:dvd|blu-?ray)\b',
        r'\bcarrying\s*case\b',
        r'\bstorage\s*case\b',
        r'\btravel\s*case\b',
        r'\bhdd\s*case\b',
        r'\bhard\s*drive\s*case\b',
        r'\bcase\s*compatible\b',
        r'\bpouch\b',
        r'\bsleeve\b',
        r'\bsticker\b',
        r'\blabel\b',
        r'\bdecal\b',
        r'\bhdd\s*stand\b',
        r'\b(?:ssd\s*/\s*hdd|hdd\s*/\s*ssd)\s*stand\b',
        r'\bmounting\s*kit\b',
        r'\binstallation\s*kit\b',
        r'\bbracket\s*kit\b',
        r'\btool\s*kit\b',
        r'\bhdd\s*enclosure\b',
        r'\bprotector\b',
        r'\bskin\b',
        r'\bwrap\b',
        r'\btray\b',
        r'\brail\b',
        r'\bbracket\b',
        r'\bconverter\b',
        r'\b(?:sata|nvme|m\.2|hdd|ssd)\s+to\s+usb\b',
        r'\bto\s+usb[\s-]*c?\s*adapter\b',
    ]
    if any(re.search(p, t) for p in always_deny):
        return False

    if not strong:
        ambiguous = [
            r'\bbox\b',
            r'\bbay\b',
            r'\bcable\b',
            r'\bcase\b',
            r'\bstand\b',
            r'\bbag\b',
            r'\bcover\b',
            r'\bmount\b',
            r'\bheatsink\b',
            r'\bcooler\b',
            r'\badapter\b',
        ]
        if any(re.search(p, t) for p in ambiguous):
            return False

    storage_kw = [
        'hdd', 'hard drive', 'hard disk', 'ssd', 'solid state', 'nvme',
        'sata', 'storage', 'internal', 'external', 'portable', 'desktop',
        'enterprise', 'nas', 'data center', 'server', 'drive',
    ]
    return any(kw in t for kw in storage_kw)


def deactivate_non_storage(conn: sqlite3.Connection | None = None) -> int:
    """Mark accessory / non-storage rows inactive. Returns rows deactivated."""
    own = conn is None
    if own:
        conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, title, url, COALESCE(is_active, 1) FROM products')
    deactivated = 0
    for row_id, title, url, active in c.fetchall():
        if not active:
            continue
        asin = _asin_from_url(url)
        drop = (asin in KNOWN_ACCESSORY_ASINS) or (not is_real_storage(title or ''))
        if drop:
            c.execute('UPDATE products SET is_active=0 WHERE id=?', (row_id,))
            deactivated += 1
    conn.commit()
    if own:
        conn.close()
    return deactivated




def process_products(items, default_platform='Amazon.sg', default_seller=None):
    """Filter raw items into storage products. Platform/seller may come from item."""
    products = []
    seen = set()
    seller_fallback = default_seller if default_seller is not None else default_platform
    for item in items:
        title = item.get('title', '')
        price = item.get('price', 0) or 0
        url = item.get('url', '')
        if price <= 0 or not url or url in seen:
            continue
        if not is_real_storage(title):
            continue
        cap_gb, cap_tb = parse_capacity(title)
        if cap_tb <= 0:
            continue
        cost_per_tb = price / cap_tb if cap_tb > 0 else 0
        # Cheap $/TB sanity: absurd high-TB @ tiny price (empty enclosure / fake).
        if (
            cap_tb >= ABSURD_MIN_CAPACITY_TB
            and cost_per_tb < ABSURD_MIN_COST_PER_TB_SGD
        ):
            continue
        seen.add(url)
        platform = item.get('platform') or default_platform
        seller = item.get('seller') or seller_fallback
        original = item.get('original_price')
        if original is None or original <= 0:
            original = price
        products.append({
            'platform': platform,
            'title': title,
            'url': url,
            'image_url': item.get('image_url', '') or '',
            'price': price,
            'original_price': original,
            'capacity_gb': cap_gb,
            'capacity_tb': cap_tb,
            'is_ssd': is_ssd(title),
            'cost_per_tb': cost_per_tb,
            'seller': seller,
        })
    return products


def save_products(products):
    """Upsert products. Always migrates schema first (defensive for Actions DB).

    Callers should still invoke init_db() early, but save_products must not
    assume that — run https://github.com/Kytosyn/amazon-sg-price-tracker/actions/runs/35431766074
    crashed with OperationalError when INSERT used first_seen on an old
    checked-in diskprices.db after CREATE TABLE IF NOT EXISTS no-oped.
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        for p in products:
            try:
                c.execute(
                    """INSERT INTO products
                    (platform,title,url,image_url,price,original_price,capacity_gb,capacity_tb,is_ssd,cost_per_tb,seller,timestamp,first_seen,last_seen,is_active)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (
                        p["platform"],
                        p["title"],
                        p["url"],
                        p["image_url"],
                        p["price"],
                        p["original_price"],
                        p["capacity_gb"],
                        p["capacity_tb"],
                        p["is_ssd"],
                        p["cost_per_tb"],
                        p["seller"],
                        now,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError:
                c.execute(
                    """UPDATE products SET price=?, original_price=?, cost_per_tb=?,
                       timestamp=?, last_seen=?, is_active=1 WHERE url=?""",
                    (p["price"], p["original_price"], p["cost_per_tb"], now, now, p["url"]),
                )
        conn.commit()
    except sqlite3.OperationalError as e:
        cols = {row[1] for row in c.execute("PRAGMA table_info(products)")}
        raise sqlite3.OperationalError(
            f"{e}; DB={DB_PATH!r} columns={sorted(cols)}. "
            "Call init_db() (or use this save_products) so first_seen/last_seen/is_active exist."
        ) from e
    finally:
        conn.close()


# --- Proxy helpers (shared by Amazon / Shopee / Lazada scrapers) ---


def proxied_url(url: str, *, mode: str | None = None, extra_params: dict | None = None) -> str:
    """Optional ScraperAPI / ZenRows / custom proxy prefix via env (Amazon pattern).

    ``mode="auto"`` uses ZenRows Adaptive Stealth (do not also pass js_render /
    premium_proxy — ZenRows manages those). Amazon keeps the classic
    ``premium_proxy=true`` path when mode is unset.
    """
    scraperapi = os.environ.get("SCRAPERAPI_KEY", "").strip()
    if scraperapi:
        return (
            f"http://api.scraperapi.com?api_key={quote(scraperapi)}"
            f"&url={quote(url, safe='')}&country_code=sg"
        )
    zenrows = os.environ.get("ZENROWS_API_KEY", "").strip()
    if zenrows:
        params: dict[str, str] = {
            "apikey": zenrows,
            "url": url,
        }
        if mode == "auto":
            params["mode"] = "auto"
        else:
            params["premium_proxy"] = "true"
        if extra_params:
            for k, v in extra_params.items():
                if v is None:
                    continue
                # Avoid conflicting with Adaptive Stealth managed knobs.
                if mode == "auto" and k in ("js_render", "premium_proxy"):
                    continue
                params[str(k)] = str(v)
        return f"https://api.zenrows.com/v1/?{urlencode(params)}"
    return url


def using_proxy() -> bool:
    return bool(
        os.environ.get("SCRAPERAPI_KEY", "").strip()
        or os.environ.get("ZENROWS_API_KEY", "").strip()
    )


def zenrows_get(
    session: requests.Session,
    url: str,
    *,
    headers: dict | None = None,
    timeout: int = 60,
    retries: int = 3,
    extra_params: dict | None = None,
    mode: str | None = None,
) -> requests.Response | None:
    """GET ``url`` through ZenRows/ScraperAPI when configured, else direct.

    Amazon callers omit mode and keep ``premium_proxy=true``. Shopee prefers
    explicit ``js_render`` / ``json_response`` / ``custom_headers`` via
    ``extra_params`` (``mode=auto`` on the search API returned RESP001).
    Pass target headers here; with ``custom_headers=true`` ZenRows forwards
    them to the destination URL.
    """
    target = proxied_url(url, mode=mode, extra_params=extra_params)
    last_err = None
    for attempt in range(retries):
        try:
            resp = session.get(target, headers=headers or {}, timeout=timeout)
            if resp.status_code in (429, 503):
                time.sleep((attempt + 1) * 5)
                continue
            return resp
        except Exception as e:
            last_err = e
            time.sleep((attempt + 1) * 3)
    if last_err:
        print(f"  zenrows_get failed for {url[:80]}…: {last_err}")
    return None


def zenrows_quota_exceeded(resp: requests.Response | None) -> bool:
    """True when ZenRows returns AUTH004 / HTTP 402 usage exceeded."""
    if resp is None:
        return False
    if resp.status_code == 402:
        return True
    text = (resp.text or "")[:400]
    return "AUTH004" in text or "usage limit" in text.lower() or "Usage exceeded" in text


def sea_soft_exit(message: str) -> None:
    """Log ERROR then soft-exit (0) for SEA scrapers in the first week.

    Amazon remains hard-fail. Set SEA_SOFT_FAIL=0 to harden Shopee/Lazada later.
    """
    print(f"ERROR: {message}")
    soft = os.environ.get("SEA_SOFT_FAIL", "1").strip().lower() not in ("0", "false", "no")
    if soft:
        print(
            "SEA soft-fail: exiting 0 so Amazon export can still ship "
            "(set SEA_SOFT_FAIL=0 to harden)."
        )
        raise SystemExit(0)
    raise SystemExit(1)
