import psycopg

conn = psycopg.connect("postgresql://data_core:data_core@localhost:5432/data_core")

enums = conn.execute(
    "SELECT typname FROM pg_type WHERE typtype = 'e' ORDER BY typname"
).fetchall()
print("PG enums:", [r[0] for r in enums])

nba_tables = conn.execute(
    "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'nba%' ORDER BY tablename"
).fetchall()
print("NBA tables:", [r[0] for r in nba_tables])

wnba_tables = conn.execute(
    "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'wnba%'"
).fetchall()
print("WNBA tables:", [r[0] for r in wnba_tables])

counts = {}
for t in ["nba_games", "nba_odds", "nba_features", "nba_signals", "nba_quant_bets", "nba_edge_registry"]:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        counts[t] = n
    except Exception as e:
        counts[t] = f"ERROR: {e}"

print("NBA row counts:", counts)
conn.close()
