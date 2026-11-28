"""Dark dashboard theme (Sprint 00-21): CSS, KPI cards and data-source badges.

Base colours come from ``.streamlit/config.toml``; this module adds the card, navigation
and badge styling on top. HTML helpers escape every value they render.
"""

from __future__ import annotations

from html import escape

PALETTE = {
    "background": "#0B1220",
    "surface": "#111A2E",
    "surface_raised": "#16213A",
    "border": "#22304D",
    "text": "#E6EDF6",
    "muted": "#93A3BD",
    "primary": "#2F6FDE",
    "ok": "#22C55E",
    "warn": "#EAB308",
    "missing": "#EF4444",
}

CSS = """
<style>
:root {
  --surface: #111A2E; --surface-raised: #16213A; --border: #22304D;
  --text: #E6EDF6; --muted: #93A3BD; --primary: #2F6FDE;
}
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1600px; }
header[data-testid="stHeader"] { background: transparent; }

/* Sidebar navigation: the main radio looks like a vertical menu. */
section[data-testid="stSidebar"] { background: #0D1526; border-right: 1px solid var(--border); }
section[data-testid="stSidebar"] div[role="radiogroup"] > label {
  padding: 0.55rem 0.75rem; margin: 0.1rem 0; border-radius: 8px; width: 100%;
  transition: background 0.15s ease;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover { background: #18243F; }
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
  background: var(--primary);
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display: none; }

/* App header */
.app-header { display: flex; align-items: center; gap: 0.9rem; margin-bottom: 0.2rem; }
.app-header .logo {
  width: 46px; height: 46px; border-radius: 10px; background: var(--surface-raised);
  border: 1px solid var(--border); display: flex; align-items: center; justify-content: center;
  font-size: 1.6rem;
}
.app-header h1 { font-size: 1.55rem; margin: 0; padding: 0; line-height: 1.2; }
.app-header p { margin: 0; color: var(--muted); font-size: 0.95rem; }

/* KPI cards */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.75rem; margin: 0.6rem 0 1rem 0; }
.kpi-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 0.85rem 1rem; display: flex; gap: 0.8rem; align-items: center; min-height: 92px; }
.kpi-icon { width: 44px; height: 44px; border-radius: 10px; flex: 0 0 44px;
  display: flex; align-items: center; justify-content: center; font-size: 1.35rem; }
.kpi-label { color: var(--muted); font-size: 0.82rem; line-height: 1.2; }
.kpi-value { color: var(--text); font-size: 1.55rem; font-weight: 700; line-height: 1.25; }
.kpi-sub { font-size: 0.82rem; font-weight: 600; }

/* Panels */
.panel-title { font-weight: 650; font-size: 1.02rem; margin: 0.2rem 0 0.4rem 0; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }

/* Data-source badges */
.source-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.1rem 0 0.8rem 0; }
.source-badge { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.76rem;
  padding: 0.18rem 0.55rem; border-radius: 999px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted); }
.source-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

/* Small screens: tighter header and two KPI columns. */
@media (max-width: 760px) {
  .app-header h1 { font-size: 1.2rem; }
  .app-header p { font-size: 0.82rem; }
  .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .kpi-value { font-size: 1.25rem; }
  .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
}
</style>
"""


def header_html(title: str, subtitle: str, icon: str = "🏙️") -> str:
    return (
        '<div class="app-header">'
        f'<div class="logo">{escape(icon)}</div>'
        f"<div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>"
        "</div>"
    )


def kpi_card_html(label: str, value: str, sub: str = "", color: str = "#2F6FDE",
                  icon: str = "■") -> str:
    """One KPI card; ``color`` tints the icon tile and the sub-line."""
    tint = f"{color}33"  # ~20% alpha background for the icon tile
    sub_html = f'<div class="kpi-sub" style="color:{escape(color)}">{escape(sub)}</div>' if sub else ""
    return (
        '<div class="kpi-card">'
        f'<div class="kpi-icon" style="background:{escape(tint)};color:{escape(color)}">'
        f"{escape(icon)}</div>"
        f'<div><div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value">{escape(value)}</div>{sub_html}</div>'
        "</div>"
    )


def kpi_grid_html(cards: list[str]) -> str:
    return '<div class="kpi-grid">' + "".join(cards) + "</div>"


def source_badges_html(entries: list[dict]) -> str:
    """Badges for data sources: green = in repo, amber = local-only file, red = missing."""
    badges = []
    for entry in entries:
        if not entry["available"]:
            color, state = PALETTE["missing"], "eksik"
        elif entry.get("local_only"):
            color, state = PALETTE["warn"], "yerel"
        else:
            color, state = PALETTE["ok"], "depoda"
        title = f"{entry['role']} · {entry['terms']} · Sprint {entry['sprint']} · {state}"
        badges.append(
            f'<span class="source-badge" title="{escape(title)}">'
            f'<span class="source-dot" style="background:{color}"></span>'
            f"{escape(entry['name'])}</span>"
        )
    return '<div class="source-row">' + "".join(badges) + "</div>"


def format_int(value: int) -> str:
    """Turkish thousands separator: 46563 → 46.563."""
    return f"{int(value):,}".replace(",", ".")


def format_pct(share: float, digits: int = 1) -> str:
    """Turkish percent: 0.175 → %17,5."""
    return "%" + f"{share * 100:.{digits}f}".replace(".", ",")
