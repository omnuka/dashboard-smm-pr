from __future__ import annotations

import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse, urlunparse, parse_qs

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCES_PATH = DATA / "sources.json"
COMPETITORS_PATH = DATA / "competitors.json"
FINDINGS_PATH = DATA / "weekly_findings.json"
STATUS_PATH = DATA / "collector_status.json"
LAST_RUN_PATH = DATA / "last_run_summary.json"
MEDIA_SOURCES_PATH = DATA / "media_sources.json"
CLIENT_BRANDS_PATH = DATA / "client_brands.json"

TODAY_DATE = date.today()
TODAY = TODAY_DATE.isoformat()
LOOKBACK_DAYS = 7
WINDOW_START = TODAY_DATE - timedelta(days=LOOKBACK_DAYS)

USER_AGENT = "SerenityCompetitorRadar/2.0 (+https://github.com/omnuka/dashboard-smm-pr)"
TIMEOUT = 18
SLEEP_BETWEEN_REQUESTS = 0.35
MEDIA_SEARCH_SLEEP_SECONDS = 7
MEDIA_SEARCH_RETRY_DELAYS = (30, 60)
MAX_LINKS_PER_SOURCE = 24
MAX_FINDINGS_PER_SOURCE = 8
MAX_DETAIL_FETCHES = 700
MAX_NEWS_MENTIONS_PER_COMPETITOR = 4
MAX_NEWS_MENTIONS_PER_CLIENT = 8
MAX_MEDIA_COMPETITOR_QUERIES_PER_RUN = 20
MAX_CONSECUTIVE_MEDIA_429 = 3

SERVICE_KEYWORDS = [
    ("Упаковка", ["упаков", "pack", "package", "fmcg", "этикет"]),
    ("Нейминг", ["нейминг", "naming", "названи"]),
    ("Стратегия", ["стратег", "strategy", "платформ", "позиционир"]),
    ("Айдентика", ["айдентик", "identity", "logo", "логотип", "фирмен"]),
    ("Digital", ["сайт", "site", "digital", "лендинг", "ux", "ui", "web"]),
    ("PR", ["pr", "пиар", "сми", "интервью", "комментари", "медиа"]),
    ("SMM", ["smm", "соцсет", "telegram", "vk", "контент"]),
    ("Исследования", ["исслед", "research", "аналит", "опрос"]),
]

CONTENT_THEME_KEYWORDS = [
    ("Рейтинги / премии", ["рейтинг", "топ ", "топ-", "top ", "преми", "награ", "award", "шорт-лист", "shortlist"]),
    ("Отчеты / исследования", ["отчет", "исслед", "аналит", "статист", "итоги", "результаты", "обзор рынка", "гайд", "white paper"]),
    ("Прогнозы", ["прогноз", "будущее", "перспектив", "что ждет", "ожидается", "будет расти", "станет"]),
    ("Тренды", ["тренд", "trend", "тенденц", "подборка", "что сейчас", "новые форматы"]),
    ("Анонсы / события", ["анонс", "запуск", "старт", "приглашаем", "регистрация", "вебинар", "лекция", "конференц", "мероприят", "выставк", "событи"]),
    ("Реклама / кампании", ["реклам", "кампани", "промо", "ролик", "баннер", "спецпроект", "ooh", "наружн", "перформанс", "performance"]),
    ("Продукты / запуски", ["продукт", "линейк", "товар", "новинка", "ассортимент", "бренд продукта", "упаковка для", "этикетка для"]),
    ("Мнение / комментарий", ["интервью", "комментар", "колонк", "эксперт", "мнение", "цитирует", "ответил"]),
    ("Описание услуги", ["услуг", "что такое", "как мы", "разрабатываем", "создаем", "заказать", "стоимость", "подход к", "этапы работ"]),
    ("Новости агентства", ["новост", "обновлен", "партнерств", "сотрудничеств", "команда", "назначен"]),
]

CLIENT_BRAND_NAMES = [
    "Группа Компаний Красное Золото",
    "Красное Золото",
    "Русаков",
    "Тунгутун",
    "Авача",
    "Виктория Бис",
    "Укинский леман",
]

KNOWN_BRANDS = [
    *CLIENT_BRAND_NAMES,
    "Добрый", "НМЖК", "Самокат", "Магнит", "Пятерочка", "Перекресток", "ВкусВилл", "Сбер", "МТС",
    "Яндекс", "Ozon", "Wildberries", "Аэрофлот", "Билайн", "Т-Банк", "Газпром", "Лукойл",
    "Черкизово", "Danone", "Pepsi", "Coca-Cola", "Borjomi", "Боржоми", "Меридиан", "Санта-Бремор",
    "Русская картошка", "Вкусно и точка", "Rive Gauche", "Рив Гош", "X5", "Fix Price", "Лента",
]

DEFAULT_MEDIA_SOURCES = [
    {"name": "Sostav", "domain": "sostav.ru"},
    {"name": "AdIndex", "domain": "adindex.ru"},
    {"name": "VC", "domain": "vc.ru"},
    {"name": "Cossa", "domain": "cossa.ru"},
    {"name": "РБК", "domain": "rbc.ru"},
    {"name": "РБК Компании", "domain": "companies.rbc.ru"},
    {"name": "Retail.ru", "domain": "retail.ru"},
    {"name": "New Retail", "domain": "new-retail.ru"},
    {"name": "RB.RU", "domain": "rb.ru"},
    {"name": "Деловой Петербург", "domain": "dp.ru"},
]

CONTENT_WORDS = [
    "case", "cases", "work", "works", "project", "projects", "portfolio", "blog", "news", "media",
    "journal", "article", "articles", "insight", "insights", "press", "post", "posts", "publication",
    "кейс", "кейсы", "проект", "проекты", "портфолио", "блог", "новост", "медиа", "стать", "журнал",
    "публикац", "работ", "исслед", "интервью",
]

SKIP_WORDS = [
    "privacy", "policy", "cookie", "contacts", "contact", "about", "team", "career", "vacanc", "job",
    "login", "sign", "search", "tag", "category", "terms", "uploads", "wp-content", "cdn", "mailto:",
    "tel:", "javascript:", "контакт", "команда", "ваканс", "политик", "соглас", "карьер", "услуг",
    "о-нас", "about-us", "client", "clients", "клиент", "brief", "бриф",
]

SECTION_SLUGS = {
    "", "portfolio", "cases", "case", "work", "works", "projects", "project", "blog", "news", "media",
    "journal", "articles", "article", "insights", "press", "publications", "publication", "ru", "en",
    "портфолио", "кейсы", "кейс", "проекты", "проект", "блог", "новости", "медиа", "статьи", "публикации",
}

RU_MONTHS = {
    "января": 1, "январь": 1, "февраля": 2, "февраль": 2, "марта": 3, "март": 3,
    "апреля": 4, "апрель": 4, "мая": 5, "май": 5, "июня": 6, "июнь": 6,
    "июля": 7, "июль": 7, "августа": 8, "август": 8, "сентября": 9, "сентябрь": 9,
    "октября": 10, "октябрь": 10, "ноября": 11, "ноябрь": 11, "декабря": 12, "декабрь": 12,
}

@dataclass
class Candidate:
    competitor: str
    source_type_raw: str
    source_url: str
    url: str
    anchor: str
    placement: str
    channel: str
    published_date: str | None = None
    monitor_scope: str = "competitor"


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_url(url: str, keep_query: bool = False) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower().replace("www.", "")
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = parsed.query if keep_query else ""
    return urlunparse((scheme, netloc, path, "", query, ""))


def url_key(url: str) -> str:
    return normalize_url(url, keep_query=False)


def is_url(value: str) -> bool:
    return bool(re.match(r"^https?://", (value or "").strip(), re.I))


def same_domain(a: str, b: str) -> bool:
    pa = urlparse(a)
    pb = urlparse(b)
    da = pa.netloc.lower().replace("www.", "")
    db = pb.netloc.lower().replace("www.", "")
    return da == db


def path_segments(url: str) -> list[str]:
    return [p for p in urlparse(url).path.split("/") if p]


def is_listing_page(url: str) -> bool:
    segments = path_segments(url_key(url))
    if not segments:
        return True
    last = segments[-1].lower()
    if last in SECTION_SLUGS:
        return True
    if len(segments) == 1 and last in SECTION_SLUGS:
        return True
    return False


def is_child_of_source(candidate_url: str, source_url: str) -> bool:
    c = url_key(candidate_url)
    s = url_key(source_url)
    if c == s:
        return False
    if not same_domain(c, s):
        return False
    sp = urlparse(s).path.rstrip("/")
    cp = urlparse(c).path.rstrip("/")
    if sp in {"", "/"}:
        return True
    return cp.startswith(sp + "/") and len(path_segments(c)) > len(path_segments(s))


def looks_content_url(url: str, text: str, source_url: str, strict: bool) -> bool:
    normalized = url_key(url)
    source_normalized = url_key(source_url)
    if not normalized or normalized == source_normalized:
        return False
    blob = f"{normalized} {text}".lower()
    if any(w in blob for w in SKIP_WORDS):
        return False
    if is_listing_page(normalized):
        return False
    if strict:
        if is_child_of_source(normalized, source_normalized):
            return True
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
    if "vc" in st or "vc.ru" in host:
        return "VC", "VC"
    if "дзен" in st or "dzen.ru" in host or "zen.yandex" in host:
        return "Дзен", "Дзен"
    if "behance" in st or "behance.net" in host:
        return "Behance", "Behance"
    if "dprofile" in st or "dprofile.ru" in host:
        return "Dprofile", "Dprofile"
    if any(x in st for x in ["нов", "блог", "сайт", "медиа", "доп"]):
        return "Сайт", "Сайт"
    return source_type or "Сайт", source_type or "Сайт"


def fetch(url: str) -> tuple[str, str | None]:
    try:
        response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        if response.status_code >= 400:
            return "", f"HTTP {response.status_code}"
        response.encoding = response.encoding or "utf-8"
        return response.text, None
    except Exception as exc:
        return "", str(exc)[:180]


def to_iso_date(value: Any) -> str | None:
    if not value:
        return None
    text = clean_text(str(value))
    if not text:
        return None
    # 2026-06-24 or 2026.06.24 or 2026/06/24
    m = re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    # 24.06.2026
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            pass
    low = text.lower()
    if "сегодня" in low:
        return TODAY
    if "вчера" in low:
        return (TODAY_DATE - timedelta(days=1)).isoformat()
    # 24 июня 2026 or 24 июня
    m = re.search(r"(\d{1,2})\s+([а-яА-ЯеЕёЁ]+)(?:\s+(20\d{2}))?", text)
    if m:
        month = RU_MONTHS.get(m.group(2).lower())
        year = int(m.group(3) or TODAY_DATE.year)
        if month:
            try:
                return date(year, month, int(m.group(1))).isoformat()
            except ValueError:
                pass
    # RFC date
    try:
        dt = parsedate_to_datetime(text)
        if dt:
            return dt.date().isoformat()
    except Exception:
        pass
    return None


def date_from_url(url: str) -> str | None:
    path = urlparse(url).path
    return to_iso_date(path)


def date_in_window(value: str | None) -> bool:
    if not value:
        return False
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return False
    return WINDOW_START <= d <= TODAY_DATE


def extract_date_from_soup(soup: BeautifulSoup, fallback_text: str = "") -> str | None:
    selectors = [
        {"property": "article:published_time"}, {"property": "article:modified_time"}, {"property": "og:updated_time"},
        {"name": "date"}, {"name": "pubdate"}, {"name": "publishdate"}, {"name": "timestamp"},
        {"itemprop": "datePublished"}, {"itemprop": "dateModified"},
    ]
    for attrs in selectors:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            iso = to_iso_date(tag.get("content"))
            if iso:
                return iso
    for t in soup.find_all("time")[:10]:
        raw = t.get("datetime") or t.get("content") or t.get_text(" ", strip=True)
        iso = to_iso_date(raw)
        if iso:
            return iso
    return to_iso_date(fallback_text)


def soup_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        return clean_text(og_title.get("content", ""))
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(" ", strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(" ", strip=True)
    return ""


def detect_date_near_link(a) -> str | None:
    chunks = []
    parent = a.parent
    for _ in range(4):
        if not parent:
            break
        chunks.append(parent.get_text(" ", strip=True)[:600])
        time_tag = parent.find("time") if hasattr(parent, "find") else None
        if time_tag:
            iso = to_iso_date(time_tag.get("datetime") or time_tag.get_text(" ", strip=True))
            if iso:
                return iso
        parent = parent.parent
    return to_iso_date(" ".join(chunks))


def extract_site_candidates(source: dict[str, Any], html: str) -> list[Candidate]:
    source_url = source.get("url_or_query", "")
    stype = source.get("source_type", "")
    competitor = source.get("competitor", "")
    placement, channel = source_placement(stype, source_url)
    soup = BeautifulSoup(html, "html.parser")
    strict = any(x in stype.lower() for x in ["сайт", "нов", "блог", "медиа", "доп", "vc", "дзен", "behance", "dprofile"])
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
        text = clean_text(a.get_text(" ", strip=True))[:220]
        normalized = normalize_url(absolute)
        key = url_key(normalized)
        if not key or key in seen:
            continue
        if not looks_content_url(normalized, text, source_url, strict=strict):
            continue
        seen.add(key)
        published = date_from_url(normalized) or detect_date_near_link(a)
        candidates.append(Candidate(competitor, stype, source_url, normalized, text, placement, channel, published))
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
    return f"https://t.me/s/{parts[0]}"


def extract_telegram_candidates(source: dict[str, Any], html: str) -> list[Candidate]:
    source_url = source.get("url_or_query", "")
    competitor = source.get("competitor", "")
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[Candidate] = []
    for msg in soup.select(".tgme_widget_message"):
        date_link = msg.select_one("a.tgme_widget_message_date")
        message_url = normalize_url(date_link.get("href", ""), keep_query=True) if date_link else ""
        if not message_url:
            continue
        time_el = msg.select_one("time")
        published = to_iso_date(time_el.get("datetime") if time_el else "") or to_iso_date(date_link.get("title", "") if date_link else "")
        if not date_in_window(published):
            continue
        text_el = msg.select_one(".tgme_widget_message_text")
        text = clean_text(text_el.get_text(" ", strip=True) if text_el else "Пост Telegram")
        views_el = msg.select_one(".tgme_widget_message_views")
        views = clean_text(views_el.get_text(" ", strip=True) if views_el else "")
        anchor = text[:180] or "Пост Telegram"
        if views:
            anchor = f"{anchor} | просмотры: {views}"
        candidates.append(Candidate(competitor, "Telegram", source_url, message_url, anchor, "Telegram", "Telegram", published))
    return candidates[:MAX_LINKS_PER_SOURCE]


def youtube_feed_url(source_url: str, html: str) -> str | None:
    parsed = urlparse(source_url)
    qs = parse_qs(parsed.query)
    if "channel_id" in qs:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={qs['channel_id'][0]}"
    m = re.search(r'"channelId"\s*:\s*"(UC[^"]+)"', html)
    if m:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}"
    m = re.search(r'itemprop="channelId"\s+content="(UC[^"]+)"', html)
    if m:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}"
    return None


def extract_youtube_candidates(source: dict[str, Any], html: str) -> list[Candidate]:
    source_url = source.get("url_or_query", "")
    competitor = source.get("competitor", "")
    feed = youtube_feed_url(source_url, html)
    if not feed:
        return []
    xml_text, err = fetch(feed)
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    if err or not xml_text:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    candidates: list[Candidate] = []
    try:
        root = ET.fromstring(xml_text)
        for entry in root.findall("a:entry", ns):
            title = clean_text(entry.findtext("a:title", default="", namespaces=ns))
            video_id = entry.findtext("yt:videoId", default="", namespaces=ns)
            published = to_iso_date(entry.findtext("a:published", default="", namespaces=ns))
            if not video_id or not date_in_window(published):
                continue
            url = f"https://www.youtube.com/watch?v={video_id}"
            candidates.append(Candidate(competitor, "YouTube", source_url, url, title or "Видео YouTube", "YouTube", "YouTube", published))
    except Exception:
        return []
    return candidates[:MAX_LINKS_PER_SOURCE]


def vk_mobile_url(url: str) -> str:
    parsed = urlparse(url)
    if "vk.com" not in parsed.netloc.lower():
        return url
    return urlunparse((parsed.scheme or "https", "m.vk.com", parsed.path, "", parsed.query, ""))


def extract_vk_candidates(source: dict[str, Any], html: str) -> list[Candidate]:
    source_url = source.get("url_or_query", "")
    competitor = source.get("competitor", "")
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    candidates: list[Candidate] = []
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        if "wall" not in href:
            continue
        absolute = urljoin("https://vk.com", href.replace("m.vk.com", "vk.com")).replace("https://m.vk.com", "https://vk.com")
        key = url_key(absolute)
        if key in seen:
            continue
        published = detect_date_near_link(a)
        if not date_in_window(published):
            continue
        seen.add(key)
        text = clean_text(a.get_text(" ", strip=True)) or "Пост VK"
        candidates.append(Candidate(competitor, "VK", source_url, normalize_url(absolute, keep_query=True), text[:180], "VK", "VK", published))
        if len(candidates) >= MAX_LINKS_PER_SOURCE:
            break
    return candidates


def classify_type(text: str, url: str, channel: str) -> str:
    blob = f"{text} {url}".lower()
    if channel in {"Telegram", "VK"}:
        return "Пост"
    if channel == "YouTube":
        return "Видео"
    if any(w in blob for w in ["case", "cases", "кейс", "project", "projects", "portfolio", "work", "works"]):
        return "Кейс"
    if channel not in {"Сайт", "VC", "Дзен", "Behance", "Dprofile"}:
        return "СМИ"
    return "Новость"


def detect_service(text: str) -> str:
    blob = f" {text.lower()} "
    for label, keys in SERVICE_KEYWORDS:
        if any(k in blob for k in keys):
            return label
    return "Брендинг"


def detect_theme(text: str, source_type: str = "") -> str:
    blob = f" {text.lower()} "
    if source_type == "Кейс":
        return "Кейсы"
    for label, keys in CONTENT_THEME_KEYWORDS:
        if any(k in blob for k in keys):
            return label
    return "Инфоповод"


def detect_tags(text: str) -> list[str]:
    blob = text.lower()
    tags = []
    hashtags = re.findall(r"#[\wа-яА-ЯеЕёЁ-]+", text)
    for label, keys in SERVICE_KEYWORDS + CONTENT_THEME_KEYWORDS:
        if any(k in blob for k in keys):
            tags.append(label)
    return sorted(set(tags + hashtags))[:12]


def detect_hashtags(text: str) -> list[str]:
    return sorted(set(re.findall(r"#[\wа-яА-ЯеЕёЁ-]+", text)))[:12]


def is_noise_title(text: str) -> bool:
    value = clean_text(text)
    if not value:
        return True
    low = value.lower()
    # Виджеты курсов, крипты, биржевые значения: USD 74.62, EUR 85.48, BTC / USD 61.1K
    if re.fullmatch(r"[A-ZА-Я]{2,6}(?:\s*/\s*[A-ZА-Я]{2,6})?\s+[\d.,]+\s*[KkКкMmМм%₽$€£]*", value):
        return True
    if re.fullmatch(r"(?:usd|eur|btc|eth|usdt|cny|gbp|brent|moex|s&p|nasdaq)[\s/:-]+[\d.,]+\s*[kKmM%₽$€£]*", low):
        return True
    noise_words = [
        "курс валют", "курсы валют", "биржевые котировки", "котировки", "погода",
        "подписаться", "войти", "регистрация", "читать далее", "показать еще",
        "наверх", "меню", "контакты", "политика конфиденциальности"
    ]
    if low in noise_words:
        return True
    if len(value) <= 3:
        return True
    return False


def load_client_brands() -> list[dict[str, str]]:
    raw = read_json(CLIENT_BRANDS_PATH, [])
    if isinstance(raw, list) and raw:
        brands = []
        for item in raw:
            if isinstance(item, str):
                brands.append({"name": item, "category": "клиент Serenity"})
            elif isinstance(item, dict) and item.get("name"):
                brands.append(item)
        priority = {name.lower(): index for index, name in enumerate(CLIENT_BRAND_NAMES)}
        return sorted(brands, key=lambda item: priority.get(str(item.get("name") or "").lower(), len(priority)))
    return [{"name": name, "category": "клиент Serenity"} for name in CLIENT_BRAND_NAMES]


def load_media_sources() -> list[dict[str, str]]:
    raw = read_json(MEDIA_SOURCES_PATH, [])
    if isinstance(raw, list) and raw:
        return [x for x in raw if isinstance(x, dict) and (x.get("name") or x.get("domain"))]
    return DEFAULT_MEDIA_SOURCES


def detect_brands(text: str) -> list[dict[str, str]]:
    found = []
    lower = text.lower()
    for brand in KNOWN_BRANDS:
        if brand.lower() in lower:
            found.append({"name": brand, "category": "", "context": "упоминание в материале"})
    return found


def detail_text_and_date(candidate: Candidate, budget: list[int]) -> tuple[str, str, str | None]:
    title = candidate.anchor or ""
    summary = ""
    published = candidate.published_date or date_from_url(candidate.url)
    if candidate.channel in {"Telegram", "VK", "YouTube"}:
        return title, summary, published
    if budget[0] <= 0:
        return title, summary, published
    budget[0] -= 1
    html, err = fetch(candidate.url)
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    if err or not html:
        return title, summary, published
    soup = BeautifulSoup(html, "html.parser")
    page_title = soup_title(html)
    if page_title:
        title = page_title
    desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if desc and desc.get("content"):
        summary = clean_text(desc.get("content", ""))[:360]
    if not summary:
        p = soup.find("p")
        if p:
            summary = clean_text(p.get_text(" ", strip=True))[:360]
    published = published or extract_date_from_soup(soup, f"{title} {summary}")
    return title or candidate.url, summary, published


def pr_smm_use(theme: str, service: str, source_type: str) -> str:
    if source_type == "Кейс":
        return f"Свежий сигнал: конкурент выводит тему «{theme}» через услугу «{service}». Можно сравнить подачу и аргументацию."
    if source_type in {"Пост", "Видео"}:
        return f"Свежий сигнал для контента Serenity: тема «{theme}» уже звучит у конкурентов."
    if source_type == "Новость":
        return f"Материал показывает, как конкурент подает тему «{theme}» на своем сайте."
    return f"СМИ-сигнал по теме «{theme}». Можно проверить, нужен ли Serenity комментарий или свой инфоповод."


def make_finding(candidate: Candidate, detail_budget: list[int]) -> dict[str, Any] | None:
    title, summary, published = detail_text_and_date(candidate, detail_budget)
    # В дашборде должна быть дата публикации материала, а не дата сканирования.
    # Если публикационная дата не найдена или она вне недельного окна, материал не показываем.
    if not date_in_window(published):
        return None
    if is_noise_title(title) or is_noise_title(candidate.anchor):
        return None
    text = f"{title} {summary} {candidate.anchor} {candidate.url}"
    source_type = classify_type(text, candidate.url, candidate.channel)
    service = detect_service(text)
    theme = detect_theme(text, source_type)
    tags = detect_tags(text)
    hashtags = detect_hashtags(text)
    brands = detect_brands(text)
    ukey = url_key(candidate.url)
    return {
        "id": hashlib.sha1(f"{candidate.competitor}|{ukey}".encode("utf-8")).hexdigest()[:16],
        "date": published,
        "theme": theme,
        "content_theme": theme,
        "service": service,
        "source_type": source_type,
        "placement": candidate.placement,
        "channel": candidate.channel,
        "competitor": candidate.competitor,
        "title": title or candidate.anchor or candidate.url,
        "summary": summary or "Материал найден в недельном мониторинге. Проверь страницу перед выводами.",
        "url": candidate.url,
        "url_key": ukey,
        "source_url": candidate.source_url,
        "views": None,
        "reactions": None,
        "comments": None,
        "tags": tags,
        "hashtags": hashtags,
        "mentioned_brands": brands,
        "sentiment": "нейтрально",
        "serenity_pr_smm_use": pr_smm_use(theme, service, source_type),
        "baseline": False,
        "date_confidence": "found_on_page_or_feed",
        "monitor_scope": getattr(candidate, "monitor_scope", "competitor"),
    }


def collect_candidates_for_source(source: dict[str, Any], status: dict[str, Any]) -> list[Candidate]:
    raw_url = str(source.get("url_or_query", "")).strip()
    stype = str(source.get("source_type", "")).strip()
    if not is_url(raw_url):
        status["sources_skipped"] += 1
        return []
    stype_lower = stype.lower()
    if "telegram" in stype_lower or "t.me" in raw_url:
        tg_url = telegram_public_url(raw_url)
        if not tg_url:
            status["sources_skipped"] += 1
            return []
        html, err = fetch(tg_url)
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        if err:
            status["sources_failed"] += 1
            status["notes"].append({"source": raw_url, "error": err})
            return []
        status["sources_checked"] += 1
        return extract_telegram_candidates(source, html)
    if "vk" in stype_lower or "vk.com" in raw_url:
        html, err = fetch(vk_mobile_url(raw_url))
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        if err:
            status["sources_failed"] += 1
            status["notes"].append({"source": raw_url, "error": err})
            return []
        status["sources_checked"] += 1
        return extract_vk_candidates(source, html)
    html, err = fetch(raw_url)
    time.sleep(SLEEP_BETWEEN_REQUESTS)
    if err:
        status["sources_failed"] += 1
        status["notes"].append({"source": raw_url, "error": err})
        return []
    status["sources_checked"] += 1
    if "youtube" in stype_lower or "youtu" in raw_url:
        return extract_youtube_candidates(source, html)
    if any(x in stype_lower for x in ["сайт", "нов", "блог", "медиа", "доп", "vc", "дзен", "behance", "dprofile"]):
        return extract_site_candidates(source, html)
    status["sources_skipped"] += 1
    return []


def media_name_from_domain(domain: str, media_sources: list[dict[str, str]]) -> str:
    host = (domain or "").lower().replace("www.", "")
    for item in media_sources:
        d = str(item.get("domain") or "").lower().replace("www.", "")
        if d and (host == d or host.endswith("." + d)):
            return str(item.get("name") or d)
    return domain or "СМИ"


def new_media_query_diagnostic(query: str, owner: str, scope: str) -> dict[str, Any]:
    return {
        "query": query,
        "owner": owner,
        "scope": scope,
        "status": "checked",
        "error": "",
        "articles_returned": 0,
        "findings_saved": 0,
        "discard_reasons": {},
    }


def add_media_discard(detail: dict[str, Any], reason: str) -> None:
    reasons = detail.setdefault("discard_reasons", {})
    reasons[reason] = reasons.get(reason, 0) + 1


def gdelt_search(query: str, status: dict[str, Any], max_records: int, detail: dict[str, Any]) -> list[dict[str, Any]]:
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + \
        f"query={quote(query)}&mode=ArtList&format=json&timespan={LOOKBACK_DAYS}d&maxrecords={max_records}&sort=HybridRel"
    last_err = ""
    for attempt in range(len(MEDIA_SEARCH_RETRY_DELAYS) + 1):
        text, err = fetch(url)
        time.sleep(MEDIA_SEARCH_SLEEP_SECONDS)
        if err == "HTTP 429":
            status["media_429_count"] += 1
            status["media_consecutive_429"] += 1
            detail["status"] = "failed"
            detail["error"] = err
            last_err = err
            if attempt < len(MEDIA_SEARCH_RETRY_DELAYS) and status["media_consecutive_429"] < MAX_CONSECUTIVE_MEDIA_429:
                time.sleep(MEDIA_SEARCH_RETRY_DELAYS[attempt])
                continue
        if err or not text:
            status["media_failed"] += 1
            detail["status"] = "failed"
            detail["error"] = err or "empty response"
            status["notes"].append({"media_query": query[:180], "error": err or "empty response"})
            return []
        try:
            data = json.loads(text)
        except Exception as exc:
            status["media_failed"] += 1
            detail["status"] = "failed"
            detail["error"] = f"invalid json: {str(exc)[:120]}"
            status["notes"].append({"media_query": query[:180], "error": f"invalid json: {str(exc)[:120]}"})
            return []
        status["media_consecutive_429"] = 0
        status["media_queries_checked"] += 1
        articles = data.get("articles") or []
        detail["articles_returned"] = len(articles)
        return articles
    status["media_failed"] += 1
    detail["status"] = "failed"
    detail["error"] = last_err or "request failed"
    status["notes"].append({"media_query": query[:180], "error": last_err or "request failed"})
    return []


def gdelt_articles_to_candidates(
    articles: list[dict[str, Any]],
    owner_name: str,
    source_query: str,
    status: dict[str, Any],
    media_sources: list[dict[str, str]],
    monitor_scope: str = "competitor",
    brand_name: str | None = None,
    max_records: int = MAX_NEWS_MENTIONS_PER_COMPETITOR,
) -> list[Candidate]:
    result = []
    detail = status.get("_current_media_query_detail") or {}
    for item in articles[:max_records]:
        art_url = item.get("url") or ""
        title = clean_text(item.get("title") or "")
        if is_noise_title(title):
            add_media_discard(detail, "noise")
            continue
        raw_domain = clean_text(item.get("domain") or urlparse(art_url).netloc.replace("www.", ""))
        media_name = media_name_from_domain(raw_domain, media_sources)
        published = to_iso_date(item.get("seendate") or item.get("datetime") or "")
        if not art_url:
            add_media_discard(detail, "missing_url")
            continue
        if not published:
            add_media_discard(detail, "no_date")
            continue
        if not date_in_window(published):
            add_media_discard(detail, "date_outside_window")
            continue
        c = Candidate(owner_name, "СМИ", source_query, normalize_url(art_url, keep_query=True), title or "СМИ-упоминание", media_name, "СМИ", published)
        c.monitor_scope = monitor_scope
        result.append(c)
    return result


def gdelt_mentions(competitor: dict[str, Any], status: dict[str, Any], media_sources: list[dict[str, str]]) -> list[Candidate]:
    name = str(competitor.get("name") or competitor.get("agency") or "").strip()
    if not name or len(name) < 3:
        status["media_queries_skipped"] += 1
        return []
    query = f'"{name}" (брендинг OR агентство OR branding OR design OR айдентика OR ребрендинг OR нейминг OR упаковка)'
    detail = new_media_query_diagnostic(query, name, "competitor")
    status["media_query_details"].append(detail)
    status["_current_media_query_detail"] = detail
    articles = gdelt_search(query, status, MAX_NEWS_MENTIONS_PER_COMPETITOR, detail)
    return gdelt_articles_to_candidates(articles, name, query, status, media_sources, "competitor", max_records=MAX_NEWS_MENTIONS_PER_COMPETITOR)


def gdelt_client_mentions(client: dict[str, str], status: dict[str, Any], media_sources: list[dict[str, str]]) -> list[Candidate]:
    name = str(client.get("name") or "").strip()
    if not name or len(name) < 3:
        status["media_queries_skipped"] += 1
        return []
    context = " OR ".join(["икра", "рыба", "морепродукты", "деликатесы", "продукты", "ритейл", "бренд", "упаковка", "производство"])
    query = f'"{name}" ({context})'
    detail = new_media_query_diagnostic(query, name, "client_brand")
    status["media_query_details"].append(detail)
    status["_current_media_query_detail"] = detail
    articles = gdelt_search(query, status, MAX_NEWS_MENTIONS_PER_CLIENT, detail)
    candidates = gdelt_articles_to_candidates(articles, "Клиенты Serenity", query, status, media_sources, "client_brand", brand_name=name, max_records=MAX_NEWS_MENTIONS_PER_CLIENT)
    # Подмешиваем бренд в текст якоря, чтобы detect_brands нашел его даже если в заголовке СМИ он сокращен.
    for c in candidates:
        c.anchor = f"{c.anchor} {name}"
    return candidates


def collect() -> None:
    sources = read_json(SOURCES_PATH, [])
    competitors = read_json(COMPETITORS_PATH, [])
    if not isinstance(sources, list):
        raise SystemExit("data/sources.json must be a list")
    if not isinstance(competitors, list):
        competitors = []
    media_sources = load_media_sources()
    client_brands = load_client_brands()

    status = {
        "last_run": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "mode": "last_7_days_window",
        "window_start": WINDOW_START.isoformat(),
        "window_end": TODAY,
        "sources_total": len(sources),
        "sources_checked": 0,
        "sources_skipped": 0,
        "sources_failed": 0,
        "media_queries_total": min(len(client_brands) + min(len(competitors), MAX_MEDIA_COMPETITOR_QUERIES_PER_RUN), len(client_brands) + len(competitors)),
        "media_queries_available": len(competitors) + len(client_brands),
        "media_query_limit_competitors": MAX_MEDIA_COMPETITOR_QUERIES_PER_RUN,
        "media_query_limit_total": len(client_brands) + min(len(competitors), MAX_MEDIA_COMPETITOR_QUERIES_PER_RUN),
        "client_brands_total": len(client_brands),
        "media_queries_checked": 0,
        "media_failed": 0,
        "media_429_count": 0,
        "media_findings_total": 0,
        "media_queries_skipped": 0,
        "media_status": "ok",
        "media_consecutive_429": 0,
        "media_query_details": [],
        "findings_total": 0,
        "undated_candidates_skipped": 0,
        "duplicates_skipped": 0,
        "notes": [],
    }

    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    detail_budget = [MAX_DETAIL_FETCHES]

    for source in sources:
        candidates = collect_candidates_for_source(source, status)
        emitted = 0
        for c in candidates:
            if emitted >= MAX_FINDINGS_PER_SOURCE:
                break
            key = (c.competitor, url_key(c.url))
            if key in seen:
                status["duplicates_skipped"] += 1
                continue
            finding = make_finding(c, detail_budget)
            if not finding:
                status["undated_candidates_skipped"] += 1
                continue
            seen.add(key)
            findings.append(finding)
            emitted += 1

    # СМИ ищем отдельно за последние 7 дней: сначала по текущим клиентам Serenity, затем по агентствам.
    for client in client_brands:
        if status["media_consecutive_429"] >= MAX_CONSECUTIVE_MEDIA_429:
            remaining = len(client_brands) - client_brands.index(client) + min(len(competitors), MAX_MEDIA_COMPETITOR_QUERIES_PER_RUN)
            status["media_queries_skipped"] += remaining
            status["media_status"] = "rate_limited"
            status["notes"].append({"media": "stopped_after_consecutive_429", "skipped": remaining})
            break
        for c in gdelt_client_mentions(client, status, media_sources):
            key = (c.competitor, url_key(c.url))
            if key in seen:
                status["duplicates_skipped"] += 1
                add_media_discard(status.get("_current_media_query_detail") or {}, "duplicate")
                continue
            finding = make_finding(c, detail_budget)
            if not finding:
                add_media_discard(status.get("_current_media_query_detail") or {}, "page_read_error_or_date_missing_or_noise")
                continue
            # Явно фиксируем бренд-клиент, чтобы он появился во вкладке «Бренды и клиенты».
            client_name = str(client.get("name") or "").strip()
            if client_name:
                existing = [b.get("name") for b in finding.get("mentioned_brands", []) if isinstance(b, dict)]
                if client_name not in existing:
                    finding.setdefault("mentioned_brands", []).append({
                        "name": client_name,
                        "category": client.get("category") or "клиент Serenity",
                        "context": "мониторинг текущих клиентов Serenity"
                    })
            seen.add(key)
            findings.append(finding)
            status["media_findings_total"] += 1
            (status.get("_current_media_query_detail") or {}).update({"findings_saved": (status.get("_current_media_query_detail") or {}).get("findings_saved", 0) + 1})

    ranked_competitors = sorted(competitors, key=lambda item: int(str(item.get("rank") or 9999).split(".")[0]) if str(item.get("rank") or "").split(".")[0].isdigit() else 9999)
    selected_competitors = ranked_competitors[:MAX_MEDIA_COMPETITOR_QUERIES_PER_RUN]
    skipped_competitors = ranked_competitors[MAX_MEDIA_COMPETITOR_QUERIES_PER_RUN:]
    for comp in skipped_competitors:
        name = str(comp.get("name") or comp.get("agency") or "").strip()
        if name:
            status["media_queries_skipped"] += 1
            status["media_query_details"].append({"query": name, "owner": name, "scope": "competitor", "status": "skipped", "error": "outside_per_run_limit", "articles_returned": 0, "findings_saved": 0, "discard_reasons": {}})

    if status["media_consecutive_429"] < MAX_CONSECUTIVE_MEDIA_429:
        for index, comp in enumerate(selected_competitors):
            if status["media_consecutive_429"] >= MAX_CONSECUTIVE_MEDIA_429:
                remaining = len(selected_competitors) - index
                status["media_queries_skipped"] += remaining
                status["notes"].append({"media": "stopped_after_consecutive_429", "skipped": remaining})
                break
            for c in gdelt_mentions(comp, status, media_sources):
                key = (c.competitor, url_key(c.url))
                if key in seen:
                    status["duplicates_skipped"] += 1
                    add_media_discard(status.get("_current_media_query_detail") or {}, "duplicate")
                    continue
                finding = make_finding(c, detail_budget)
                if not finding:
                    add_media_discard(status.get("_current_media_query_detail") or {}, "page_read_error_or_date_missing_or_noise")
                    continue
                seen.add(key)
                findings.append(finding)
                status["media_findings_total"] += 1
                (status.get("_current_media_query_detail") or {}).update({"findings_saved": (status.get("_current_media_query_detail") or {}).get("findings_saved", 0) + 1})

    if status["media_consecutive_429"] >= MAX_CONSECUTIVE_MEDIA_429:
        status["media_status"] = "rate_limited"
    elif status["media_failed"]:
        status["media_status"] = "partial"
    else:
        status["media_status"] = "ok"
    status.pop("_current_media_query_detail", None)
    findings.sort(key=lambda x: (x.get("date", ""), x.get("competitor", "")), reverse=True)
    status["findings_total"] = len(findings)
    write_json(FINDINGS_PATH, findings)
    write_json(STATUS_PATH, status)
    write_json(LAST_RUN_PATH, {
        "last_run": status["last_run"],
        "mode": status["mode"],
        "window_start": status["window_start"],
        "window_end": status["window_end"],
        "findings_total": len(findings),
        "sources_checked": status["sources_checked"],
        "media_queries_checked": status["media_queries_checked"],
    })
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    collect()
