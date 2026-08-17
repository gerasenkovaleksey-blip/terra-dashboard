import re
import io
import logging
import urllib.parse

import requests
import streamlit as st
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

REGISTRY_ID = "1K4OZ6wMkJFgW3gAvW4m4YJpwzFaPICB8hZIeKRVt5DU"

COL_SCHOOL  = "Название школы"
COL_CLUSTER = "Кластер"
COL_URL     = "Ссылка на таблицу с подробным описанием школы"
COL_LEADER  = "Полное ФИО"
COL_TG      = "Ссылка на профиль"

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
    "Стретегия": "Стратегия",
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
    if resp.status_code == 410:
        raise ValueError(f"Таблица удалена навсегда (410 Gone). sheet_id={spreadsheet_id}")
    resp.raise_for_status()
    return resp.content


def _parse_sheet(spreadsheet_id: str, sheet_name: str) -> pd.DataFrame:
    """
    Parse a named sheet from the cached XLSX bytes.
    If the first row contains only Unnamed columns, scans up to 5 rows
    to find the real header row.
    Always normalizes column names to strings.
    """
    xl = pd.ExcelFile(io.BytesIO(_load_workbook(spreadsheet_id)))
    df = xl.parse(sheet_name)
    # Если все колонки — Unnamed, ищем строку-заголовок в первых 5 строках
    if all(str(c).startswith("Unnamed:") for c in df.columns):
        for i in range(min(5, len(df))):
            candidate = [str(v).strip() for v in df.iloc[i].tolist()]
            if not all(v.startswith("Unnamed:") or v in ("nan", "") for v in candidate):
                df.columns = candidate
                df = df.iloc[i + 1:].reset_index(drop=True)
                break
    # Всегда приводим имена колонок к строкам (защита от float/int имён из XLSX)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _extract_sheet_id(url: str) -> str | None:
    """Extract spreadsheet ID from a Google Sheets URL."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", str(url))
    return match.group(1) if match else None

# ─── Registry ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_registry() -> pd.DataFrame:
    """
    Load the school registry.
    Returns DataFrame with columns: Школа, Кластер, Руководитель, Телеграм, sheet_id.
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
    # Руководитель школы и ссылка на его телеграм.
    # В таблице встречаются лишние пробелы по краям — чистим сразу.
    for src, dst in ((COL_LEADER, "Руководитель"), (COL_TG, "Телеграм")):
        if src in df.columns:
            df[dst] = df[src].apply(lambda v: str(v).strip() if pd.notna(v) else "")
        else:
            logger.warning("Колонка «%s» не найдена в реестре", src)
            df[dst] = ""

    result = df[[COL_SCHOOL, COL_CLUSTER, COL_URL,
                 "Руководитель", "Телеграм", "sheet_id"]].reset_index(drop=True)
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
    "Количество учеников на занятии",
    "Кол-во учеников в школе",
    "Кол-во учеников на занятии",
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
    cols_lower = {str(c).lower(): c for c in df.columns}
    for alias in aliases:
        if alias in df.columns:
            return alias
        if alias.lower() in cols_lower:
            return cols_lower[alias.lower()]
    # Not found — create empty column so downstream dropna handles it gracefully
    logger.warning("Колонка не найдена (искали: %s). Доступные: %s", aliases[0], list(df.columns))
    df[fallback] = float("nan")
    return fallback


def _to_numeric_clean(series: pd.Series) -> pd.Series:
    """
    Convert a series to numeric, handling mixed cell types gracefully.
    Strips non-numeric characters (e.g. "20 чел." → 20, "15 чел" → 15).
    For pure numeric series, uses pd.to_numeric directly without string conversion.
    """
    if series.dtype == object:
        cleaned = (
            series.astype(str)
            .str.strip()
            .str.replace(r"[^\d.,]", "", regex=True)   # keep digits, dot, comma
            .str.replace(",", ".", regex=False)          # "20,5" → "20.5"
            .str.replace(r"\.(?=.*\.)", "", regex=True)  # remove extra dots if any
        )
        return pd.to_numeric(cleaned, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


@st.cache_data(ttl=3600)
def load_minutka(sheet_id: str) -> pd.DataFrame:
    """
    Load МИНУТКА_ДАРОВАНИЯ sheet from an individual school spreadsheet.
    Drops rows with non-numeric Занятие or missing student count.
    Normalizes Процент выполнения to percentage float (e.g. 89.47).
    Handles both string "89,47%" format and decimal fraction 0.8947 from XLSX.
    Tolerates alternative column names via _find_col().
    """
    df = _parse_sheet(sheet_id, "МИНУТКА_ДАРОВАНИЯ")  # columns already stripped

    lesson_col = _find_col(df, _LESSON_COL_ALIASES, "Занятие")
    stream_col = _find_col(df, _STREAM_COL_ALIASES, "Поток")

    df = df[pd.to_numeric(df[lesson_col], errors="coerce").notna()].copy()
    df["Занятие"] = df[lesson_col].astype(int)
    df["Поток"]   = pd.to_numeric(df[stream_col], errors="coerce")

    students_col = _find_col(df, _STUDENTS_COL_ALIASES, "Количество учеников в школе")
    df["Количество учеников в школе"] = _to_numeric_clean(df[students_col])

    forms_col = _find_col(df, _FORMS_COL_ALIASES, "Количество сданных форм")
    df["Количество сданных форм"] = _to_numeric_clean(df[forms_col])

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
    # Normalize decimal fractions to percentages.
    # Case 1: all values <= 1.0 — pure decimal format, multiply everything by 100.
    # Case 2: mixed format (some <= 1.0, some > 1.0) — XLSX stored some cells as
    #         numeric fraction (1.0 = 100%) and others as string "100%". Multiply
    #         only the fraction values by 100 to unify the column.
    pct_max = pct.max(skipna=True)
    has_fractions = ((pct > 0) & (pct <= 1.0)).any()
    if pct_max <= 1.0:
        pct = pct * 100
    elif has_fractions:
        pct = pct.apply(lambda x: x * 100 if pd.notna(x) and 0 < x <= 1.0 else x)
    df["Процент выполнения"] = pct.round(2)
    return df.dropna(subset=["Поток", "Занятие", "Количество учеников в школе"])

# ─── ШТРАФЫ ──────────────────────────────────────────────────────────────────

_FINE_AMOUNT_ALIASES = [
    "Сумма штрафа",
    "Сумма",
    "Штраф",
    "Размер штрафа",
    "Сумма (руб)",
    "Сумма (₽)",
    "Сумма руб",
]
_FINE_REASON_ALIASES = [
    "Причина штрафа",
    "Пункт правил",
    "Причина",
    "За что",
    "Нарушение",
    "Описание",
]
_FINE_REPAYMENT_ALIASES = [
    "Сумма погашения",
    "Погашено",
    "Погашение",
    "Оплачено",
    "Сумма оплаты",
]

# ─── Нормализация причин штрафов ─────────────────────────────────────────────
# Порядок важен: первое совпадение ключевого слова (без регистра) выигрывает.
# Добавляй новые ключевые слова в нужную группу по мере появления в данных.
FINE_REASON_GROUPS: list[tuple[list[str], str]] = [
    (["дз", "домашк", "не сдал", "не сдала", "задани"],  "ДЗ"),
    (["контролер", "контролёр"],                          "Контролер"),
    (["отчет", "отчёт"],                                  "Отчёт"),
    (["опоздани", "опездани"],                            "Опоздание на занятие"),
    (["телефон", "гаджет", "трекшен", "сигнал"],          "Телефон"),
    (["бадди"],                                           "За бадди"),
]

def _normalize_fine_reason(reason) -> str:
    """Map a raw fine reason string to a normalized group name."""
    if not isinstance(reason, str):
        reason = "" if (reason is None or (isinstance(reason, float) and reason != reason)) else str(reason)
    r = reason.lower().strip()
    for keywords, group in FINE_REASON_GROUPS:
        if any(kw in r for kw in keywords):
            return group
    return reason  # не попало ни в одну группу — оставляем как есть


@st.cache_data(ttl=3600)
def load_fines(sheet_id: str) -> pd.DataFrame:
    """
    Load ШТРАФЫ sheet from an individual school spreadsheet.
    Drops rows with non-numeric Поток.
    """
    df = _parse_sheet(sheet_id, "ШТРАФЫ")  # columns already stripped

    stream_col = _find_col(df, _STREAM_COL_ALIASES, "Поток")
    df = df[pd.to_numeric(df[stream_col], errors="coerce").notna()].copy()
    df["Поток"] = df[stream_col].astype(int)

    amount_col = _find_col(df, _FINE_AMOUNT_ALIASES, "Сумма штрафа")
    df["Сумма штрафа"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)

    repayment_col = _find_col(df, _FINE_REPAYMENT_ALIASES, "Сумма погашения")
    df["Сумма погашения"] = pd.to_numeric(df[repayment_col], errors="coerce").fillna(0)

    reason_col = _find_col(df, _FINE_REASON_ALIASES, "Причина штрафа")
    df["Причина штрафа"] = df[reason_col].apply(_normalize_fine_reason)
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

    total_fines      = float(f["Сумма штрафа"].sum())
    total_fines_paid = float(f["Сумма погашения"].sum()) if "Сумма погашения" in f.columns else 0.0
    _fbr_col = "Сумма погашения" if "Сумма погашения" in f.columns else "Сумма штрафа"
    fines_by_reason = (
        f.groupby("Причина штрафа")[_fbr_col]
        .sum()
        .sort_values(ascending=False)
    )

    return {
        "first_lesson_students": first,
        "last_lesson_students":  last,
        "dropout_pct":           dropout_pct,
        "total_fines":           total_fines,
        "total_fines_paid":      total_fines_paid,
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
      Школа, Кластер, Старт, Финиш, Отсев %, Штрафы ₽, Штрафов назначено ₽,
      На 1 ученика (старт), На 1 ученика (финиш), Минутка %, sheet_id
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
            start    = metrics["first_lesson_students"]
            finish   = metrics["last_lesson_students"]
            assigned = int(metrics["total_fines"])
            paid     = int(metrics["total_fines_paid"])
            per_start  = int(round(assigned / start))  if start  > 0 else 0
            per_finish = int(round(assigned / finish)) if finish > 0 else 0
            rows.append({
                "Школа":                  school_row["Школа"],
                "Кластер":                school_row[COL_CLUSTER],
                "Старт":                  start,
                "Финиш":                  finish,
                "Отсев %":                metrics["dropout_pct"],
                "Штрафы ₽":               paid,
                "Штрафов назначено ₽":    assigned,
                "На 1 ученика (старт)":   per_start,
                "На 1 ученика (финиш)":   per_finish,
                "Минутка %":              metrics["avg_minutka_pct"],
                "sheet_id":               sid,
            })
        except Exception as e:
            logger.warning("Ошибка загрузки школы %s (sheet_id=%s): %s",
                           school_row.get("Школа", "?"), sid, e)
            continue
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600)
def load_streams_history(streams: tuple[int, ...]) -> pd.DataFrame:
    """
    Сводка по нескольким потокам сразу — источник данных для спарклайнов (трендов).

    Переиспользует load_all_schools_summary() для каждого потока: XLSX-файлы школ
    уже лежат в кэше _load_workbook(), поэтому дополнительной сетевой нагрузки нет —
    только пересчёт метрик.

    Школы, которых в прошлых потоках не было, просто отсутствуют в строках за те
    потоки — вызывающий код дополняет их нулями (новая школа = отсчёт от нуля).

    Returns: те же колонки, что load_all_schools_summary(), плюс "Поток".
    Пустой DataFrame, если данных нет вообще.
    """
    frames = []
    for s in streams:
        df = load_all_schools_summary(int(s))
        if len(df) == 0:
            continue
        df = df.copy()
        df["Поток"] = int(s)
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["Школа", "Кластер", "Поток"])
    return pd.concat(frames, ignore_index=True)


@st.cache_data(ttl=3600)
def load_all_fines_detail(stream: int) -> pd.DataFrame:
    """
    Load raw fines for ALL schools for a given stream.
    Returns DataFrame with columns: Школа, Кластер, Причина штрафа, Сумма штрафа.
    Used for aggregated fines-by-reason breakdown in the summary dashboard.
    """
    registry = load_registry()
    rows = []
    for _, school_row in registry.iterrows():
        sid = school_row["sheet_id"]
        if not sid:
            continue
        try:
            f = load_fines(sid)
            f_stream = f[f["Поток"] == stream]
            if len(f_stream) == 0:
                continue
            for _, fine_row in f_stream.iterrows():
                rows.append({
                    "Школа":           school_row["Школа"],
                    "Кластер":         school_row[COL_CLUSTER],
                    "Причина штрафа":  fine_row["Причина штрафа"],
                    "Сумма погашения": fine_row.get("Сумма погашения", 0),
                })
        except Exception as e:
            logger.warning("Ошибка штрафов школы %s (sheet_id=%s): %s",
                           school_row.get("Школа", "?"), sid, e)
            continue
    return pd.DataFrame(rows, columns=["Школа", "Кластер", "Причина штрафа", "Сумма погашения"])

# ─── Рейтинг школ (NPS / удовлетворённость) ──────────────────────────────────

NPS_SPREADSHEET_ID = "1VnCUPhFxhI5MbWzRMBsGy5XLkwQhOglpY2D3_TlII7s"
NPS_RATING_SHEET   = "Рейтинг школ по нпс"
NPS_ANSWERS_SHEET  = "Ответы на форму (1)"


@st.cache_data(ttl=3600)
def load_school_ratings() -> pd.DataFrame:
    """
    Load average satisfaction rating (0-10) per school from the общий feedback-таблица.
    Ratings come from a Google Sheets pivot table that only exports correctly via the
    gviz CSV endpoint (regular XLSX export drops computed pivot values for this sheet).
    Response counts come from the raw form-answers sheet via the normal XLSX parser.
    Returns DataFrame with columns: Школа, Рейтинг (float), Отзывов (int).
    """
    encoded = urllib.parse.quote(NPS_RATING_SHEET)
    url = (
        f"https://docs.google.com/spreadsheets/d/{NPS_SPREADSHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={encoded}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    ratings = pd.read_csv(io.StringIO(resp.content.decode("utf-8")))
    ratings.columns = ["Школа", "Рейтинг"]
    ratings = ratings[ratings["Школа"] != "Итого"].copy()
    ratings["Рейтинг"] = pd.to_numeric(
        ratings["Рейтинг"].astype(str).str.replace(",", ".", regex=False), errors="coerce"
    )
    ratings = ratings.dropna(subset=["Рейтинг"])

    answers = _parse_sheet(NPS_SPREADSHEET_ID, NPS_ANSWERS_SHEET)
    school_col = _find_col(answers, ["По какой школе оставляешь обратную связь?"], "Школа")
    counts = (
        answers[school_col].value_counts()
        .rename_axis("Школа")
        .reset_index(name="Отзывов")
    )

    result = ratings.merge(counts, on="Школа", how="left")
    result["Отзывов"] = result["Отзывов"].fillna(0).astype(int)
    return result


@st.cache_data(ttl=3600)
def load_nps_answers() -> pd.DataFrame:
    """
    Сырые ответы формы НПС: школа + дата заполнения.
    Returns DataFrame с колонками: Школа, Дата (datetime.date).
    """
    df = _parse_sheet(NPS_SPREADSHEET_ID, NPS_ANSWERS_SHEET)
    school_col = _find_col(df, ["По какой школе оставляешь обратную связь?"], "Школа")
    time_col = _find_col(df, ["Отметка времени", "Timestamp"], "Отметка времени")
    parsed = pd.to_datetime(df[time_col], errors="coerce")
    out = pd.DataFrame({
        "Школа": df[school_col].astype(str).str.strip(),
        "Дата": parsed.map(lambda x: x.date() if pd.notna(x) else None),
    })
    return out[out["Дата"].notna() & (out["Школа"] != "nan")].reset_index(drop=True)


@st.cache_data(ttl=3600)
def load_lessons(sheet_id: str) -> pd.DataFrame:
    """
    Занятия школы с датами — без отбрасывания незаполненных строк.

    Отличие от load_minutka(): та выкидывает строки без количества учеников,
    а для контроля заполнения именно они и нужны — это занятия, по которым
    отчётность не внесли.

    Returns DataFrame: Поток, Занятие, Дата, Учеников, Записано_форм.
    """
    df = _parse_sheet(sheet_id, "МИНУТКА_ДАРОВАНИЯ")
    if len(df) == 0 or "Дата" not in df.columns:
        return pd.DataFrame(columns=["Поток", "Занятие", "Дата", "Учеников", "Записано_форм"])

    raw = df["Дата"]
    if isinstance(raw, pd.DataFrame):      # в отдельных таблицах колонка задвоена
        raw = raw.iloc[:, 0]
    parsed = pd.to_datetime(raw, errors="coerce")

    lesson_col   = _find_col(df, _LESSON_COL_ALIASES, "Занятие")
    stream_col   = _find_col(df, _STREAM_COL_ALIASES, "Поток")
    students_col = _find_col(df, _STUDENTS_COL_ALIASES, "Количество учеников в школе")
    forms_col    = _find_col(df, _FORMS_COL_ALIASES, "Количество сданных форм")

    out = pd.DataFrame({
        "Поток":         pd.to_numeric(df[stream_col], errors="coerce"),
        "Занятие":       pd.to_numeric(df[lesson_col], errors="coerce"),
        # .map, а не .dt.date: dtype колонки различается от таблицы к таблице
        "Дата":          parsed.map(lambda x: x.date() if pd.notna(x) else None),
        "Учеников":      _to_numeric_clean(df[students_col]),
        "Записано_форм": _to_numeric_clean(df[forms_col]),
    })
    return out[out["Дата"].notna()].reset_index(drop=True)


# Сколько дней после занятия форма ещё считается сданной вовремя.
# Регламент: в день занятия или на следующий.
NPS_WINDOW_DAYS = 1
# Насколько дата занятия может «съехать», чтобы заподозрить опечатку, а не незаполнение
DATE_SUSPECT_DAYS = 3


@st.cache_data(ttl=3600)
def build_control_report() -> dict:
    """
    Сверяет записанное количество сданных форм с фактическим числом ответов НПС.

    Ответ засчитывается занятию, если пришёл в день занятия или на следующий —
    это регламент, а не эвристика.

    Returns dict:
      lessons   — DataFrame по занятиям со статусом расхождения
      no_dates  — школы, у которых в минутке нет дат, но НПС идёт
      late      — ответы, не попавшие в окно ни одного занятия
      period    — (первая дата НПС, последняя дата НПС)
    """
    import datetime as _dt

    answers = load_nps_answers()
    if len(answers) == 0:
        return {"lessons": pd.DataFrame(), "no_dates": pd.DataFrame(),
                "late": pd.DataFrame(), "period": (None, None)}

    lo, hi = answers["Дата"].min(), answers["Дата"].max()
    registry = load_registry()

    lesson_rows, no_dates_rows, late_rows = [], [], []

    for _, school in registry.iterrows():
        name = str(school["Школа"]).strip()
        sid = school["sheet_id"]
        sub = answers[answers["Школа"] == name]

        # pd.notna: у школ без ссылки sheet_id приходит как NaN, а NaN истинный —
        # простая проверка `if sid` пропустила бы его и дала запрос к .../d/nan/
        has_sheet = pd.notna(sid) and str(sid).strip() not in ("", "nan", "None")
        try:
            lessons = load_lessons(sid) if has_sheet else pd.DataFrame()
        except Exception as e:
            logger.warning("Контроль: не удалось прочитать занятия школы %s: %s", name, e)
            lessons = pd.DataFrame()

        in_period = lessons[lessons["Дата"].map(lambda d: lo <= d <= hi)] if len(lessons) else lessons

        if len(in_period) == 0:
            if len(sub):
                by_day = sorted(sub["Дата"].value_counts().items())
                no_dates_rows.append({
                    "Школа": name,
                    "Кластер": school.get("Кластер"),
                    "Ответов": len(sub),
                    "Дни по НПС": " · ".join(f"{d:%d.%m} ({c})" for d, c in by_day if c >= 3),
                })
            continue

        covered = set()
        for _, lr in in_period.sort_values("Дата").iterrows():
            start = lr["Дата"]
            window = [start + _dt.timedelta(days=k) for k in range(NPS_WINDOW_DAYS + 1)]
            covered.update(window)
            fact = int(sub["Дата"].isin(window).sum())
            written = lr["Записано_форм"]
            has_written = pd.notna(written)

            if not has_written:
                if fact == 0:
                    continue                      # занятие ещё не прошло — не про что отчитываться
                status = "Форм нет"
                diff = None
            else:
                written = int(written)
                diff = fact - written
                if diff == 0:
                    status = "Совпало"
                elif diff > 0:
                    status = "Кураторы / открытый"
                elif fact == 0 and _has_nearby_answers(sub, start):
                    # Ответы есть, но рядом с указанной датой, а не в ней.
                    # Это похоже на опечатку в дате, а не на то, что школа не собрала формы —
                    # обвинять её в незаполнении было бы несправедливо.
                    status = "Проверить дату"
                else:
                    status = "Не заполнили"

            lesson_rows.append({
                "Школа": name,
                "Кластер": school.get("Кластер"),
                "Поток": lr["Поток"],
                "Занятие": lr["Занятие"],
                "Дата": start,
                "Учеников": lr["Учеников"],
                "Записано": int(written) if has_written else None,
                "Факт": fact,
                "Разница": diff,
                "Статус": status,
            })

        late = sub[~sub["Дата"].isin(covered)]
        if len(late):
            by_day = sorted(late["Дата"].value_counts().items())
            peak_day, peak_n = max(by_day, key=lambda x: x[1])
            late_rows.append({
                "Школа": name,
                "Ответов": len(late),
                "Дни": " · ".join(f"{d:%d.%m} ({c})" for d, c in by_day),
                # Крупное скопление в один день — это, скорее всего, занятие,
                # которого просто нет в таблице, а не толпа опоздавших
                "Похоже на занятие": f"{peak_day:%d.%m}" if peak_n >= 5 else "",
            })

    return {
        "lessons": pd.DataFrame(lesson_rows),
        "no_dates": pd.DataFrame(no_dates_rows),
        "late": pd.DataFrame(late_rows),
        "period": (lo, hi),
    }


def _has_nearby_answers(school_answers: pd.DataFrame, lesson_date) -> bool:
    """Есть ли ответы в пределах DATE_SUSPECT_DAYS от даты занятия."""
    import datetime as _dt
    lo = lesson_date - _dt.timedelta(days=DATE_SUSPECT_DAYS)
    hi = lesson_date + _dt.timedelta(days=DATE_SUSPECT_DAYS)
    return bool(school_answers["Дата"].map(lambda d: lo <= d <= hi).any())


def get_school_rating(ratings: pd.DataFrame, school_name: str) -> dict | None:
    """Return {"score": float, "count": int} for a school, or None if no data."""
    row = ratings[ratings["Школа"] == school_name]
    if len(row) == 0:
        return None
    return {
        "score": float(row.iloc[0]["Рейтинг"]),
        "count": int(row.iloc[0]["Отзывов"]),
    }
