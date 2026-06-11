import psycopg

conn = psycopg.connect("postgresql://data_core:data_core@localhost:5432/data_core")

enums = conn.execute("""
    SELECT t.typname, e.enumlabel
    FROM pg_type t
    JOIN pg_enum e ON t.oid = e.enumtypid
    WHERE t.typtype = 'e'
    ORDER BY t.typname, e.enumsortorder
""").fetchall()

current = None
for typname, label in enums:
    if typname != current:
        print(f"\n{typname}:")
        current = typname
    print(f"  '{label}'")

conn.close()
