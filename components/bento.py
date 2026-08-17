"""
Bento-блок для сводной страницы: шапка + ряд KPI со спарклайнами.

Рендерится через st.components.v1.html (отдельный iframe), а не через st.markdown,
потому что Streamlit вырезает <script> из markdown — а нам нужен JS для
анимации счётчиков. Всё самодостаточно: свои стили, свой JS, никаких внешних CDN.
"""
from html import escape


def sparkline_path(values: list[float], height: int = 22, pad: int = 3) -> str:
    """
    SVG path (`d`) для спарклайна по значениям.
    Нормализует по min/max ряда; при плоском ряде рисует линию посередине.
    Возвращает пустую строку, если точек меньше двух.
    """
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = hi - lo
    usable = height - pad * 2
    n = len(vals)
    pts = []
    for i, v in enumerate(vals):
        x = i / (n - 1) * 100
        y = (height / 2) if span == 0 else (height - pad - (v - lo) / span * usable)
        pts.append(f"{x:.1f},{y:.1f}")
    return "M" + " L".join(pts)


def _fmt_attrs(kpi: dict) -> str:
    """data-* атрибуты для JS-счётчика."""
    return (
        f'data-count="{kpi["num"]}" '
        f'data-dec="{kpi.get("dec", 0)}" '
        f'data-sep="{1 if kpi.get("sep") else 0}" '
        f'data-suf="{escape(kpi.get("suf", ""))}"'
    )


def format_value(kpi: dict) -> str:
    """
    Финальное значение KPI ровно в том виде, в каком его нарисует JS-счётчик.

    Пишется прямо в HTML, чтобы правильное число было на экране ещё до того,
    как отработает анимация. Если JS или requestAnimationFrame не сработают
    (фоновая вкладка, экономия энергии, старый браузер) — пользователь увидит
    настоящее число, а не ноль.
    """
    num = kpi["num"]
    suffix = kpi.get("suf", "")
    if kpi.get("sep"):
        body = f"{int(round(float(num))):,}".replace(",", " ")
    else:
        body = f"{float(num):.{kpi.get('dec', 0)}f}"
    return body + suffix


def _safe_link(url) -> str:
    """
    Возвращает URL, только если это обычная http(s)-ссылка.

    Ссылки приходят из Google-таблицы, которую редактируют руками, поэтому
    подставлять их в href как есть нельзя: значение вида `javascript:...`
    превратилось бы в исполняемый код на странице.
    """
    if not url:
        return ""
    clean = str(url).strip()
    return clean if clean.lower().startswith(("https://", "http://")) else ""


def _kpi_cell(kpi: dict) -> str:
    color = kpi.get("color", "#2563eb")
    spark = ""
    d = sparkline_path(kpi.get("series") or [])
    if d:
        spark = (
            f'<svg class="spk" viewBox="0 0 100 22" preserveAspectRatio="none" aria-hidden="true">'
            f'<path d="{d}"/></svg>'
        )
    icon = kpi.get("icon", "")
    icon_html = f'<div class="ic">{icon}</div>' if icon else ""
    return f"""
    <div class="cell k" style="--c:{color}">
      {icon_html}
      <div class="lab">{escape(str(kpi["label"]))}</div>
      <div class="val" {_fmt_attrs(kpi)}>{escape(format_value(kpi))}</div>
      {spark}
    </div>"""


def bento_header_html(
    title: str,
    subtitle: str,
    kpis: list[dict],
    avg_rating: float | None,
    rating_note: str,
    schools_note: str,
    trend_note: str,
    accent: str = "#2563eb",
    pill: dict | None = None,
    rating_label: str = "Средний рейтинг",
    leader: dict | None = None,
) -> str:
    """
    Полный HTML-документ для components.html: шапка (3 плитки) + ряд KPI.

    kpis — список словарей:
      label (str), num (float), dec (int), sep (bool), suf (str),
      color (str), icon (str), series (list[float] | None)
    accent — цвет акцента шапки (обычно цвет кластера).
    pill   — {"text": ..., "color": ...}: плашка рядом с заголовком.
    leader — {"name": ..., "url": ...}: строка «Руководитель» под подзаголовком.
    """
    pill_html = ""
    if pill and pill.get("text"):
        p_color = pill.get("color", accent)
        pill_html = (f'<span class="pill" style="background:{p_color}1a;color:{p_color}">'
                     f'{escape(str(pill["text"]))}</span>')

    leader_html = ""
    if leader and leader.get("name"):
        l_name = escape(str(leader["name"]))
        l_url = _safe_link(leader.get("url"))
        # Без валидной ссылки показываем просто имя — строка не пропадает
        l_body = (
            f'<a href="{escape(l_url)}" target="_blank" rel="noopener noreferrer">'
            f'{l_name}<span class="tg">↗</span></a>'
            if l_url else l_name
        )
        leader_html = f'<div class="hm-leader">Руководитель: {l_body}</div>'

    if avg_rating is not None:
        r_color = "#22c55e" if avg_rating >= 9 else "#f97316" if avg_rating >= 7 else "#ef4444"
        r_pct = max(0.0, min(100.0, avg_rating / 10 * 100))
        # окружность r=30 → 2πr ≈ 188.5
        dash = 188.5
        offset = dash * (1 - r_pct / 100)
        rating_cell = f"""
      <div class="cell head-rate" style="--c:{r_color}">
        <div class="lab">{escape(rating_label)}</div>
        <div class="hr-body">
          <div class="ring-wrap">
            <svg class="ring" viewBox="0 0 72 72" aria-hidden="true">
              <circle class="ring-bg" cx="36" cy="36" r="30"/>
              <circle class="ring-fg" cx="36" cy="36" r="30"
                      style="stroke:{r_color};stroke-dasharray:{dash};--off:{offset:.1f}"/>
            </svg>
            <div class="ring-num" style="color:{r_color}">{avg_rating:.2f}</div>
          </div>
          <div class="hr-txt">
            <div class="hr-verdict" style="color:{r_color}">
                {"Отлично" if avg_rating >= 9 else "Хорошо" if avg_rating >= 7 else "Требует внимания"}
            </div>
            <div class="hr-note">{escape(rating_note)}</div>
          </div>
        </div>
      </div>"""
    else:
        rating_cell = f"""
      <div class="cell head-rate" style="--c:#94a3b8">
        <div class="lab">{escape(rating_label)}</div>
        <div class="hr-empty">Пока нет отзывов</div>
      </div>"""

    kpi_cells = "".join(_kpi_cell(k) for k in kpis)

    return f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}
body{{margin:0;font-family:"Source Sans Pro","Segoe UI",-apple-system,sans-serif;background:transparent}}
.wrap{{display:flex;flex-direction:column;gap:12px}}
.bento{{display:grid;gap:12px}}

/* Базовое состояние — КОНЕЧНОЕ (карточка видна, полоска на месте), анимация
   проигрывается «из» пустого. Если анимации не отработают, страница выглядит
   правильно, а не пустой. */
.cell{{position:relative;background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:14px 16px;
  overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.06);
  animation:up .55s cubic-bezier(.16,1,.3,1) both;
  transition:transform .4s cubic-bezier(.16,1,.3,1),box-shadow .4s,border-color .4s}}
.cell::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--c,#2563eb);
  transform-origin:left;animation:barIn .7s cubic-bezier(.16,1,.3,1) .2s both}}
@keyframes up{{from{{opacity:0;transform:translateY(14px)}}}}
@keyframes barIn{{from{{transform:scaleX(0)}}}}
.cell:hover{{transform:translateY(-4px);border-color:var(--c);box-shadow:0 14px 34px rgba(15,23,42,.13)}}
.lab{{font-size:.6rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px}}

/* ── шапка ── */
.head{{grid-template-columns:1.7fr 1.3fr .9fr}}
.head-main{{display:flex;flex-direction:column;justify-content:center;gap:10px}}
.hm-top{{display:flex;align-items:center;gap:12px}}
.terra-ring{{width:32px;height:32px;border-radius:50%;border:2.5px solid var(--c);flex-shrink:0;
  animation:pulse 3.2s ease-in-out infinite}}
@keyframes pulse{{
  0%,100%{{box-shadow:0 0 0 0 color-mix(in srgb,var(--c) 35%,transparent)}}
  50%{{box-shadow:0 0 0 7px color-mix(in srgb,var(--c) 0%,transparent)}}}}
.hm-titleline{{display:flex;align-items:center;gap:9px;flex-wrap:wrap}}
.hm-title{{font-size:1.2rem;font-weight:700;color:#1e293b;line-height:1.15}}
.hm-sub{{font-size:.65rem;color:var(--c);letter-spacing:2px;text-transform:uppercase;margin-top:3px}}
.pill{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.62rem;font-weight:700;
  letter-spacing:.5px;white-space:nowrap}}
.hm-leader{{font-size:.72rem;color:#64748b;margin-top:7px}}
.hm-leader a{{color:var(--c);font-weight:600;text-decoration:none;
  border-bottom:1px solid transparent;transition:border-color .2s ease}}
.hm-leader a:hover{{border-bottom-color:var(--c)}}
.hm-leader .tg{{font-size:.62rem;margin-left:3px;opacity:.65}}

.head-rate .hr-body{{display:flex;align-items:center;gap:12px;margin-top:8px}}
.ring-wrap{{position:relative;width:64px;height:64px;flex-shrink:0}}
.ring{{display:block;width:64px;height:64px;transform:rotate(-90deg)}}
.ring-bg{{fill:none;stroke:#e2e8f0;stroke-width:7}}
.ring-fg{{fill:none;stroke-width:7;stroke-linecap:round;stroke-dashoffset:var(--off);
  animation:ringIn 1.2s cubic-bezier(.16,1,.3,1) .25s both}}
@keyframes ringIn{{from{{stroke-dashoffset:188.5}}}}
.ring-num{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:.95rem;font-weight:800;line-height:1;pointer-events:none}}
.hr-verdict{{font-size:.9rem;font-weight:700}}
.hr-note{{font-size:.62rem;color:#94a3b8;margin-top:4px;line-height:1.45}}
.hr-empty{{margin-top:14px;font-size:.8rem;color:#94a3b8}}

.head-meta{{display:flex;flex-direction:column;justify-content:center;gap:6px}}
.live{{display:flex;align-items:center;gap:7px;font-size:.78rem;font-weight:700;color:#334155}}
.live i{{width:8px;height:8px;border-radius:50%;background:#22c55e;flex-shrink:0;
  animation:blink 1.9s ease-in-out infinite}}
@keyframes blink{{0%,100%{{opacity:1;box-shadow:0 0 0 0 rgba(34,197,94,.5)}}
  50%{{opacity:.5;box-shadow:0 0 0 6px rgba(34,197,94,0)}}}}
.meta-note{{font-size:.62rem;color:#94a3b8;line-height:1.5}}

/* ── KPI ── */
.kpis{{grid-template-columns:repeat({max(1, len(kpis))},1fr)}}
.k{{padding:13px 12px}}
.k .ic{{font-size:1rem;margin-bottom:6px;transition:transform .35s cubic-bezier(.16,1,.3,1)}}
.k:hover .ic{{transform:scale(1.25) rotate(-8deg)}}
.k .val{{font-size:1.45rem;font-weight:800;color:var(--c);line-height:1;margin-top:6px;
  font-variant-numeric:tabular-nums}}
.spk{{display:block;width:100%;height:22px;margin-top:7px}}
.spk path{{fill:none;stroke:var(--c);stroke-width:2;stroke-linecap:round;stroke-linejoin:round;
  opacity:.4;stroke-dasharray:200;stroke-dashoffset:0;
  animation:draw 1.3s cubic-bezier(.16,1,.3,1) .4s both;transition:opacity .3s}}
@keyframes draw{{from{{stroke-dashoffset:200}}}}
.k:hover .spk path{{opacity:1}}

@media (max-width:900px){{
  .head{{grid-template-columns:1fr}}
  .kpis{{grid-template-columns:repeat(3,1fr)}}
}}
@media (prefers-reduced-motion:reduce){{
  *{{animation-duration:.01ms!important;transition-duration:.01ms!important}}
}}
</style></head><body>
<div class="wrap">
  <div class="bento head">
    <div class="cell head-main" style="--c:{accent}">
      <div class="hm-top">
        <div class="terra-ring"></div>
        <div>
          <div class="hm-titleline">
            <span class="hm-title">{escape(title)}</span>
            {pill_html}
          </div>
          <div class="hm-sub">{escape(subtitle)}</div>
          {leader_html}
        </div>
      </div>
    </div>
    {rating_cell}
    <div class="cell head-meta" style="--c:#8b5cf6">
      <div class="lab">Данные</div>
      <div class="live"><i></i>{escape(schools_note)}</div>
      <div class="meta-note">{escape(trend_note)}</div>
    </div>
  </div>
  <div class="bento kpis">{kpi_cells}</div>
</div>
<script>
(function(){{
  var NBSP=String.fromCharCode(160);   // тот же разделитель, что и в format_value()
  function sep(n){{return String(n).replace(/\B(?=(\d{{3}})+(?!\d))/g,NBSP);}}
  function ease(t){{return 1-Math.pow(1-t,3);}}
  var reduce=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll("[data-count]").forEach(function(el,i){{
    var target=parseFloat(el.dataset.count)||0,
        dec=parseInt(el.dataset.dec||"0",10),
        useSep=el.dataset.sep==="1",
        suf=el.dataset.suf||"";
    function paint(v){{
      el.textContent=(useSep?sep(Math.round(v)):v.toFixed(dec))+suf;
    }}
    if(reduce){{paint(target);return;}}
    var start=null;
    setTimeout(function(){{
      requestAnimationFrame(function step(ts){{
        if(!start)start=ts;
        var p=Math.min(1,(ts-start)/900);
        paint(target*ease(p));
        if(p<1)requestAnimationFrame(step);
      }});
    }},150+i*70);
  }});
}})();
</script></body></html>"""
