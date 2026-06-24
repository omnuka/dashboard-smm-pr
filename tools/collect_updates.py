from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCES_PATH = DATA / "sources.json"
FINDINGS_PATH = DATA / "weekly_findings.json"
SNAPSHOT_PATH = DATA / "link_snapshot.json"
STATUS_PATH = DATA / "collector_status.json"

TODAY = date.today().isoformat()
USER_AGENT = "SerenityCompetitorRadar/1.0 (+https://github.com/omnuka/dashboard-smm-pr)"
TIMEOUT = 18
SLEEP_BETWEEN_REQUESTS = 0.4
MAX_LINKS_PER_SOURCE = 45
MAX_BASELINE_FINDINGS_PER_SOURCE = 5
MAX_DETAIL_FETCHES = 80
KEEP_DAYS = 120

CONTENT_WORDS = [
    "case", "cases", "work", "works", "project", "projects", "portfolio", "blog", "news", "media",
    "journal", "article", "articles", "insight", "insights", "press", "post", "posts",
    "кейс", "кейсы", "проект", "проекты", "портфолио", "блог", "новост", "медиа", "стать", "журнал",
]

SKIP_WORDS = [
    "privacy", "policy", "cookie", "contacts", "contact", "about", "team", "career", "vacanc", "job",
    "login", "sign", "search", "tag", "category", "terms", "uploads", "wp-content", "cdn", "mailto:",
    "контакт", "команда", "ваканс", "политик", "соглас", "карьер", "услуг", "о-нас", "about-us",
]

SERVICE_KEYWORDS = [
    ("Упаковка", ["упаков", "pack", "package", "fmcg", "этикет"]),
    ("Нейминг", ["нейминг", "naming", "названи"]),
    ("Стратегия", ["стратег", "strategy", "платформ", "позиционир"]),
    ("Айдентика", ["айдентик", "identity", "logo", "логотип", "фирмен"]),
    ("Digital", ["сайт", "site", "digital", "лендинг", "ux", "ui", "web"]),
    ("PR", ["pr", "пиар", "сми", "интервью", "комментари"]),
    ("SMM", ["smm", "соцсет", "telegram", "vk", "контент"]),
    ("Исследования", ["исслед", "research", "аналит", "опрос"]),
]

THEME_KEYWORDS = [
    ("FMCG / упаковка", ["fmcg", "упаков", "этикет", "pack", "package"]),
    ("ИИ в брендинге", [" ии", "ai", "нейро", "gpt", "midjourney", "генерат"]),
    ("Ребрендинг", ["ребрендинг", "редизайн", "rebrand", "redesign"]),
    ("Публичная экспертиза агентства", ["интервью", "колонк", "комментари", "эксперт", "медиа", "сми"]),
    ("Нейминг", ["нейминг", "naming"]),
    ("Бренд-стратегия", ["стратег", "позиционир", "платформ"]),
    ("Айдентика", ["айдентик", "identity", "логотип", "брендбук"]),
    ("Digital и сайты", ["сайт", "digital", "ux", "ui", "лендинг"]),
]

KNOWN_BRANDS = [
    "Добрый", "НМЖК", "Самокат", "Магнит", "Пятерочка", "Перекресток", "ВкусВилл", "Сбер", "МТС",
    "Яндекс", "Ozon", "Wildberries", "Аэрофлот", "Билайн", "Т-Банк", "Газпром", "Лукойл",
    "Черкизово", "Danone", "Pepsi", "Coca-Cola", "Borjomi", "Боржоми", "Меридиан", "Санта-Бремор",
    "Русская картошка", "Вкусно и точка", "Rive Gauche", "Рив Гош", "X5", "Fix Price", "Лента",
]

@dataclass
class Candidate:
    competitor: str
    source_type_raw: str
    source_url: str
    url: str
    anchor: str
    placement: str
    channel: str


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower().replace("www.", "")
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def is_url(value: str) -> bool:
    return bool(re.match(r"^https?://", (value or "").strip(), re.I))


def source_key(source: dict[str, Any]) -> str:
    raw = f"{source.get('competitor','')}|{source.get('source_type','')}|{source.get('url_or_query','')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def fetch(url: str) -> tuple[str, str | None]:
    try:
        response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        if response.status_code >= 400:
            return "", f"HTTP {response.status_code}"
        response.encoding = response.encoding or "utf-8"
        return response.text, None
    except Exception as exc:
        return "", str(exc)[:180]


def soup_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(" ", strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(" ", strip=True)
    return ""


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def same_domain(a: str, b: str) -> bool:
    pa = urlparse(a)
    pb = urlparse(b)
    da = pa.netloc.lower().replace("www.", "")
    db = pb.netloc.lower().replace("www.", "")
    return da == db


def looks_content_url(url: str, text: str, strict: bool) -> bool:
    blob = f"{url} {text}".lower()
    if any(w in blob for w in SKIP_WORDS):
        return False
    if strict:
        return any(w in blob for w in CONTENT_WORDS)
    return True


def source_placement(source_type: str, url: str) -> tuple[str, str]:
    st = (source_type or "").lower()
    host = urlparse(url).netloc.lower()
    if "telegram" in st or "t.me" in host:
        return "Telegram", "Telegram"
    if "vk" in st or "vk.com" in host:
        return "VK", "VK"
    if "youtube" in st or "youtu" in host:
        return "YouTube", "YouTube"
    if "нов" in st or "блог" in st or "сайт" in st:
        return "Сайт", "Сайт"
    return source_type or "Сайт", source_type or "Сайт"


def extract_site_candidates(source: dict[str, Any], html: str) -> list[Candidate]:
    source_url = source.get("url_or_query", "")
    stype = source.get("source_type", "")
    competitor = source.get("competitor", "")
    placement, channel = source_placement(stype, source_url)
    soup = BeautifulSoup(html, "html.parser")
    strict = "сайт" in stype.lower()
    seen = set()
    candidates: list[Candidate] = []
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        if not href or href.startswith("#"):
            continue
        absolute = urljoin(source_url, href)
        if not absolute.startswith(("http://", "https://")):
            continue
        if not same_domain(source_url, absolute):
            continue
        text = clean_text(a.get_text(" ", strip=True))[:160]
        normalized = normalize_url(absolute)
        if not normalized or normalized in seen:
            continue
        if not looks_content_url(normalized, text, strict=strict):
            continue
        seen.add(normalized)
        candidates.append(Candidate(competitor, stype, source_url, normalized, text, placement, channel))
        if len(candidates) >= MAX_LINKS_PER_SOURCE:
            break
    return candidates


def telegram_public_url(url: str) -> str | None:
    parsed = urlparse(url)
    if "t.me" not in parsed.netloc.lower():
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return None
    if parts[0] in {"joinchat", "+"}:
        return None
    channel = parts[0]
    return f"https://t.me/s/{channel}"


def extract_telegram_candidates(source: dict[str, Any], html: str) -> list[Candidate]:
    source_url = source.get("url_or_query", "")
    competitor = source.get("competitor", "")
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[Candidate] = []
    for msg in soup.select(".tgme_widget_message"):
        date_link = msg.select_one("a.tgme_widget_message_date")
        message_url = normalize_url(date_link.get("href", "")) if date_link else ""
        if not message_url:
            continue
        text_el = msg.select_one(".tgme_widget_message_text")
        text = clean_text(text_el.get_text(" ", strip=True) if text_el else "Пост Telegram")
        candidates.append(Candidate(competitor, "Telegram", source_url, message_url, text[:160], "Telegram", "Telegram"))
    return candidates[:MAX_LINKS_PER_SOURCE]


def classify_type(text: str, url: str, channel: str) -> str:
    blob = f"{text} {url}".lower()
    if channel == "Telegram" or channel == "VK":
        return "Пост"
    if any(w in blob for w in ["case", "cases", "кейс", "project", "projects", "portfolio", "work", "works"]):
        return "Кейс"
    return "Пост"


def detect_service(text: str) -> str:
    blob = f" {text.lower()} "
    for label, keys in SERVICE_KEYWORDS:
        if any(k in blob for k in keys):
            return label
    return "Брендинг"


def detect_theme(text: str) -> str:
    blob = f" {text.lower()} "
    for label, keys in THEME_KEYWORDS:
        if any(k in blob for k in keys):
            return label
    return "Публичная активность агентства"


def detect_tags(text: str) -> list[str]:
    blob = text.lower()
    tags = []
    hashtags = re.findall(r"#[\wа-яА-ЯеЕёЁ-]+", text)
    for label, keys in SERVICE_KEYWORDS + THEME_KEYWORDS:
        if any(k in blob for k in keys):
            tags.append(label)
    return sorted(set(tags + hashtags))[:12]


def detect_hashtags(text: str) -> list[str]:
    return sorted(set(re.findall(r"#[\wа-яА-ЯеЕёЁ-]+", text)))[:12]


def detect_brands(text: str) -> list[dict[str, str]]:
    found = []
    lower = text.lower()
    for brand in KNOWN_BRANDS:
        if brand.lower() in lower:
            found.append({"name": brand, "category": "", "context": "упоминание в материале"})
    return found


def detail_text(candidate: Candidate, remaining_detail_fetches: list[int]) -> tuple[str, str]:
    title = candidate.anchor or ""
    summary = ""
    if remaining_detail_fetches[0] <= 0:
        return title, summary
    remaining_detail_fetches[0] -= 1
    html, err = fetch(candidate.url)
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    if err or not html:
        return title, summary
    page_title = soup_title(html)
    if page_title:
        title = page_title
    soup = BeautifulSoup(html, "html.parser")
    desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if desc and desc.get("content"):
        summary = clean_text(desc.get("content", ""))[:260]
    if not summary:
        p = soup.find("p")
        if p:
            summary = clean_text(p.get_text(" ", strip=True))[:260]
    return title or candidate.url, summary


def make_finding(candidate: Candidate, baseline: bool, detail_budget: list[int]) -> dict[str, Any]:
    title, summary = detail_text(candidate, detail_budget)
    text = f"{title} {summary} {candidate.anchor} {candidate.url}"
    source_type = classify_type(text, candidate.url, candidate.channel)
    service = detect_service(text)
    theme = detect_theme(text)
    tags = detect_tags(text)
    hashtags = detect_hashtags(text)
    brands = detect_brands(text)
    note = "Первичный срез источника. Проверь дату публикации перед выводами." if baseline else "Новая ссылка найдена при еженедельном обходе источников."
    return {
        "id": hashlib.sha1(f"{candidate.competitor}|{candidate.url}".encode("utf-8")).hexdigest()[:16],
        "date": TODAY,
        "theme": theme,
        "service": service,
        "source_type": source_type,
        "placement": candidate.placement,
        "channel": candidate.channel,
        "competitor": candidate.competitor,
        "title": title or candidate.anchor or candidate.url,
        "summary": summary or note,
        "url": candidate.url,
        "views": None,
        "reactions": None,
        "comments": None,
        "tags": tags,
        "hashtags": hashtags,
        "mentioned_brands": brands,
        "sentiment": "нейтрально",
        "serenity_pr_smm_use": pr_smm_use(theme, service, source_type, baseline),
        "baseline": baseline,
    }


def pr_smm_use(theme: str, service: str, source_type: str, baseline: bool) -> str:
    prefix = "Проверить как первичный ориентир: " if baseline else "Свежий сигнал: "
    if source_type == "Кейс":
        return prefix + f"конкурент выводит тему «{theme}» через услугу «{service}». Можно сравнить подачу, заголовок и аргументацию."
    if source_type == "Пост":
        return prefix + f"тема «{theme}» подходит для контента Serenity, если есть свой пример или сильное мнение."
    return prefix + f"упоминание можно использовать для карты инфоповодов по теме «{theme}»."


def parse_existing_findings() -> list[dict[str, Any]]:
    data = read_json(FINDINGS_PATH, [])
    return data if isinstance(data, list) else []


def keep_recent(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    threshold = date.today() - timedelta(days=KEEP_DAYS)
    kept = []
    seen_ids = set()
    for f in sorted(findings, key=lambda x: x.get("date", ""), reverse=True):
        fid = f.get("id") or hashlib.sha1(f"{f.get('competitor','')}|{f.get('url','')}".encode("utf-8")).hexdigest()[:16]
        if fid in seen_ids:
            continue
        seen_ids.add(fid)
        try:
            d = datetime.strptime(f.get("date", ""), "%Y-%m-%d").date()
            if d < threshold:
                continue
        except Exception:
            pass
        kept.append(f)
    return kept


def collect() -> None:
    sources = read_json(SOURCES_PATH, [])
    if not isinstance(sources, list):
        raise SystemExit("data/sources.json must be a list")

    snapshot = read_json(SNAPSHOT_PATH, {})
    if not isinstance(snapshot, dict):
        snapshot = {}

    existing = parse_existing_findings()
    existing_urls = {normalize_url(f.get("url", "")) for f in existing if f.get("url")}
    new_findings: list[dict[str, Any]] = []
    detail_budget = [MAX_DETAIL_FETCHES]
    status = {
        "last_run": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "sources_total": len(sources),
        "sources_checked": 0,
        "sources_skipped": 0,
        "sources_failed": 0,
        "new_findings": 0,
        "baseline_findings": 0,
        "notes": [],
    }

    for source in sources:
        raw_url = str(source.get("url_or_query", "")).strip()
        stype = str(source.get("source_type", "")).strip()
        if not is_url(raw_url):
            status["sources_skipped"] += 1
            continue

        candidates: list[Candidate] = []
        fetch_url = raw_url
        if "telegram" in stype.lower() or "t.me" in raw_url:
            tg_url = telegram_public_url(raw_url)
            if not tg_url:
                status["sources_skipped"] += 1
                continue
            fetch_url = tg_url
            html, err = fetch(fetch_url)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            if err:
                status["sources_failed"] += 1
                status["notes"].append({"source": raw_url, "error": err})
                continue
            candidates = extract_telegram_candidates(source, html)
        elif any(x in stype.lower() for x in ["сайт", "нов", "блог"]):
            html, err = fetch(fetch_url)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            if err:
                status["sources_failed"] += 1
                status["notes"].append({"source": raw_url, "error": err})
                continue
            candidates = extract_site_candidates(source, html)
        else:
            status["sources_skipped"] += 1
            continue

        status["sources_checked"] += 1
        key = source_key(source)
        seen_before = set(snapshot.get(key, {}).get("seen_urls", []))
        current_urls = {c.url for c in candidates}
        is_first_run_for_source = not seen_before
        if is_first_run_for_source:
            to_emit = candidates[:MAX_BASELINE_FINDINGS_PER_SOURCE]
        else:
            to_emit = [c for c in candidates if c.url not in seen_before]

        for c in to_emit:
            if c.url in existing_urls:
                continue
            finding = make_finding(c, baseline=is_first_run_for_source, detail_budget=detail_budget)
            new_findings.append(finding)
            existing_urls.add(c.url)
            if is_first_run_for_source:
                status["baseline_findings"] += 1
            else:
                status["new_findings"] += 1

        snapshot[key] = {
            "competitor": source.get("competitor"),
            "source_type": stype,
            "source_url": raw_url,
            "last_checked": TODAY,
            "seen_urls": sorted(seen_before | current_urls),
        }

    merged = keep_recent(new_findings + existing)
    write_json(FINDINGS_PATH, merged)
    write_json(SNAPSHOT_PATH, snapshot)
    write_json(STATUS_PATH, status)
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    collect()
