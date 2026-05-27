"""Report generation (export, SVG chart, HTML report, email, Nextcloud upload) for CGM Monitor."""

import csv
import io
import logging
import shutil
from datetime import date as py_date, datetime, time as py_time
from pathlib import Path

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CONF_NEXTCLOUD_PASSWORD,
    CONF_NEXTCLOUD_PATH,
    CONF_NEXTCLOUD_URL,
    CONF_NEXTCLOUD_USER,
    CONF_REPORT_ZIP_PASSWORD,
    CONF_CRITICAL_LOW_THRESHOLD,
    CONF_EVENT_DOSE,
    CONF_EVENT_NOTE,
    CONF_EVENT_START,
    CONF_EVENT_TYPE,
    CONF_EVENT_UNIT,
    CONF_HIGH_THRESHOLD,
    CONF_LOW_THRESHOLD,
    CONF_VERY_HIGH_THRESHOLD,
    CONF_VERY_LOW_THRESHOLD,
    DEFAULT_CRITICAL_LOW_THRESHOLD,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_VERY_HIGH_THRESHOLD,
    DEFAULT_VERY_LOW_THRESHOLD,
    DOMAIN,
    STORES_KEY,
    UNIT_MG_DL,
)

_LOGGER = logging.getLogger(__name__)

REPORTS_DIR = "cgm_reports"

_THRESHOLD_KEYS = [
    CONF_CRITICAL_LOW_THRESHOLD,
    CONF_VERY_LOW_THRESHOLD,
    CONF_LOW_THRESHOLD,
    CONF_HIGH_THRESHOLD,
    CONF_VERY_HIGH_THRESHOLD,
]
_THRESHOLD_DEFAULTS = {
    CONF_CRITICAL_LOW_THRESHOLD: DEFAULT_CRITICAL_LOW_THRESHOLD,
    CONF_VERY_LOW_THRESHOLD: DEFAULT_VERY_LOW_THRESHOLD,
    CONF_LOW_THRESHOLD: DEFAULT_LOW_THRESHOLD,
    CONF_HIGH_THRESHOLD: DEFAULT_HIGH_THRESHOLD,
    CONF_VERY_HIGH_THRESHOLD: DEFAULT_VERY_HIGH_THRESHOLD,
}

# ── Helpers ────────────────────────────────────────────────────────────────────


def _out_dir(hass: HomeAssistant, report_date: py_date) -> Path:
    p = Path(hass.config.config_dir) / REPORTS_DIR / report_date.isoformat()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _file_prefix(subject_name: str) -> str:
    return subject_name.replace(" ", "_")


def _get_thresholds(hass: HomeAssistant, slug: str) -> dict[str, float]:
    result = {}
    for key in _THRESHOLD_KEYS:
        state = hass.states.get(f"number.{slug}_{key}")
        try:
            result[key] = float(state.state) if state else _THRESHOLD_DEFAULTS[key]
        except (ValueError, TypeError):
            result[key] = _THRESHOLD_DEFAULTS[key]
    return result


async def _async_get_history(
    hass: HomeAssistant,
    entity_ids: list[str],
    start_dt: datetime,
    end_dt: datetime,
) -> dict[str, list]:
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.history import get_significant_states

    def _fetch():
        return get_significant_states(
            hass,
            start_dt,
            end_dt,
            entity_ids,
            significant_changes_only=False,
            minimal_response=False,
        )

    return await get_instance(hass).async_add_executor_job(_fetch)


def _value_at(history_list: list, target_dt: datetime) -> str:
    result = ""
    for state in history_list:
        lc = state.last_changed
        if lc.tzinfo is None:
            lc = dt_util.as_local(lc)
        if lc <= target_dt:
            result = state.state
        else:
            break
    return result


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ── Export ─────────────────────────────────────────────────────────────────────


async def async_export_report(hass: HomeAssistant, report_date: py_date) -> list[Path]:
    """Export glucose history and calendar events to CSV for every subject."""
    out = Path(hass.config.config_dir) / REPORTS_DIR / report_date.isoformat()
    if out.exists():
        await hass.async_add_executor_job(shutil.rmtree, out)
    out = _out_dir(hass, report_date)
    date_str = report_date.isoformat()
    start_dt = dt_util.as_local(datetime.combine(report_date, py_time.min))
    end_dt = dt_util.as_local(datetime.combine(report_date, py_time.max))
    stores: dict = hass.data.get(DOMAIN, {}).get(STORES_KEY, {})
    written: list[Path] = []

    for subject_name, store in stores.items():
        slug = slugify(subject_name)
        prefix = _file_prefix(subject_name)

        entity_ids = [
            f"sensor.{slug}",
            f"sensor.{slug}_trend",
            f"sensor.{slug}_state",
            f"sensor.{slug}_priority",
        ]
        history = await _async_get_history(hass, entity_ids, start_dt, end_dt)
        thresholds = _get_thresholds(hass, slug)

        glucose_hist = history.get(f"sensor.{slug}", [])
        trend_hist = history.get(f"sensor.{slug}_trend", [])
        state_hist = history.get(f"sensor.{slug}_state", [])
        priority_hist = history.get(f"sensor.{slug}_priority", [])

        glucose_rows = []
        for s in glucose_hist:
            ts = s.last_changed
            if ts.tzinfo is None:
                ts = dt_util.as_local(ts)
            glucose_rows.append(
                {
                    "timestamp": ts.isoformat(),
                    "glucose": s.state,
                    "trend": _value_at(trend_hist, ts),
                    "state": _value_at(state_hist, ts),
                    "priority": _value_at(priority_hist, ts),
                    **{k: thresholds[k] for k in _THRESHOLD_KEYS},
                }
            )

        glucose_file = out / f"{prefix}_{date_str}.csv"
        fieldnames = ["timestamp", "glucose", "trend", "state", "priority"] + _THRESHOLD_KEYS
        await hass.async_add_executor_job(_write_csv, glucose_file, glucose_rows, fieldnames)
        written.append(glucose_file)

        events_file = out / f"{prefix}_{date_str}_events.csv"
        event_rows = [
            {
                "timestamp": e.get(CONF_EVENT_START, ""),
                "type": e.get(CONF_EVENT_TYPE, ""),
                "unit": e.get(CONF_EVENT_UNIT, ""),
                "dose": e.get(CONF_EVENT_DOSE, ""),
                "note": e.get(CONF_EVENT_NOTE, ""),
            }
            for e in store.get_events_in_range(start_dt, end_dt)
        ]
        await hass.async_add_executor_job(
            _write_csv, events_file, event_rows,
            ["timestamp", "type", "unit", "dose", "note"],
        )
        written.append(events_file)

    _LOGGER.info("CGM Monitor export_report: wrote %d files to %s", len(written), out)
    return written


# ── Generate ───────────────────────────────────────────────────────────────────


async def async_generate_report(hass: HomeAssistant, report_date: py_date) -> Path:
    """Merge CSVs, generate per-subject SVG charts, write a combined HTML report."""
    out = _out_dir(hass, report_date)
    date_str = report_date.isoformat()
    stores: dict = hass.data.get(DOMAIN, {}).get(STORES_KEY, {})
    subject_names = list(stores.keys())
    html_path = out / f"CGM_Report_{date_str}.html"

    await hass.async_add_executor_job(_generate_report_files, subject_names, out, date_str, html_path)
    _LOGGER.info("CGM Monitor generate_report: wrote report to %s", html_path)
    return html_path


def _generate_report_files(
    subject_names: list[str],
    out: Path,
    date_str: str,
    html_path: Path,
) -> None:
    subject_sections = []

    for subject_name in subject_names:
        prefix = _file_prefix(subject_name)
        glucose_file = out / f"{prefix}_{date_str}.csv"
        events_file = out / f"{prefix}_{date_str}_events.csv"
        full_file = out / f"{prefix}_{date_str}_full.csv"

        _write_full_csv(glucose_file, events_file, full_file)

        glucose_data, thresholds = _load_glucose_csv(glucose_file)
        events = _load_events_csv(events_file)
        svg = _svg_chart(subject_name, glucose_data, events, thresholds, date_str)

        svg_file = out / f"{prefix}_{date_str}.svg"
        svg_file.write_text(svg, encoding="utf-8")

        subject_sections.append((subject_name, svg, full_file.name))

    html = _build_html(date_str, subject_sections)
    html_path.write_text(html, encoding="utf-8")


def _write_full_csv(glucose_file: Path, events_file: Path, full_file: Path) -> None:
    rows = []
    if glucose_file.exists():
        with open(glucose_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["source"] = "glucose"
                rows.append(row)
    if events_file.exists():
        with open(events_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["source"] = "event"
                rows.append(row)

    rows.sort(key=lambda r: r.get("timestamp", ""))
    if not rows:
        return

    fieldnames = list(dict.fromkeys(k for r in rows for k in r))
    _write_csv(full_file, rows, fieldnames)


def _load_glucose_csv(
    path: Path,
) -> tuple[list[tuple[datetime, float]], dict[str, float]]:
    glucose_data: list[tuple[datetime, float]] = []
    thresholds: dict[str, float] = {}
    if not path.exists():
        return glucose_data, thresholds
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                ts = datetime.fromisoformat(row["timestamp"])
                glucose_data.append((ts, float(row["glucose"])))
                if not thresholds:
                    thresholds = {k: float(row.get(k, _THRESHOLD_DEFAULTS[k])) for k in _THRESHOLD_KEYS}
            except (ValueError, KeyError):
                pass
    return glucose_data, thresholds


def _load_events_csv(path: Path) -> list[dict]:
    events = []
    if not path.exists():
        return events
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                ts = datetime.fromisoformat(row["timestamp"])
                etype = row.get("type", "Custom")
                dose = row.get("dose", "")
                unit = row.get("unit", "")
                label = f"{dose} {unit}".strip() if dose else etype
                events.append({"time": ts, "type": etype, "label": label})
            except (ValueError, KeyError):
                pass
    return events


# ── SVG chart ─────────────────────────────────────────────────────────────────

_W, _H = 1200, 440
_ML, _MR, _MT, _MB = 70, 40, 55, 65
_PW = _W - _ML - _MR   # 1090
_PH = _H - _MT - _MB   # 320
_Y_MAX = 400.0

_EVENT_COLORS = {"Insulin": "#7b1fa2", "Meal": "#2e7d32", "Custom": "#e65100"}
_EVENT_DEFAULT_COLOR = "#e65100"


def _tx(dt: datetime) -> float:
    m = dt.hour * 60 + dt.minute + dt.second / 60.0
    return round(_ML + (m / 1440.0) * _PW, 2)


def _ty(g: float) -> float:
    return round(_MT + _PH * (1.0 - min(max(g, 0.0), _Y_MAX) / _Y_MAX), 2)


def _triangle(cx: float, cy: float, size: float = 8) -> str:
    return f"{cx},{cy - size} {cx + size * 0.85},{cy + size * 0.5} {cx - size * 0.85},{cy + size * 0.5}"


def _diamond(cx: float, cy: float, size: float = 8) -> str:
    return f"{cx},{cy - size} {cx + size * 0.7},{cy} {cx},{cy + size} {cx - size * 0.7},{cy}"


def _svg_chart(
    subject_name: str,
    glucose_data: list[tuple[datetime, float]],
    events: list[dict],
    thresholds: dict[str, float],
    date_str: str,
) -> str:
    p: list[str] = []

    def e(tag: str) -> None:
        p.append(tag)

    e(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}" '
      f'style="font-family:Arial,Helvetica,sans-serif;max-width:100%">')
    e(f'<rect width="{_W}" height="{_H}" fill="#f8f9fa"/>')
    e(f'<defs><clipPath id="plot"><rect x="{_ML}" y="{_MT}" width="{_PW}" height="{_PH}"/></clipPath></defs>')
    e(f'<rect x="{_ML}" y="{_MT}" width="{_PW}" height="{_PH}" fill="white" stroke="#ddd" stroke-width="1"/>')

    # Threshold bands
    if thresholds:
        cl = thresholds[CONF_CRITICAL_LOW_THRESHOLD]
        vl = thresholds[CONF_VERY_LOW_THRESHOLD]
        lo = thresholds[CONF_LOW_THRESHOLD]
        hi = thresholds[CONF_HIGH_THRESHOLD]
        vh = thresholds[CONF_VERY_HIGH_THRESHOLD]

        for g0, g1, color, opacity in [
            (0,   cl,    "#c62828", 0.12),
            (cl,  vl,    "#e53935", 0.09),
            (vl,  lo,    "#fb8c00", 0.09),
            (lo,  hi,    "#43a047", 0.07),
            (hi,  vh,    "#fb8c00", 0.09),
            (vh,  _Y_MAX, "#e53935", 0.11),
        ]:
            bx, by = _ML, _ty(g1)
            bh = _ty(g0) - _ty(g1)
            e(f'<rect x="{bx}" y="{by}" width="{_PW}" height="{bh}" '
              f'fill="{color}" opacity="{opacity}" clip-path="url(#plot)"/>')

        for val, color in [(cl, "#c62828"), (vl, "#e53935"), (lo, "#fb8c00"),
                           (hi, "#fb8c00"), (vh, "#e53935")]:
            y = _ty(val)
            e(f'<line x1="{_ML}" y1="{y}" x2="{_ML + _PW}" y2="{y}" '
              f'stroke="{color}" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.65" clip-path="url(#plot)"/>')

    # Horizontal grid lines
    for g in range(0, 401, 50):
        y = _ty(g)
        e(f'<line x1="{_ML}" y1="{y}" x2="{_ML + _PW}" y2="{y}" '
          f'stroke="#ccc" stroke-width="0.5" stroke-dasharray="3,3"/>')

    # Glucose polyline
    if glucose_data:
        pts = " ".join(f"{_tx(dt)},{_ty(g)}" for dt, g in glucose_data)
        e(f'<polyline points="{pts}" fill="none" stroke="#1565c0" stroke-width="2.5" '
          f'stroke-linejoin="round" stroke-linecap="round" clip-path="url(#plot)"/>')
        for dt, g in glucose_data:
            e(f'<circle cx="{_tx(dt)}" cy="{_ty(g)}" r="3.5" fill="#1565c0" clip-path="url(#plot)"/>')

    # Event markers — fixed at the bottom of the plot
    event_y = _ty(18)
    for ev in events:
        ex = _tx(ev["time"])
        color = _EVENT_COLORS.get(ev["type"], _EVENT_DEFAULT_COLOR)
        # Dotted vertical guide line from bottom of plot up to marker
        e(f'<line x1="{ex}" y1="{event_y + 12}" x2="{ex}" y2="{_MT + _PH}" '
          f'stroke="{color}" stroke-width="1" stroke-dasharray="3,3" opacity="0.55" clip-path="url(#plot)"/>')
        if ev["type"] == "Meal":
            e(f'<circle cx="{ex}" cy="{event_y}" r="7" fill="{color}" opacity="0.85" clip-path="url(#plot)"/>')
        elif ev["type"] == "Insulin":
            e(f'<polygon points="{_triangle(ex, event_y)}" fill="{color}" opacity="0.85" clip-path="url(#plot)"/>')
        else:
            e(f'<polygon points="{_diamond(ex, event_y)}" fill="{color}" opacity="0.85" clip-path="url(#plot)"/>')
        e(f'<text x="{ex}" y="{event_y - 12}" text-anchor="middle" font-size="9" '
          f'fill="{color}" clip-path="url(#plot)">{ev["label"]}</text>')

    # X axis — hours
    y_bottom = _MT + _PH
    for h in range(0, 25, 2):
        x = round(_ML + (h / 24.0) * _PW, 2)
        e(f'<line x1="{x}" y1="{y_bottom}" x2="{x}" y2="{y_bottom + 5}" stroke="#666" stroke-width="1"/>')
        e(f'<text x="{x}" y="{y_bottom + 18}" text-anchor="middle" font-size="11" fill="#555">{h:02d}:00</text>')

    # Y axis — glucose values
    for g in range(0, 401, 50):
        y = _ty(g)
        e(f'<line x1="{_ML - 5}" y1="{y}" x2="{_ML}" y2="{y}" stroke="#666" stroke-width="1"/>')
        e(f'<text x="{_ML - 9}" y="{y + 4}" text-anchor="end" font-size="11" fill="#555">{g}</text>')

    # Axis labels
    cx = _ML + _PW / 2
    e(f'<text x="{cx}" y="{_H - 8}" text-anchor="middle" font-size="12" fill="#666">Time</text>')
    e(f'<text x="14" y="{_MT + _PH / 2}" text-anchor="middle" font-size="12" fill="#666" '
      f'transform="rotate(-90,14,{_MT + _PH / 2})">Glucose ({UNIT_MG_DL})</text>')

    # Title
    e(f'<text x="{_ML + _PW / 2}" y="32" text-anchor="middle" font-size="16" '
      f'font-weight="bold" fill="#333">{subject_name}  —  {date_str}</text>')

    # Legend
    legend_items: list[tuple[str, str, str]] = [("Glucose", "line", "#1565c0")]
    seen = {ev["type"] for ev in events}
    for etype, shape in [("Insulin", "triangle"), ("Meal", "circle"), ("Custom", "diamond")]:
        if etype in seen:
            legend_items.append((etype, shape, _EVENT_COLORS[etype]))

    lx = _ML + _PW - 10
    ly = _MT + 15
    box_w, box_h = 110, len(legend_items) * 20 + 8
    e(f'<rect x="{lx - box_w}" y="{ly - 12}" width="{box_w}" height="{box_h}" '
      f'fill="white" opacity="0.85" rx="4" stroke="#ccc" stroke-width="0.5"/>')
    for label, shape, color in legend_items:
        sym_x = lx - box_w + 14
        if shape == "line":
            e(f'<line x1="{sym_x - 8}" y1="{ly}" x2="{sym_x + 8}" y2="{ly}" '
              f'stroke="{color}" stroke-width="2.5"/>')
        elif shape == "circle":
            e(f'<circle cx="{sym_x}" cy="{ly}" r="5" fill="{color}"/>')
        elif shape == "triangle":
            e(f'<polygon points="{_triangle(sym_x, ly, 6)}" fill="{color}"/>')
        elif shape == "diamond":
            e(f'<polygon points="{_diamond(sym_x, ly, 6)}" fill="{color}"/>')
        e(f'<text x="{sym_x + 14}" y="{ly + 4}" font-size="11" fill="#444">{label}</text>')
        ly += 20

    e('</svg>')
    return "\n".join(p)


# ── HTML report ────────────────────────────────────────────────────────────────


def _build_html(date_str: str, subject_sections: list[tuple[str, str, str]]) -> str:
    subjects_html = ""
    for subject_name, svg, full_csv_name in subject_sections:
        subjects_html += f"""
    <div class="subject">
      <h2>{subject_name}</h2>
      <div class="chart">{svg}</div>
      <p class="csv-note">Full data: <code>{full_csv_name}</code></p>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>CGM Daily Report — {date_str}</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; background: #f0f2f5;
           margin: 0; padding: 24px; color: #333; }}
    h1   {{ font-size: 1.6rem; margin-bottom: 24px; }}
    .subject {{ background: white; border-radius: 10px; padding: 24px;
                margin-bottom: 28px; box-shadow: 0 2px 6px rgba(0,0,0,.1); }}
    h2   {{ font-size: 1.2rem; color: #1565c0; margin: 0 0 16px; }}
    .chart {{ width: 100%; overflow-x: auto; }}
    .chart svg {{ display: block; width: 100%; height: auto; }}
    .csv-note {{ font-size: .8rem; color: #777; margin: 10px 0 0; }}
  </style>
</head>
<body>
  <h1>CGM Daily Report — {date_str}</h1>
{subjects_html}
</body>
</html>"""


# ── Send ───────────────────────────────────────────────────────────────────────


async def async_send_report(
    hass: HomeAssistant,
    report_date: py_date,
    notify_service: str,
    recipients: list[str],
) -> None:
    """Send the HTML report and full CSVs via a configured HA notify (SMTP) service."""
    out = _out_dir(hass, report_date)
    date_str = report_date.isoformat()
    stores: dict = hass.data.get(DOMAIN, {}).get(STORES_KEY, {})

    # HA's SMTP component validates attachment paths against allowlist_external_dirs.
    # Add the reports root so all dated subfolders are accepted.
    reports_root = Path(hass.config.config_dir) / REPORTS_DIR
    hass.config.allowlist_external_dirs = frozenset(
        hass.config.allowlist_external_dirs | {reports_root}
    )

    attachments: list[str] = []

    html_path = out / f"CGM_Report_{date_str}.html"
    if html_path.exists():
        attachments.append(str(html_path))

    for subject_name in stores:
        prefix = _file_prefix(subject_name)
        for suffix in ("", "_events", "_full"):
            f = out / f"{prefix}_{date_str}{suffix}.csv"
            if f.exists():
                attachments.append(str(f))

    if not attachments:
        _LOGGER.warning("CGM Monitor send_report: no report files found for %s in %s", date_str, out)
        return

    service_name = notify_service.split(".", 1)[-1] if "." in notify_service else notify_service
    service_data: dict = {
        "title": f"CGM Daily Report — {date_str}",
        "message": (
            f"CGM report for {date_str}.\n"
            f"Subjects: {', '.join(stores.keys())}\n"
            f"Attached: {len(attachments)} file(s)."
        ),
        "data": {"images": attachments},
    }
    if recipients:
        service_data["target"] = recipients

    await hass.services.async_call("notify", service_name, service_data)
    _LOGGER.info(
        "CGM Monitor send_report: sent %d files via notify.%s", len(attachments), service_name
    )


# ── Nextcloud upload ───────────────────────────────────────────────────────────


def _create_encrypted_zip(csv_file: Path, zip_password: bytes) -> bytes:
    import pyzipper
    buf = io.BytesIO()
    with pyzipper.AESZipFile(buf, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(zip_password)
        zf.write(csv_file, csv_file.name)
    return buf.getvalue()


async def async_upload_report(hass: HomeAssistant, report_date: py_date, nc_config: dict) -> list[str]:
    """Create AES-256 encrypted ZIP per subject and upload via WebDAV to Nextcloud."""
    out = _out_dir(hass, report_date)
    date_str = report_date.isoformat()
    stores: dict = hass.data.get(DOMAIN, {}).get(STORES_KEY, {})

    nc_url = nc_config[CONF_NEXTCLOUD_URL].rstrip("/")
    nc_user = nc_config[CONF_NEXTCLOUD_USER]
    nc_pass = nc_config[CONF_NEXTCLOUD_PASSWORD]
    nc_path = nc_config.get(CONF_NEXTCLOUD_PATH, "CGM_Reports").strip("/")
    zip_password = nc_config[CONF_REPORT_ZIP_PASSWORD].encode()

    auth = aiohttp.BasicAuth(nc_user, nc_pass)
    session = aiohttp_client.async_get_clientsession(hass)
    uploaded: list[str] = []

    folder_url = f"{nc_url}/remote.php/webdav/{nc_path}"
    try:
        await session.request("MKCOL", folder_url, auth=auth)
    except Exception:
        pass

    for subject_name in stores:
        prefix = _file_prefix(subject_name)
        csv_file = out / f"{prefix}_{date_str}.csv"

        if not csv_file.exists():
            _LOGGER.warning(
                "CGM Monitor upload_report: no CSV for '%s' on %s — run export_report first",
                subject_name, date_str,
            )
            continue

        zip_data = await hass.async_add_executor_job(_create_encrypted_zip, csv_file, zip_password)
        zip_filename = f"{prefix}_{date_str}_glucose.zip"
        upload_url = f"{folder_url}/{zip_filename}"

        resp = await session.put(upload_url, data=zip_data, auth=auth)
        if resp.status in (200, 201, 204):
            uploaded.append(zip_filename)
            _LOGGER.info("CGM Monitor upload_report: uploaded %s", zip_filename)
        else:
            body = await resp.text()
            _LOGGER.error(
                "CGM Monitor upload_report: failed to upload %s — HTTP %s: %s",
                zip_filename, resp.status, body[:200],
            )

    return uploaded
