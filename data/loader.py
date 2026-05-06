import re
import io
import logging

import requests
import streamlit as st
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

REGISTRY_ID = "1K4OZ6wMkJFgW3gAvW4m4YJpwzFaPICB8hZIeKRVt5DU"

COL_SCHOOL  = "Название школы"
COL_CLUSTER = "Кластер"
COL_URL     = "Ссылка на таблицу с подробным описанием школы"

# ─── Переопределения sheet_id ─────────────────────────────────────────────────
# Если ссылка на таблицу школы изменилась, указываем новый sheet_id здесь.
# Имя школы → новый sheet_id (приоритет над реестром).
SCHOOL_SHEET_OVERRIDES: dict[str, str] = {
    "Роста дохода на своих услугах":  "1ifJTmS0gBm4viTCGHHmIcnR5bciNN_hXcx01Kryp7_o",
    "Торги по банкротству":           "1LAsbORfHfNjWvSJuztufvWB3DgXA2Cx6tK454XInmcU",
    "В2В бизнеса через логистику":    "1qxSGwWw5MBoCdxqeqOPPgpiQ4ykTN5M9IVHgOr_tk3w",
    "Автоматизации и ИИ":             "1yaRtL8enVIbFOV3hy4hybAsJZLBOm4w_0OUe0dKcMKA",
    "Школа эффективного продвижения": "1sp09DkQNRQk5_mcy4xLiDCB1fNjXto_iFXh7URYhYOE",
}

# ─── Исправления опечаток в названиях кластеров ───────────────────────────────
# Если в реестре встречаются опечатки в названии кластера — указываем исправление здесь.
# Опечатка (после strip) → правильное название.
CLUSTER_NAME_FIXES: dict[str, str] = {
    # Пример: "Стретегия": "Стратегия",
}

# ─── Utilities ───────────────────────────────────────────────────────────────

def _read_csv_utf8(url: str) -> pd.DataFrame:
    """Fetch a CSV URL and parse it as UTF-8 (Google Sheets returns UTF-8)."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return pd.read_csv(io.StringIO(resp.content.decode("utf-8")))


@st.cache_data(ttl=3600)
def _load_workbook(spreadsheet_id: str) -> bytes:
    """Download XLSX once per school and cache the raw bytes."""
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=xlsx"
    resp = requests.get(url, timeout=30)
    if not resp.ok:
        logger.error("HTTP %s при загрузке sheet_id=%s — %s", resp.status_code, spreadsheet_id, url)
    resp.raise_for_status()
    return resp.content


def _parse_sheet(spreadsheet_id: str, sheet_name: str) -> pd.DataFrame:
    """Parse a named sheet from the cached XLSX bytes."""
    xl = pd.ExcelFile(io.BytesIO(_load_workbook(spreadsheet_id)))
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
    Returns DataFrame with columns: Школа, Кластер, sheet_id.
    Drops rows with empty school name.
    """
    url = f"https://docs.google.com/spreadsheets/d/{REGISTRY_ID}/export?format=csv&gid=0"
    df = _read_csv_utf8(url)
    df = df[df[COL_SCHOOL].notna() & (df[COL_SCHOOL].str.strip() != "")].copy()
    # Нормализуем пробелы в названиях школ и кластеров
    df[COL_SCHOOL]   = df[COL_SCHOOL].str.strip()
    df[COL_CLUSTER]  = df[COL_CLUSTER].str.strip()
    # Применяем исправления опечаток в кластерах
    df[COL_CLUSTER]  = df[COL_CLUSTER].map(
        lambda x: CLUSTER_NAME_FIXES.get(x, x) if pd.notna(x) else x
    )
    df["sheet_id"] = df[COL_URL].apply(
        lambda x: _extract_sheet_id(x) if pd.notna(x) else None
    )
    # Применяем переопределения sheet_id (приоритет над реестром)
    df["sheet_id"] = df.apply(
        lambda row: SCHOOL_SHEET_OVERRIDES.get(str(row[COL_SCHOOL]).strip(), row["sheet_id"]),
        axis=1,
    )
    result = df[[COL_SCHOOL, COL_CLUSTER, COL_URL, "sheet_id"]].reset_index(drop=True)
    return result.rename(columns={COL_SCHOOL: "Школа"})

# ─── МИНУТКА_ДАРОВАНИЯ ───────────────────────────────────────────────────────

# Известные варианты названий колонок в МИНУТКА_ДАРОВАНИЯ
_LESSON_COL_ALIASES = [
    "Занятие",
    "Занятия",
    "№ занятия",
    "№занятия",
    "Урок",
    "№",
    "Номер занятия",
    "Номер",
]
_STREAM_COL_ALIASES = [
    "Поток",
    "Потоки",
    "№ потока",
    "Номер потока",
]
_STUDENTS_COL_ALIASES = [
    "Количество учеников в школе",
    "Кол-во учеников в школе",
    "Кол-во учеников",
    "Количество учеников",
    "Ученики в школе",
    "Ученики",
]
_FORMS_COL_ALIASES = [
    "Количество сданных форм",
    "Кол-во сданных форм",
    "Сданных форм",
    "Форм сдано",
]
_PCT_COL_ALIASES = [
    "Процент выполнения",
    "% выполнения",
    "Выполнение %",
    "Выполнение",
]


def _find_col(df: pd.DataFrame, aliases: list[str], fallback: str) -> str:
    """Return the first alias found in df.columns, or fallback (creating NaN column)."""
    cols_lower = {c.lower(): c for c in df.columns}
    for alias in aliases:
        if alias in df.columns:
            return alias
        if alias.lower() in cols_lower:
            return cols_lower[alias.lower()]
    # Not found — create empty column so downstream dropna handles it gracefully
    logger.warning("Колонка не найдена (искали: %s). Доступные: %s", aliases[0], list(df.columns))
    df[fallback] = float("nan")
    return fallback


@st.cache_data(ttl=3600)
def load_minutka(sheet_id: str) -> pd.DataFrame:
    """
    Load МИНУТКА_ДАРОВАНИЯ sheet from an individual school spreadsheet.
    Drops rows with non-numeric Занятие or missing student count.
    Normalizes Процент выполнения to percentage float (e.g. 89.47).
    Handles both string "89,47%" format and decimal fraction 0.8947 from XLSX.
    Tolerates alternative column names via _find_col().
    """
    df = _parse_sheet(sheet_id, "МИНУТКА_ДАРОВАНИЯ")
    df.columns = df.columns.str.strip()

    lesson_col = _find_col(df, _LESSON_COL_ALIASES, "Занятие")
    stream_col = _find_col(df, _STREAM_COL_ALIASES, "Поток")

    df = df[pd.to_numeric(df[lesson_col], errors="coerce").notna()].copy()
    df["Занятие"] = df[lesson_col].astype(int)
    df["Поток"]   = pd.to_numeric(df[stream_col], errors="coerce")

    students_col = _find_col(df, _STUDENTS_COL_ALIASES, "Количество учеников в школе")
    df["Количество учеников в школе"] = pd.to_numeric(df[students_col], errors="coerce")

    forms_col = _find_col(df, _FORMS_COL_ALIASES, "Количество сданных форм")
    df["Количество сданных форм"] = pd.to_numeric(df[forms_col], errors="coerce")

    pct_col = _find_col(df, _PCT_COL_ALIASES, "Процент выполнения")
    # Handle both "89,47%" string format and 0.8947 decimal fraction from XLSX
    pct_raw = df[pct_col]
    if pct_raw.dtype == object:
        pct = (
            pct_raw.astype(str)
            .str.replace("%", "", regex=False)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
        )
    else:
        pct = pd.to_numeric(pct_raw, errors="coerce")
        # If all values are <= 1.0, treat as decimal fraction and convert to percentage
        if pct.max(skipna=True) <= 1.0:
            pct = pct * 100
    df["Процент выполнения"] = pct.round(2)
    return df.dropna(subset=["Поток", "Занятие", "Количество учеников в школе"])

# ─── ШТРАФЫ ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_fines(sheet_id: str) -> pd.DataFrame:
    """
    Load ШТРАФЫ sheet from an individual school spreadsheet.
    Drops rows with non-numeric Поток.
    """
    df = _parse_sheet(sheet_id, "ШТРАФЫ")
    df.columns = df.columns.str.strip()

    stream_col = _find_col(df, _STREAM_COL_ALIASES, "Поток")
    df = df[pd.to_numeric(df[stream_col], errors="coerce").notna()].copy()
    df["Поток"] = df[stream_col].astype(int)
    df["Сумма штрафа"] = pd.to_numeric(df["Сумма штрафа"], errors="coerce").fillna(0)
    reason_col = "Причина штрафа" if "Причина штрафа" in df.columns else "Пункт правил"
    df["Причина штрафа"] = df[reason_col].astype(str).str.strip()
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
        f.groupby("Причина штрафа")["Сумма штрафа"]
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
                "Школа":     school_row["Школа"],
                "Кластер":   school_row[COL_CLUSTER],
                "Старт":     metrics["first_lesson_students"],
                "Финиш":     metrics["last_lesson_students"],
                "Отсев %":   metrics["dropout_pct"],
                "Штрафы ₽":  int(metrics["total_fines"]),
                "Минутка %": metrics["avg_minutka_pct"],
                "sheet_id":  sid,
            })
        except Exception as e:
            logger.warning("Ошибка загрузки школы %s (sheet_id=%s): %s",
                           school_row.get("Школа", "?"), sid, e)
            continue
    return pd.DataFrame(rows)
