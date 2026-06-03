"""
OBSERVATION MODE — Weekly Report
Gera relatório semanal de crescimento, freshness, concentração, resiliência,
source health e price coverage. Sem desenvolvimento. Apenas medição.

Uso: python observation_report.py
"""
import sys
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from database.session import SessionLocal
from sqlalchemy import text

# ── Configuração ──────────────────────────────────────────────────────────────
BASELINE = {
    "jobs": {"top_source": "greenhouse", "top_share": 48.2, "hhi": 3793},
    "real_estate": {"top_source": "apolar", "top_share": 67.2, "hhi": 5159},
}
ALERT_THRESHOLDS = {
    "jobs_top_share": 60.0,
    "jobs_hhi": 5000,
    "re_top_share": 75.0,
    "re_hhi": 6000,
}
RE_URL_MAP = {
    "apolar":             "%apolar%",
    "razao":              "%irazao%",
    "gonzaga":            "%gonzagaimoveis%",
    "imobiliariapacheco": "%imobiliariapacheco%",
    "imobiliariamaringa": "%imobiliariamaringa%",
    "cadena":             "%cadenaimoveis%",
    "prates":             "%casaprates%",
    "cibraco":            "%cibraco%",
    "noruega":            "%imobiliarianoruega%",
}
JOB_SOURCES = ["greenhouse", "gupy", "lever", "smartrecruiters", "recruitee", "teamtailor"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def sep(char="-", n=64):
    return char * n

def hhi(counts):
    total = sum(counts)
    if not total:
        return 0
    return sum((c / total) ** 2 for c in counts) * 10_000

def delta_tag(current, baseline, lower_is_better=True):
    diff = current - baseline
    if abs(diff) < baseline * 0.02:
        return "ESTAVEL"
    if lower_is_better:
        return "MELHOROU" if diff < 0 else "PIOROU"
    return "MELHOROU" if diff > 0 else "PIOROU"


def run_report():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    d1 = now - timedelta(hours=24)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    lines = []
    alerts = []

    def p(*args):
        line = " ".join(str(a) for a in args)
        lines.append(line)
        print(line)

    def alert(msg):
        alerts.append(msg)
        p("  *** ALERTA:", msg)

    p()
    p("=" * 64)
    p("OBSERVATION MODE — WEEKLY REPORT")
    p("Gerado em:", now.strftime("%Y-%m-%d %H:%M UTC"))
    p("=" * 64)

    # ── MISSÃO 1: GROWTH TRACKING ─────────────────────────────────────────────
    p()
    p(sep("="))
    p("MISSAO 1 — GROWTH TRACKING")
    p(sep("="))

    # Jobs
    p()
    p("-- JOBS --")
    p("%-22s %8s %8s %8s %8s" % ("source", "total", "+24h", "+7d", "+30d"))
    p(sep())
    job_totals = {}
    for src in JOB_SOURCES:
        row = db.execute(text(
            "SELECT COUNT(*) as total,"
            " SUM(CASE WHEN collected_at >= :d1 THEN 1 ELSE 0 END) as d1,"
            " SUM(CASE WHEN collected_at >= :d7 THEN 1 ELSE 0 END) as d7,"
            " SUM(CASE WHEN collected_at >= :d30 THEN 1 ELSE 0 END) as d30"
            " FROM raw_collections WHERE module='jobs' AND source_name=:s"
        ), {"s": src, "d1": d1, "d7": d7, "d30": d30}).fetchone()
        total, n1, n7, n30 = row[0] or 0, row[1] or 0, row[2] or 0, row[3] or 0
        job_totals[src] = total
        p("%-22s %8d %8d %8d %8d" % (src, total, n1, n7, n30))

    # RE
    p()
    p("-- REAL ESTATE --")
    p("%-28s %8s %8s %8s %8s" % ("agency", "total", "+24h", "+7d", "+30d"))
    p(sep())
    re_totals = {}
    for agency, pattern in RE_URL_MAP.items():
        row = db.execute(text(
            "SELECT COUNT(*) as total,"
            " SUM(CASE WHEN collected_at >= :d1 THEN 1 ELSE 0 END) as d1,"
            " SUM(CASE WHEN collected_at >= :d7 THEN 1 ELSE 0 END) as d7,"
            " SUM(CASE WHEN collected_at >= :d30 THEN 1 ELSE 0 END) as d30"
            " FROM raw_collections"
            " WHERE module='real_estate' AND target_url LIKE :p"
        ), {"p": pattern, "d1": d1, "d7": d7, "d30": d30}).fetchone()
        total, n1, n7, n30 = row[0] or 0, row[1] or 0, row[2] or 0, row[3] or 0
        re_totals[agency] = total
        p("%-28s %8d %8d %8d %8d" % (agency, total, n1, n7, n30))

    # ── MISSÃO 2: FRESHNESS TRACKING ─────────────────────────────────────────
    p()
    p(sep("="))
    p("MISSAO 2 — FRESHNESS TRACKING")
    p(sep("="))

    p()
    p("-- JOBS --")
    p("%-22s %-20s %-8s" % ("source", "last_collection", "status"))
    p(sep())
    for src in JOB_SOURCES:
        row = db.execute(text(
            "SELECT MAX(collected_at) FROM raw_collections"
            " WHERE module='jobs' AND source_name=:s"
        ), {"s": src}).fetchone()
        ultima = row[0]
        if ultima:
            age_h = (now - ultima.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            status = "ACTIVE" if age_h < 48 else ("STALE" if age_h < 336 else "DEAD")
            p("%-22s %-20s %-8s (%.0fh ago)" % (src, str(ultima)[:16], status, age_h))
        else:
            p("%-22s %-20s %-8s" % (src, "NUNCA", "DEAD"))

    p()
    p("-- REAL ESTATE --")
    p("%-28s %-20s %-8s" % ("agency", "last_collection", "status"))
    p(sep())
    for agency, pattern in RE_URL_MAP.items():
        row = db.execute(text(
            "SELECT MAX(collected_at) FROM raw_collections"
            " WHERE module='real_estate' AND target_url LIKE :p"
        ), {"p": pattern}).fetchone()
        ultima = row[0]
        if ultima:
            age_h = (now - ultima.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            status = "ACTIVE" if age_h < 48 else ("STALE" if age_h < 336 else "DEAD")
            p("%-28s %-20s %-8s (%.0fh ago)" % (agency, str(ultima)[:16], status, age_h))
        else:
            p("%-28s %-20s %-8s" % (agency, "NUNCA", "DEAD"))

    # ── MISSÃO 3: CONCENTRATION TREND ────────────────────────────────────────
    p()
    p(sep("="))
    p("MISSAO 3 — CONCENTRATION TREND")
    p(sep("="))

    # Jobs
    p()
    p("-- JOBS --")
    total_jobs = sum(job_totals.values())
    hhi_jobs = hhi(list(job_totals.values()))
    top_job = max(job_totals, key=job_totals.get) if job_totals else "N/A"
    top_job_share = 100 * job_totals.get(top_job, 0) / total_jobs if total_jobs else 0

    for src, cnt in sorted(job_totals.items(), key=lambda x: -x[1]):
        if cnt > 0:
            share = 100 * cnt / total_jobs
            p("  %-22s %5d  %5.1f%%" % (src, cnt, share))
    p()
    p("  Top Source : %s (%.1f%%)" % (top_job, top_job_share))
    p("  HHI        : %.0f" % hhi_jobs)
    p("  Baseline   : %s %.1f%%, HHI %.0f" % (
        BASELINE["jobs"]["top_source"], BASELINE["jobs"]["top_share"], BASELINE["jobs"]["hhi"]))
    p("  Delta HHI  : %s (%.0f -> %.0f)" % (
        delta_tag(hhi_jobs, BASELINE["jobs"]["hhi"]), BASELINE["jobs"]["hhi"], hhi_jobs))

    if top_job_share > ALERT_THRESHOLDS["jobs_top_share"]:
        alert("Jobs top_share %.1f%% > %.0f%% (threshold)" % (
            top_job_share, ALERT_THRESHOLDS["jobs_top_share"]))
    if hhi_jobs > ALERT_THRESHOLDS["jobs_hhi"]:
        alert("Jobs HHI %.0f > %.0f (threshold)" % (hhi_jobs, ALERT_THRESHOLDS["jobs_hhi"]))

    # RE
    p()
    p("-- REAL ESTATE --")
    total_re = sum(re_totals.values())
    hhi_re = hhi(list(re_totals.values()))
    top_re = max(re_totals, key=re_totals.get) if re_totals else "N/A"
    top_re_share = 100 * re_totals.get(top_re, 0) / total_re if total_re else 0

    for agency, cnt in sorted(re_totals.items(), key=lambda x: -x[1]):
        if cnt > 0:
            share = 100 * cnt / total_re
            p("  %-28s %5d  %5.1f%%" % (agency, cnt, share))
    p()
    p("  Top Source : %s (%.1f%%)" % (top_re, top_re_share))
    p("  HHI        : %.0f" % hhi_re)
    p("  Baseline   : %s %.1f%%, HHI %.0f" % (
        BASELINE["real_estate"]["top_source"],
        BASELINE["real_estate"]["top_share"],
        BASELINE["real_estate"]["hhi"]))
    p("  Delta HHI  : %s (%.0f -> %.0f)" % (
        delta_tag(hhi_re, BASELINE["real_estate"]["hhi"]),
        BASELINE["real_estate"]["hhi"], hhi_re))

    if top_re_share > ALERT_THRESHOLDS["re_top_share"]:
        alert("RE top_share %.1f%% > %.0f%% (threshold)" % (
            top_re_share, ALERT_THRESHOLDS["re_top_share"]))
    if hhi_re > ALERT_THRESHOLDS["re_hhi"]:
        alert("RE HHI %.0f > %.0f (threshold)" % (hhi_re, ALERT_THRESHOLDS["re_hhi"]))

    # ── MISSÃO 4: RESILIENCE TREND ────────────────────────────────────────────
    p()
    p(sep("="))
    p("MISSAO 4 — RESILIENCE TREND")
    p(sep("="))

    p()
    p("-- JOBS: sem Greenhouse --")
    without_gh = {s: c for s, c in job_totals.items() if s != "greenhouse"}
    total_wgh = sum(without_gh.values())
    hhi_wgh = hhi(list(without_gh.values()))
    p("  Registros restantes : %d  (%.1f%% do total)" % (
        total_wgh, 100 * total_wgh / total_jobs if total_jobs else 0))
    p("  Fontes restantes    : %d" % sum(1 for v in without_gh.values() if v > 0))
    p("  HHI sem GH          : %.0f" % hhi_wgh)
    p("  Dataset util?       : %s" % ("SIM" if total_wgh >= 200 else "NAO"))

    p()
    p("-- REAL ESTATE: sem Apolar --")
    without_ap = {s: c for s, c in re_totals.items() if s != "apolar"}
    total_wap = sum(without_ap.values())
    hhi_wap = hhi(list(without_ap.values()))
    p("  Registros restantes : %d  (%.1f%% do total)" % (
        total_wap, 100 * total_wap / total_re if total_re else 0))
    p("  Fontes restantes    : %d" % sum(1 for v in without_ap.values() if v > 0))
    p("  HHI sem Apolar      : %.0f" % hhi_wap)
    p("  Dataset util?       : %s" % ("SIM" if total_wap >= 100 else "NAO"))

    # ── MISSÃO 5: SOURCE HEALTH ────────────────────────────────────────────────
    p()
    p(sep("="))
    p("MISSAO 5 — SOURCE HEALTH")
    p(sep("="))

    p()
    p("-- JOBS: runs recentes (7d) --")
    p("%-22s %8s %8s %8s %8s" % ("source", "runs", "success", "failed", "dup_rate"))
    p(sep())
    for src in JOB_SOURCES:
        row = db.execute(text(
            "SELECT COUNT(*) as runs,"
            " SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as ok,"
            " SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as err,"
            " SUM(COALESCE(items_collected,0)) as collected,"
            " SUM(COALESCE(raw_saved_count,0)) as saved"
            " FROM collection_runs"
            " WHERE collector_name=:c AND started_at >= :d7"
        ), {"c": f"jobs.{src}", "d7": d7}).fetchone()
        runs, ok, err, collected, saved = (
            row[0] or 0, row[1] or 0, row[2] or 0, row[3] or 0, row[4] or 0)
        dup_rate = (1 - saved / collected) if collected > 0 else 0
        p("%-22s %8d %8d %8d %7.0f%%" % (src, runs, ok, err, dup_rate * 100))

    # ── MISSÃO 6: PRICE COVERAGE (RE) ────────────────────────────────────────
    p()
    p(sep("="))
    p("MISSAO 6 — PRICE COVERAGE (REAL ESTATE)")
    p(sep("="))

    p()
    # price fica em raw_json->'structured_fields'->>'price'
    row = db.execute(text(
        "SELECT COUNT(*) as total,"
        " SUM(CASE WHEN raw_json->'structured_fields'->>'price' IS NOT NULL"
        "       AND raw_json->'structured_fields'->>'price' != '' THEN 1 ELSE 0 END) as has_price"
        " FROM raw_collections WHERE module='real_estate'"
    )).fetchone()
    total_re_raw = row[0] or 0
    has_price_sf = row[1] or 0
    p("  Total registros RE       : %d" % total_re_raw)
    p("  Com price (structured)   : %d  (%.1f%%)" % (
        has_price_sf, 100 * has_price_sf / total_re_raw if total_re_raw else 0))
    p()
    p("  Por agencia:")
    rows_price = db.execute(text(
        "SELECT"
        "  regexp_replace(target_url, 'https?://([^/]+).*', '\\1') as domain,"
        "  COUNT(*) as total,"
        "  SUM(CASE WHEN raw_json->'structured_fields'->>'price' IS NOT NULL"
        "       AND raw_json->'structured_fields'->>'price' != '' THEN 1 ELSE 0 END) as has_price"
        " FROM raw_collections WHERE module='real_estate'"
        " GROUP BY 1 ORDER BY total DESC"
    )).fetchall()
    for rp in rows_price:
        pct = 100 * (rp[2] or 0) / rp[1] if rp[1] else 0
        p("  %-38s total=%-5d price=%-5d (%.1f%%)" % (rp[0], rp[1], rp[2] or 0, pct))

    # ── ALERTAS ───────────────────────────────────────────────────────────────
    p()
    p(sep("="))
    p("ALERTAS ATIVOS")
    p(sep("="))
    if alerts:
        for a in alerts:
            p("  [ALERTA]", a)
    else:
        p("  Nenhum alerta ativo.")

    # ── SALVAR RELATÓRIO ──────────────────────────────────────────────────────
    report_dir = Path("observation_reports")
    report_dir.mkdir(exist_ok=True)
    filename = report_dir / ("report_%s.txt" % now.strftime("%Y-%m-%d"))
    filename.write_text("\n".join(lines), encoding="utf-8")

    # ── JSON snapshot para trending ───────────────────────────────────────────
    snapshot = {
        "date": now.strftime("%Y-%m-%d"),
        "jobs": {
            "totals": job_totals,
            "total": total_jobs,
            "hhi": round(hhi_jobs, 1),
            "top_source": top_job,
            "top_share": round(top_job_share, 2),
            "without_greenhouse": {"total": total_wgh, "hhi": round(hhi_wgh, 1)},
        },
        "real_estate": {
            "totals": re_totals,
            "total": total_re,
            "hhi": round(hhi_re, 1),
            "top_source": top_re,
            "top_share": round(top_re_share, 2),
            "without_apolar": {"total": total_wap, "hhi": round(hhi_wap, 1)},
        },
        "alerts": alerts,
    }
    snap_file = report_dir / ("snapshot_%s.json" % now.strftime("%Y-%m-%d"))
    snap_file.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

    db.close()
    p()
    p("Relatorio salvo em:", str(filename))
    p("Snapshot JSON    :", str(snap_file))
    return snapshot


if __name__ == "__main__":
    run_report()
