"""Seed bulk villages + population history for load testing (k6).

    docker compose exec api python -m app.scripts.seed_performance_data
    docker compose exec api python -m app.scripts.seed_performance_data --villages 5000
    docker compose exec api python -m app.scripts.seed_performance_data --clean   # remove seed data only

Design notes
- Uses set-based native SQL (INSERT ... SELECT generate_series) instead of the ORM:
  tens of thousands of rows in seconds, and it counts as the "native SQL" case.
- Seed rows are identifiable: villages.slug LIKE 'seed-village-%' and
  sources.title LIKE '[SEED]%'. Real data is never touched.
- Idempotent: every run removes the previous seed data first.
- Deterministic (setseed): same data every run, so before/after benchmarks are comparable.
- Respects the schema constraints: unique (village_id, reference_year, source_id),
  year range 1800..2100, verification_status in (pending, verified, disputed).
- Governorates are inserted only if missing (ON CONFLICT DO NOTHING).
"""
import argparse

from sqlalchemy import text

from app.db.session import SessionLocal

GOVERNORATES = [
    ("جنين", "Jenin"),
    ("طوباس", "Tubas"),
    ("طولكرم", "Tulkarm"),
    ("نابلس", "Nablus"),
    ("قلقيلية", "Qalqilya"),
    ("سلفيت", "Salfit"),
    ("رام الله والبيرة", "Ramallah and al-Bireh"),
    ("أريحا", "Jericho"),
    ("القدس", "Jerusalem"),
    ("بيت لحم", "Bethlehem"),
    ("الخليل", "Hebron"),
]

SEED_SOURCES = [
    ("[SEED] PCBS Population Census", "census"),
    ("[SEED] PCBS Annual Estimates", "official"),
    ("[SEED] Municipality Records", "official"),
]

CLEAN_POPULATION = text(
    "DELETE FROM population_records WHERE village_id IN "
    "(SELECT id FROM villages WHERE slug LIKE 'seed-village-%')"
)
CLEAN_VILLAGES = text("DELETE FROM villages WHERE slug LIKE 'seed-village-%'")
CLEAN_SOURCES = text("DELETE FROM sources WHERE title LIKE '[SEED]%'")

INSERT_GOVERNORATE = text(
    "INSERT INTO governorates (name_ar, name_en) VALUES (:ar, :en) "
    "ON CONFLICT (name_ar) DO NOTHING"
)

INSERT_SOURCE = text(
    "INSERT INTO sources (title, source_type) "
    "SELECT CAST(:title AS VARCHAR), CAST(:stype AS VARCHAR) "
    "WHERE NOT EXISTS (SELECT 1 FROM sources WHERE title = CAST(:title AS VARCHAR))"
)

INSERT_VILLAGES = text(
    """
    WITH g AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY id) - 1 AS rn FROM governorates
    ),
    gc AS (SELECT COUNT(*) AS c FROM g)
    INSERT INTO villages
        (slug, name_ar, name_en, name_origin, historical_overview,
         latitude, longitude, elevation_m, area_km2, governorate_id)
    SELECT
        'seed-village-' || s,
        'قرية تجريبية ' || s,
        'Seed Village ' || s,
        'Generated name origin for load testing, village ' || s || '.',
        'Generated historical overview for load testing, village ' || s || '.',
        ROUND(CAST(31.35 + random() * 1.0 AS numeric), 6),
        ROUND(CAST(34.90 + random() * 0.6 AS numeric), 6),
        ROUND(CAST(100 + random() * 900 AS numeric), 1),
        ROUND(CAST(1 + random() * 30 AS numeric), 2),
        g.id
    FROM generate_series(1, CAST(:n AS integer)) AS s
    JOIN g ON g.rn = s % (SELECT c FROM gc)
    """
)

# 8 yearly records per village, one source per (village, year) so the unique
# constraint holds. Every 10th village gets an extra conflicting 2017 value from
# another source (status 'disputed') to mimic the conflict strategy in ADR-005.
INSERT_POPULATION = text(
    """
    WITH src AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY id) - 1 AS rn
        FROM sources WHERE title LIKE '[SEED]%'
    ),
    sc AS (SELECT COUNT(*) AS c FROM src),
    yrs AS (
        SELECT unnest(ARRAY[1997, 2007, 2012, 2017, 2020, 2022, 2024, 2025]) AS year
    )
    INSERT INTO population_records
        (village_id, population, reference_year, source_id, verification_status, notes)
    SELECT
        v.id,
        ROUND(
            (300 + (v.id * 7919) % 12000)
            * POWER(1.025, y.year - 1997)
            * (0.97 + random() * 0.06)
        )::int,
        y.year,
        src.id,
        CASE WHEN v.id % 5 = 0 THEN 'pending' ELSE 'verified' END,
        'seed'
    FROM villages v
    CROSS JOIN yrs y
    JOIN src ON src.rn = (v.id + y.year) % (SELECT c FROM sc)
    WHERE v.slug LIKE 'seed-village-%'
    UNION ALL
    SELECT
        v.id,
        ROUND((300 + (v.id * 7919) % 12000) * POWER(1.025, 20) * 1.08)::int,
        2017,
        src.id,
        'disputed',
        'seed: conflicting value from another source'
    FROM villages v
    JOIN src ON src.rn = (v.id + 2017 + 1) % (SELECT c FROM sc)
    WHERE v.slug LIKE 'seed-village-%' AND v.id % 10 = 0
    """
)


def clean(db) -> None:
    db.execute(CLEAN_POPULATION)
    db.execute(CLEAN_VILLAGES)
    db.execute(CLEAN_SOURCES)


def seed(db, villages: int) -> None:
    clean(db)
    db.execute(text("SELECT setseed(0.42)"))
    for ar, en in GOVERNORATES:
        db.execute(INSERT_GOVERNORATE, {"ar": ar, "en": en})
    for title, stype in SEED_SOURCES:
        db.execute(INSERT_SOURCE, {"title": title, "stype": stype})
    db.execute(INSERT_VILLAGES, {"n": villages})
    db.execute(INSERT_POPULATION)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--villages", type=int, default=2000, help="number of villages (default 2000)")
    parser.add_argument("--clean", action="store_true", help="only remove previously seeded data")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.clean:
            clean(db)
            db.commit()
            print("Seed data removed")
            return 0

        seed(db, args.villages)
        db.commit()

        # refresh planner statistics so EXPLAIN / k6 results are realistic
        for table in ("villages", "population_records", "sources"):
            db.execute(text(f"ANALYZE {table}"))
        db.commit()

        v = db.execute(text("SELECT COUNT(*) FROM villages WHERE slug LIKE 'seed-village-%'")).scalar()
        p = db.execute(
            text(
                "SELECT COUNT(*) FROM population_records pr "
                "JOIN villages v ON v.id = pr.village_id WHERE v.slug LIKE 'seed-village-%'"
            )
        ).scalar()
        print(f"Seeded {v} villages and {p} population records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
