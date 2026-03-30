"""
build_segments.py  v5-final
----------------------------
Lit traffic.csv et produit segments.json.

CORRECTIONS :
  1. Bounding box elargie : lat >= 40.60 (couvre Brooklyn/NJ/tunnels)
  2. Longitude tronquee rejetee : lon > -73.50 (truncation CSV "-73." ou "-73.0")
  3. Outlier GPS : correction uniquement si ecart lat > 0.040 deg (typos grossieres uniquement)
     Les ecarts < 0.04 deg sont des variations normales de trace de route.
"""

import csv, json, os, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
IN   = os.path.join(HERE, "traffic.csv")
OUT  = os.path.join(HERE, "segments.json")

THRESHOLDS = [
    (200,   "free",     "#22d07a"),
    (400,   "normal",   "#a3e635"),
    (700,   "slow",     "#f5c518"),
    (1200,  "heavy",    "#ff7a2b"),
    (9999,  "critical", "#ff3b3b"),
]

# Seuil outlier conservateur : seulement les vraies typos (>0.04 deg = ~4.5 km)
MAX_LAT_DEVIATION = 0.040

def tt_status(tt):
    for limit, label, color in THRESHOLDS:
        if tt < limit:
            return label, color
    return "critical", "#ff3b3b"


def is_valid(lat_s, lng_s):
    """
    Validation - zone NYC elargie + rejet des coords tronquees par le CSV.
    """
    try:
        lat = float(lat_s)
        lng = float(lng_s)
    except ValueError:
        return False, 0, 0

    # Rejeter longitudes tronquees (ex: '-73.' -> -73.0, '-73.0' sans decimales suffisantes)
    dec_lon = len(lng_s.strip().split(".")[-1]) if "." in lng_s else 0
    if dec_lon < 3:
        return False, 0, 0

    # Bounding box elargie : Manhattan + Brooklyn + NJ (tunnels, Battery Tunnel, BQE)
    if not (40.60 <= lat <= 40.95 and -74.30 <= lng <= -73.70):
        return False, 0, 0

    return True, round(lat, 6), round(lng, 6)


def fix_outliers(pts):
    """
    Corrige uniquement les typos grossieres (ecart > MAX_LAT_DEVIATION).
    Les variations normales de trace sont preservees.
    """
    if len(pts) < 3:
        return pts, []

    lats = [p[0] for p in pts]
    med_lat = statistics.median(lats)

    corrected = list(pts)
    log = []

    for i, pt in enumerate(corrected):
        if pt is None:
            continue
        lat, lon = pt
        if abs(lat - med_lat) > MAX_LAT_DEVIATION:
            prev_ok = next(
                (corrected[j] for j in range(i - 1, -1, -1)
                 if corrected[j] is not None and abs(corrected[j][0] - med_lat) <= MAX_LAT_DEVIATION),
                None
            )
            next_ok = next(
                (corrected[j] for j in range(i + 1, len(corrected))
                 if corrected[j] is not None and abs(corrected[j][0] - med_lat) <= MAX_LAT_DEVIATION),
                None
            )
            if prev_ok and next_ok:
                new_lat = round((prev_ok[0] + next_ok[0]) / 2, 6)
                new_lon = round((prev_ok[1] + next_ok[1]) / 2, 6)
            elif prev_ok:
                new_lat, new_lon = prev_ok[0], prev_ok[1]
            elif next_ok:
                new_lat, new_lon = next_ok[0], next_ok[1]
            else:
                log.append(f"    pt[{i}] ({lat},{lon}) -> SUPPRIME")
                corrected[i] = None
                continue
            log.append(f"    pt[{i}] lat={lat} -> {new_lat} (ecart={abs(lat-med_lat):.4f} deg)")
            corrected[i] = [new_lat, new_lon]

    corrected = [p for p in corrected if p is not None]
    return corrected, log


# ── parse CSV ─────────────────────────────────────────────────────────────
raw = defaultdict(lambda: {"name": "", "pts": None, "speeds": [], "tts": []})

with open(IN, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        lid  = row["link_id"].strip()
        name = row["link_name"].strip()
        try:   spd = float(row["speed"])
        except: spd = 0.0
        try:   tt  = float(row["travel_time"])
        except: tt  = 0.0

        if raw[lid]["pts"] is None:
            pts = []
            for tok in row.get("link_points", "").strip().split():
                p = tok.split(",")
                if len(p) != 2:
                    continue
                ok, lat, lng = is_valid(p[0], p[1])
                if ok:
                    pts.append([lat, lng])
            raw[lid]["pts"]  = pts
            raw[lid]["name"] = name

        if spd > 0:
            raw[lid]["speeds"].append(spd)
        if tt > 0:
            raw[lid]["tts"].append(tt)

# ── build segments ────────────────────────────────────────────────────────
segments = []
total_fixes = 0
skipped = []

for lid, s in raw.items():
    pts_raw = s["pts"]
    if not pts_raw or len(pts_raw) < 2:
        skipped.append(f"  SKIP {lid}: {s['name'][:50]} ({len(pts_raw) if pts_raw else 0} pts valides)")
        continue

    pts, fix_log = fix_outliers(pts_raw)
    if fix_log:
        total_fixes += len(fix_log)
        print(f"  Fix GPS: {s['name'][:60]} (id={lid})")
        for msg in fix_log:
            print(msg)

    if len(pts) < 2:
        skipped.append(f"  SKIP {lid}: {s['name'][:50]} (apres correction: {len(pts)} pts)")
        continue

    avg_speed = round(statistics.mean(s["speeds"]), 1) if s["speeds"] else 0.0
    avg_tt    = round(statistics.mean(s["tts"]),    1) if s["tts"]    else 0.0
    min_tt    = round(min(s["tts"]),                1) if s["tts"]    else 0.0
    max_tt    = round(max(s["tts"]),                1) if s["tts"]    else 0.0
    p10_tt    = round(sorted(s["tts"])[int(len(s["tts"])*.10)], 1) if len(s["tts"]) > 5 else min_tt
    p90_tt    = round(sorted(s["tts"])[int(len(s["tts"])*.90)], 1) if len(s["tts"]) > 5 else max_tt

    status, color = tt_status(avg_tt)
    weight = {"free": 3.5, "normal": 4.0, "slow": 4.5, "heavy": 5.5, "critical": 6.5}[status]

    segments.append({
        "id":        lid,
        "name":      s["name"],
        "pts":       pts,
        "n_pts":     len(pts),
        "avg_speed": avg_speed,
        "avg_tt":    avg_tt,
        "min_tt":    min_tt,
        "max_tt":    max_tt,
        "p10_tt":    p10_tt,
        "p90_tt":    p90_tt,
        "n_samples": len(s["tts"]),
        "status":    status,
        "color":     color,
        "weight":    weight,
    })

segments.sort(key=lambda s: s["avg_tt"], reverse=True)

all_tt = [s["avg_tt"] for s in segments]
counts = {label: sum(1 for s in segments if s["status"] == label)
          for _, label, _ in THRESHOLDS}

out = {
    "segments":   segments,
    "thresholds": [
        {"label": lbl, "color": col, "max_tt": lim, "count": counts.get(lbl, 0)}
        for lim, lbl, col in THRESHOLDS
    ],
    "meta": {
        "total":     len(segments),
        "tt_min":    round(min(all_tt), 1),
        "tt_max":    round(max(all_tt), 1),
        "tt_mean":   round(statistics.mean(all_tt), 1),
        "tt_median": round(statistics.median(all_tt), 1),
    }
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

if skipped:
    print("\nSegments ignores:")
    for s in skipped: print(s)

print(f"\nOK  {OUT}")
print(f"    {len(segments)} segments  |  {total_fixes} point(s) GPS corrige(s)")
for s in segments:
    print(f"  {s['status']:10}  {s['avg_tt']:7.1f}s  {s['avg_speed']:5.1f}mph  {s['n_pts']:2d} pts  {s['name'][:50]}")
