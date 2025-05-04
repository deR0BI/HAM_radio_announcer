#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер «Анонсов экспедиций» с rdaward.ru
✓ корректно вытаскивает все RDA‑коды (даже внутри […])
✓ аккуратно вытаскивает даты/источник/добавлено
✓ умеет отдавать только новые записи (only_new=True)
"""

import html, re, requests
from datetime import datetime
from bs4 import BeautifulSoup

URL = "https://rdaward.ru"

# запоминаем id анонсов, чтобы не повторяться
_seen: set[str] = set()

RDA_RE = re.compile(r"[A-Z]{2}-\d{2}")           # OM‑07, NS‑44 …

# ─────────── helpers ───────────
def _clean_space(txt: str) -> str:
    """заменяем не‑разрывные пробелы и убираем лишние"""
    return re.sub(r"\s+", " ", txt.replace("\xa0", " ")).strip()


def _fetch_fragment() -> str:
    """отдаёт HTML‑фрагмент, который сайт вставляет JS‑ом"""
    page = requests.get(URL, timeout=20).text
    soup = BeautifulSoup(page, "html.parser")
    script = soup.find("script", string=re.compile(r"var\s+div_contents"))
    raw = re.search(r"var\s+div_contents\s*=\s*'(.+?)';", script.string, re.S).group(1)
    return html.unescape(raw).replace("\\'", "'")


def _unique_ordered(seq):
    seen = set()
    out  = []
    for i in seq:
        if i not in seen:
            out.append(i)
            seen.add(i)
    return out


# ─────────── main low‑level parse ───────────
def _parse() -> list[dict]:
    frag = BeautifulSoup(_fetch_fragment(), "html.parser")
    cards = frag.find_all("div", style=re.compile(r"border:1px solid"))
    out = []

    for card in cards:
        left, right = card.find_all("div", recursive=False)[:2]
        callsign = _clean_space(left.b.text)
        declared = _clean_space(left.span.text)

        right_text = _clean_space(right.get_text(" ", strip=True))

        # даты
        m_date = re.search(r"с\s*(\d{2}\.\d{2}\.\d{4}).*?по\s*(\d{2}\.\d{2}\.\d{4})", right_text)
        d_from, d_to = m_date.groups() if m_date else ("—", "—")

        # источник, добавлено
        m_src  = re.search(r"источник:\s*([^,•]+)", right_text, re.I)
        m_add  = re.search(r"добавлено:\s*(\d{2}\.\d{2}\.\d{4})", right_text)
        source = _clean_space(m_src.group(1)) if m_src else "—"
        added  = m_add.group(1) if m_add else "—"

        # RDA‑коды: берём ТЕКСТ целиком → ищем регэкспом → удаляем дубли сохраняя порядок
        rdas = _unique_ordered(RDA_RE.findall(right_text))

        out.append({
            "id": f"{callsign}_{declared}",
            "callsign": callsign,
            "date_from": d_from,
            "date_to":   d_to,
            "source":    source,
            "added":     added,
            "rdas":      rdas,
        })
    return out


# ─────────── публичная точка входа ───────────
def build_announcements_message(*, only_new=False, wrap: int = 10) -> str:
    """Возвращает красиво отформатированный текст.
       wrap — через сколько RDA делать перенос строки (0 = не переносить)."""
    global _seen
    items = _parse()

    if only_new:
        items = [i for i in items if i["id"] not in _seen]
    if not items:
        return ""

    _seen.update(i["id"] for i in items)

    blocks: list[str] = []
    for a in items:
        # красиво упаковываем RDA‑список
        if wrap:
            parts = [", ".join(a["rdas"][i:i + wrap]) for i in range(0, len(a["rdas"]), wrap)]
            rda_txt = ",\n".join(parts)
        else:
            rda_txt = ", ".join(a["rdas"])

        blocks.append(
            f"📡 <b>{a['callsign']}</b> "
            f"(<i>{a['date_from']}—{a['date_to']}</i>)\n"
            f"🏷️ <b>{len(a['rdas'])}</b> районов: {rda_txt}\n"
            f"🔗 источник: <i>{a['source']}</i> • ➕ {a['added']}"
        )
    return "\n\n".join(blocks)
