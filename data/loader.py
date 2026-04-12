import re
import io
from urllib.parse import quote
from html import escape

import requests
import streamlit as st
import pandas as pd

# ─── Constants ───────────────────────────────────────────────────────────────

REGISTRY_ID = "1K4OZ6wMkJFgW3gAvW4m4YJpwzFaPICB8hZIeKRVt5DU"

COL_SCHOOL  = "Название школы"
COL_CLUSTER = "Кластер"
COL_URL     = "Ссылка на таблицу с подробным описанием школы"

# ─── Utilities ───────────────────────────────────────────────────────────────

def _read_csv_utf8(url: str) -> pd.DataFrame:
    """Fetch a CSV URL and parse it as UTF-8 (Google Sheets returns UTF-8)."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.content.decode("utf-8")))


def _read_xlsx_sheet(spreadsheet_id: str, sheet_name: str) -> pd.DataFrame:
    """
    Download spreadsheet as XLSX and parse the named sheet.
    This is necessary because Google Sheets CSV export with sheet= parameter
    is unreliable for named sheets (returns first sheet instead).
    """
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    xl = pd.ExcelFile(io.BytesIO(resp.content))
    return xl.parse(sheet_name)


def _extract_sheet_id(url: str) -> str | None:
    """Extract spreadsheet ID from a Google Sheets URL."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", str(url))
    return match.group(1) if match else None

# ─── Registry ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_registry() -> pd.DataFrame:
    """
    Load the school registry.
    Returns DataFrame with columns: Название школы, Кластер, COL_URL, sheet_id.
    Drops rows with empty school name.
    """
    url = f"https://docs.google.com/spreadsheets/d/{REGISTRY_ID}/export?format=csv&gid=0"
    df = _read_csv_utf8(url)
    df = df[df[COL_SCHOOL].notna() & (df[COL_SCHOOL].str.strip() != "")].copy()
    df["sheet_id"] = df[COL_URL].apply(
        lambda x: _extract_sheet_id(x) if pd.notna(x) else None
    )
    return df[[COL_SCHOOL, COL_CLUSTER, COL_URL, "sheet_id"]].reset_index(drop=True)

# ─── МИНУТКА_ДАРОВАНИЯ ───────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_minutka(sheet_id: str) -> pd.DataFrame:
    """
    Load МИНУТКА_ДАРОВАНИЯ sheet from an individual school spreadsheet.
    Drops rows with non-numeric Занятие.
    Normalizes Процент выполнения to percentage float (e.g. 89.47).
    Handles both string "89,47%" format and decimal fraction 0.8947 from XLSX.
    """
    df = _read_xlsx_sheet(sheet_id, "МИНУТКА_ДАРОВАНИЯ")
    df.columns = df.columns.str.strip()

    df = df[pd.to_numeric(df["Занятие"], errors="coerce").notna()].copy()
    df["Занятие"] = df["Занятие"].astype(int)
    df["Поток"]   = pd.to_numeric(df["Поток"], errors="coerce")
    df["Количество учеников в школе"] = pd.to_numeric(
        df["Количество учеников в школе"], errors="coerce"
    )
    df["Количество сданных форм"] = pd.to_numeric(
        df["Количество сданных форм"], errors="coerce"
    )
    # Handle both "89,47%" string format and 0.8947 decimal fraction from XLSX
    pct_raw = df["Процент выполнения"]
    if pct_raw.dtype == object:
        # String format: "89,47%" — strip % and replace comma
        pct = (
            pct_raw.astype(str)
            .str.replace("%", "", regex=False)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
        )
    else:
        # Numeric from XLSX: may be decimal fraction (0.8947) or already pct (89.47)
        pct = pd.to_numeric(pct_raw, errors="coerce")
        # If max value <= 2.0, treat as decimal fraction and convert to percentage
        if pct.max(skipna=True) <= 2.0:
            pct = pct * 100
    df["Процент выполнения"] = pct.round(2)
    return df.dropna(subset=["Поток", "Занятие"])

# ─── ШТРАФЫ ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_fines(sheet_id: str) -> pd.DataFrame:
    """
    Load ШТРАФЫ sheet from an individual school spreadsheet.
    Drops rows with non-numeric Поток.
    """
    df = _read_xlsx_sheet(sheet_id, "ШТРАФЫ")
    df.columns = df.columns.str.strip()

    df = df[pd.to_numeric(df["Поток"], errors="coerce").notna()].copy()
    df["Поток"] = df["Поток"].astype(int)
    df["Сумма штрафа"] = pd.to_numeric(df["Сумма штрафа"], errors="coerce").fillna(0)
    df["Пункт правил"] = df["Пункт правил"].astype(str).str.strip()
    return df.dropna(subset=["Поток"])

# ─── Metrics ─────────────────────────────────────────────────────────────────

def school_metrics(minutka: pd.DataFrame, fines: pd.DataFrame, stream: int) -> dict:
    """
    Compute metrics for one school and one stream.

    Returns dict with keys:
      first_lesson_students (int)
      last_lesson_students  (int)
      dropout_pct           (float, e.g. 29.2)
      total_fines           (float)
      avg_minutka_pct       (float)
      fines_by_reason       (pd.Series: reason -> total amount, sorted desc)
      minutka_by_lesson     (pd.DataFrame: Занятие, Количество учеников в школе,
                                           Количество сданных форм, Процент выполнения)
    """
    m = minutka[minutka["Поток"] == stream].sort_values("Занятие")
    f = fines[fines["Поток"] == stream]

    if len(m) > 0:
        first = int(m.iloc[0]["Количество учеников в школе"])
        last  = int(m.iloc[-1]["Количество учеников в школе"])
        dropout_pct = round((first - last) / first * 100, 1) if first > 0 else 0.0
        avg_minutka = round(m["Процент выполнения"].mean(), 1)
    else:
        first = last = 0
        dropout_pct = avg_minutka = 0.0

    total_fines = float(f["Сумма штрафа"].sum())
    fines_by_reason = (
        f.groupby("Пункт правил")["Сумма штрафа"]
        .sum()
        .sort_values(ascending=False)
    )

    return {
        "first_lesson_students": first,
        "last_lesson_students":  last,
        "dropout_pct":           dropout_pct,
        "total_fines":           total_fines,
        "avg_minutka_pct":       avg_minutka,
        "fines_by_reason":       fines_by_reason,
        "minutka_by_lesson":     m[["Занятие", "Количество учеников в школе",
                                    "Количество сданных форм", "Процент выполнения"]].copy(),
    }

# ─── Summary across all schools ──────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_all_schools_summary(stream: int) -> pd.DataFrame:
    """
    Load metrics for ALL schools for a given stream.
    Returns DataFrame with columns:
      Школа, Кластер, Старт, Финиш, Отсев %, Штрафы ₽, Минутка %, sheet_id
    Skips schools with no data for the requested stream.
    """
    registry = load_registry()
    rows = []
    for _, school_row in registry.iterrows():
        sid = school_row["sheet_id"]
        if not sid:
            continue
        try:
            m = load_minutka(sid)
            f = load_fines(sid)
            if stream not in m["Поток"].values:
                continue
            metrics = school_metrics(m, f, stream)
            rows.append({
                "Школа":     school_row[COL_SCHOOL],
                "Кластер":   school_row[COL_CLUSTER],
                "Старт":     metrics["first_lesson_students"],
                "Финиш":     metrics["last_lesson_students"],
                "Отсев %":   metrics["dropout_pct"],
                "Штрафы ₽":  int(metrics["total_fines"]),
                "Минутка %": metrics["avg_minutka_pct"],
                "sheet_id":  sid,
            })
        except Exception:
            continue
    return pd.DataFrame(rows)
