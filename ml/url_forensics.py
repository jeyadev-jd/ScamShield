"""Lexical URL forensics (contribution C4).

Links are never fetched or resolved. Everything is judged from the spelling
of the URL alone, which is what a phone user sees before tapping.

    >>> analyze_url("http://sbi-kyc.xyz/login")["lookalike_of"]
    'sbi.co.in'
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

# Official domains of brands commonly impersonated in Indian SMS scams.
BRANDS: dict[str, str] = {
    "sbi": "sbi.co.in", "onlinesbi": "onlinesbi.sbi", "yono": "sbi.co.in", "hdfc": "hdfcbank.com",
    "icici": "icicibank.com", "axis": "axisbank.com", "kotak": "kotak.com", "pnb": "pnbindia.in",
    "bob": "bankofbaroda.in", "canara": "canarabank.com", "paytm": "paytm.com", "phonepe": "phonepe.com",
    "gpay": "pay.google.com", "bhim": "bhimupi.org.in", "npci": "npci.org.in", "amazon": "amazon.in",
    "flipkart": "flipkart.com", "indiapost": "indiapost.gov.in", "bluedart": "bluedart.com",
    "fedex": "fedex.com", "dhl": "dhl.com", "irctc": "irctc.co.in", "uidai": "uidai.gov.in",
    "aadhaar": "uidai.gov.in", "incometax": "incometax.gov.in", "epfo": "epfindia.gov.in",
    "jio": "jio.com", "airtel": "airtel.in", "bsnl": "bsnl.co.in", "electricity": "",
}
OFFICIAL = {d for d in BRANDS.values() if d}

SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "cutt.ly", "rb.gy", "t.ly",
    "shorturl.at", "tiny.cc", "rebrand.ly", "bitly.com", "s.id", "v.gd", "short.gy", "wa.me",
}
SUSPICIOUS_TLDS = {
    "xyz", "top", "club", "online", "site", "info", "live", "icu", "buzz", "cc", "tk", "ml", "ga",
    "cf", "gq", "work", "click", "link", "rest", "fit", "support", "shop", "vip", "cyou", "sbs",
}

URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s<>\"]+"
    r"|\b(?:[a-z0-9-]+\.)+(?:com|in|org|net|xyz|top|info|co|ly|me|io|gd|at|live|site|online|club|icu|cc|tk|"
    r"gov|app|link|click|shop|vip|support|sbi|cyou|sbs|ml|ga|cf|gq|buzz|fit|rest|work)\b(?:/[^\s<>\"]*)?",
    re.IGNORECASE,
)
IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def extract_urls(text: str) -> list[str]:
    return [m.group().rstrip(".,;:!?)") for m in URL_RE.finditer(text)]


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _registered(host: str) -> str:
    """Rough registrable domain: last two labels, or three for co.in / gov.in style."""
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "gov", "org", "net", "ac", "nic"} and parts[-1] == "in":
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def analyze_url(url: str) -> dict:
    raw = url if re.match(r"^[a-z]+://", url, re.I) else "http://" + url
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    has_at = "@" in parts.netloc
    reg = _registered(host)
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    official = reg in OFFICIAL or host in OFFICIAL

    lookalike_of, distance = None, None
    if not official and not IP_RE.match(host):
        bare = re.sub(r"[^a-z0-9]", "", host)
        for key, dom in BRANDS.items():
            if dom and len(key) >= 3 and key in bare:
                lookalike_of, distance = dom, levenshtein(reg, dom)
                break
        if lookalike_of is None:  # typosquats: "hdfcbnak.com", "paytrn.com"
            label = reg.split(".")[0]
            for dom in OFFICIAL:
                d = levenshtein(label, dom.split(".")[0])
                if 0 < d <= 2 and len(label) >= 5:
                    lookalike_of, distance = dom, d
                    break

    result = {
        "url": url,
        "domain": host,
        "registered_domain": reg,
        "official": official,
        "lookalike_of": lookalike_of,
        "distance": distance,
        "shortener": reg in SHORTENERS or host in SHORTENERS,
        "suspicious_tld": tld in SUSPICIOUS_TLDS,
        "ip_host": bool(IP_RE.match(host)),
        "has_at": has_at,
        "subdomains": max(0, host.count(".") - reg.count(".")),
        "hyphens": reg.count("-"),
        "https": parts.scheme == "https" if url.lower().startswith(("http://", "https://")) else None,
    }
    result["score"] = url_risk(result)
    return result


def url_risk(r: dict) -> float:
    """Heuristic 0-1 suspicion score for one URL (a feature, not a verdict)."""
    if r["official"]:
        return 0.0
    s = 0.15
    s += 0.35 if r["lookalike_of"] else 0
    s += 0.2 if r["suspicious_tld"] else 0
    s += 0.2 if r["shortener"] else 0
    s += 0.3 if r["ip_host"] else 0
    s += 0.25 if r["has_at"] else 0
    s += 0.05 * min(r["subdomains"], 3) + 0.05 * min(r["hyphens"], 2)
    return round(min(s, 1.0), 3)


def analyze_text(text: str) -> list[dict]:
    return [analyze_url(u) for u in extract_urls(text)]
