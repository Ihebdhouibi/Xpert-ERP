"""
Seed script: realistic vehicle repair shop parts catalogue.
Adds categories and parts for garage_id=1.

Usage:
    docker exec xpert_erp_api python seed_parts.py
    # or locally:
    python seed_parts.py
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

GARAGE_ID = 1

# Detect whether running inside Docker (use 'db' host) or locally (127.0.0.1:5433)
_in_docker = os.path.exists("/.dockerenv")
DB_HOST = "db" if _in_docker else "127.0.0.1"
DB_PORT = 5432 if _in_docker else 5433
DB_NAME = os.environ.get("POSTGRES_DB", "xpert_erp")
DB_USER = os.environ.get("POSTGRES_USER", "xpert")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "xpert_dev_password")

# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------
CATEGORIES = [
    {"name": "Filtration",             "description": "Filtres huile, air, habitacle et carburant"},
    {"name": "Huiles & Lubrifiants",   "description": "Huiles moteur, boîte de vitesses et graisse"},
    {"name": "Freinage",               "description": "Plaquettes, disques, étriers et flexibles de frein"},
    {"name": "Suspension & Direction", "description": "Amortisseurs, rotules, biellettes et roulements"},
    {"name": "Électrique & Batterie",  "description": "Batteries, alternateurs, démarreurs et câblage"},
    {"name": "Éclairage",              "description": "Ampoules, optiques et kits LED"},
    {"name": "Distribution & Moteur",  "description": "Courroie de distribution, joints, bougies et chaînes"},
    {"name": "Refroidissement",        "description": "Radiateurs, thermostats, pompes à eau et durites"},
    {"name": "Transmission & Embrayage","description": "Kits embrayage, joints homocinétiques, huile de boîte"},
    {"name": "Carrosserie & Vitrage",  "description": "Essuie-glaces, miroirs, joints de carrosserie"},
]

# ---------------------------------------------------------------------------
# Parts: (sku_code, name, category_index, unit, purchase_minor, selling_minor, reorder_threshold, reorder_qty)
# category_index is 0-based into CATEGORIES list above
# ---------------------------------------------------------------------------
PARTS = [
    # --- Filtration (0) ---
    ("FIL-HUI-001", "Filtre à huile universel",         0, "pcs",  450,   850,  10, 20),
    ("FIL-HUI-BOX", "Boîte 10 filtres à huile mixtes",  0, "box", 3500,  6200,   3,  5),
    ("FIL-AIR-001", "Filtre à air panneau",             0, "pcs",  600,  1100,   8, 15),
    ("FIL-HAB-001", "Filtre d'habitacle / pollen",      0, "pcs",  700,  1400,   8, 15),
    ("FIL-CAR-001", "Filtre carburant diesel universel",0, "pcs",  900,  1700,   5, 10),

    # --- Huiles & Lubrifiants (1) ---
    ("HUI-5W30-5L",  "Huile moteur 5W-30 Full Synth 5L",1, "L",   1800,  3200,  10, 20),
    ("HUI-5W40-5L",  "Huile moteur 5W-40 Full Synth 5L",1, "L",   1900,  3400,  10, 20),
    ("HUI-10W40-1L", "Huile moteur 10W-40 Semi-synth 1L",1,"L",    450,   800,  20, 40),
    ("HUI-BOI-75W90","Huile boîte manuelle 75W-90 1L",  1, "L",    600,  1100,   5, 10),
    ("GRS-POLY-400", "Graisse polyvalente 400g",        1, "pcs",  350,   650,   5, 10),
    ("LIQ-FRN-500",  "Liquide de frein DOT 4 500ml",    1, "pcs",  380,   700,   8, 15),
    ("LIQ-REF-5L",   "Liquide refroidissement -37° 5L", 1, "L",    900,  1600,   8, 15),

    # --- Freinage (2) ---
    ("FRN-PLQ-AV01", "Plaquettes de frein avant (kit)",  2, "kit", 1400,  2700,   8, 15),
    ("FRN-PLQ-AR01", "Plaquettes de frein arrière (kit)",2, "kit", 1100,  2100,   8, 15),
    ("FRN-DSQ-AV28", "Disque de frein avant Ø280mm",    2, "pcs", 2200,  4200,   4, 10),
    ("FRN-DSQ-AV30", "Disque de frein avant Ø300mm",    2, "pcs", 2500,  4700,   4, 10),
    ("FRN-DSQ-AR25", "Disque de frein arrière Ø258mm",  2, "pcs", 1900,  3600,   4, 10),
    ("FRN-CPT-AV",   "Étrier de frein AV complet (échange)", 2, "pcs", 4500, 8500, 2, 4),
    ("FRN-FLX-001",  "Flexible de frein renforcé",      2, "pcs",  750,  1400,   5, 10),

    # --- Suspension & Direction (3) ---
    ("SUS-AMO-AV01", "Amortisseur avant (unité)",       3, "pcs", 3500,  6500,   4,  8),
    ("SUS-AMO-AR01", "Amortisseur arrière (unité)",     3, "pcs", 2900,  5500,   4,  8),
    ("SUS-ROT-INF",  "Rotule inférieure triangle",      3, "pcs",  950,  1800,   4,  8),
    ("SUS-BIE-001",  "Biellette de barre stabilisatrice",3,"pcs",  480,   900,   5, 10),
    ("SUS-RLT-RAV",  "Roulement de roue avant",         3, "pcs", 1800,  3400,   4,  8),
    ("SUS-RLT-RAR",  "Roulement de roue arrière",       3, "pcs", 1600,  3000,   4,  8),
    ("DIR-EXT-001",  "Rotule de direction extérieure",  3, "pcs",  700,  1300,   5, 10),

    # --- Électrique & Batterie (4) ---
    ("BAT-70AH-12V", "Batterie 70Ah 12V 640A",          4, "pcs", 5500, 10000,   3,  5),
    ("BAT-80AH-12V", "Batterie 80Ah 12V 720A",          4, "pcs", 6500, 11500,   3,  5),
    ("ELC-ALT-001",  "Alternateur reconditionné 90A",   4, "pcs",12000, 22000,   1,  2),
    ("ELC-DEM-001",  "Démarreur reconditionné",         4, "pcs", 9000, 17000,   1,  2),
    ("ELC-BOG-001",  "Câbles de démarrage 400A",        4, "pcs",  800,  1500,   3,  6),

    # --- Éclairage (5) ---
    ("ECL-H4-55W",   "Ampoule H4 55/60W hallogène",     5, "pcs",  150,   350,  20, 40),
    ("ECL-H7-55W",   "Ampoule H7 55W hallogène",        5, "pcs",  130,   300,  20, 40),
    ("ECL-LED-H7",   "Kit LED H7 canbus 6000K",         5, "kit",  900,  1800,  10, 20),
    ("ECL-LED-H4",   "Kit LED H4 canbus 6000K",         5, "kit",  950,  1900,  10, 20),
    ("ECL-W5W-SET",  "Jeu 10 ampoules W5W 5W",          5, "set",  120,   280,  10, 20),

    # --- Distribution & Moteur (6) ---
    ("DIS-KIT-001",  "Kit distribution complet (courroie + galet + pompe eau)", 6, "kit", 5500, 9800, 3, 6),
    ("DIS-COU-001",  "Courroie de distribution seule",  6, "pcs", 1800,  3200,   5, 10),
    ("MOT-BOU-NGK",  "Bougies d'allumage NGK (jeu 4)",  6, "set",  800,  1500,   5, 10),
    ("MOT-JNT-CUL",  "Joint de culasse",                6, "pcs", 2800,  5200,   2,  4),
    ("MOT-KIT-JNT",  "Kit joints moteur complet",       6, "kit", 3500,  6500,   2,  4),

    # --- Refroidissement (7) ---
    ("REF-RAD-001",  "Radiateur de refroidissement",    7, "pcs", 7500, 13500,   2,  4),
    ("REF-THM-001",  "Thermostat + joint",              7, "pcs",  650,  1200,   5, 10),
    ("REF-PMP-001",  "Pompe à eau",                     7, "pcs", 2200,  4000,   3,  6),
    ("REF-DUR-001",  "Durite supérieure radiateur",     7, "pcs",  600,  1100,   4,  8),
    ("REF-DUR-002",  "Durite inférieure radiateur",     7, "pcs",  550,  1000,   4,  8),

    # --- Transmission & Embrayage (8) ---
    ("EMB-KIT-001",  "Kit embrayage complet (disque + méca + butée)", 8, "kit", 8500, 15500, 2, 4),
    ("EMB-DSQ-001",  "Disque d'embrayage seul",         8, "pcs", 3000,  5500,   2,  4),
    ("TRN-HOM-AV",   "Soufflet de cardan avec graisse", 8, "pcs", 1200,  2200,   4,  8),
    ("TRN-AXE-AV",   "Demi-arbre de transmission AV",  8, "pcs",10000, 18000,   1,  2),

    # --- Carrosserie & Vitrage (9) ---
    ("ESS-PLT-600",  "Balai essuie-glace plat 600mm",   9, "pcs",  450,   900,  10, 20),
    ("ESS-PLT-400",  "Balai essuie-glace plat 400mm",   9, "pcs",  380,   750,  10, 20),
    ("VIT-JNT-PAR",  "Joint de pare-brise universel",   9, "pcs",  900,  1700,   3,  6),
    ("CAR-MAS-500",  "Mastic carrosserie 500g",         9, "pcs",  350,   700,   5, 10),
    ("CAR-ANT-BAS",  "Traitement anticorrosion bas de caisse 1L", 9, "L", 750, 1400, 4, 8),
]


async def seed() -> None:
    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
        )

        # ---------------------------------------------------------------
        # Categories
        # ---------------------------------------------------------------
        log.info("Seeding %d categories…", len(CATEGORIES))
        cat_id_map: dict[int, int] = {}  # index → DB id
        for i, cat in enumerate(CATEGORIES):
            existing = await conn.fetchval(
                "SELECT id FROM part_category WHERE garage_id=$1 AND name=$2",
                GARAGE_ID, cat["name"],
            )
            if existing:
                cat_id_map[i] = existing
                log.info("  Category exists: %s (id=%d)", cat["name"], existing)
            else:
                new_id = await conn.fetchval(
                    """
                    INSERT INTO part_category (garage_id, name, description)
                    VALUES ($1, $2, $3) RETURNING id
                    """,
                    GARAGE_ID, cat["name"], cat["description"],
                )
                cat_id_map[i] = new_id
                log.info("  Created category: %s (id=%d)", cat["name"], new_id)

        # ---------------------------------------------------------------
        # Parts
        # ---------------------------------------------------------------
        log.info("Seeding %d parts…", len(PARTS))
        now = datetime.now(timezone.utc)
        created = 0
        skipped = 0
        for (sku, name, cat_idx, uom, purchase_minor, selling_minor, reorder_thr, reorder_qty) in PARTS:
            existing = await conn.fetchval(
                "SELECT id FROM part WHERE garage_id=$1 AND sku_code=$2",
                GARAGE_ID, sku,
            )
            if existing:
                skipped += 1
                continue
            await conn.execute(
                """
                INSERT INTO part (
                    public_id, garage_id, sku_code, name, unit_of_measure,
                    purchase_price_minor, selling_price_minor,
                    category_id, reorder_threshold, reorder_quantity,
                    status, version, created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                """,
                str(uuid.uuid4()), GARAGE_ID, sku, name, uom,
                purchase_minor, selling_minor,
                cat_id_map[cat_idx], reorder_thr, reorder_qty,
                'active', 1, now, now,
            )
            created += 1

        log.info("Parts: %d created, %d already existed", created, skipped)

    except Exception as e:
        log.error("Seed failed: %s", e)
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            await conn.close()


if __name__ == '__main__':
    asyncio.run(seed())
