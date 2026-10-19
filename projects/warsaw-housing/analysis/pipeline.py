"""
Warsaw apartment prices – data pipeline & analysis
==================================================

Input : Houses.csv  (Kaggle "House prices in Poland", listings from Warsaw,
        Kraków and Poznań, scraped ~2021) + Warsaw districts GeoJSON.
Output: ../data/results.json  – everything the project page needs.

Steps
  1. Load raw file (cp1250 encoding – the source mixes Polish characters).
  2. Clean: drop impossible values, duplicates, outliers (IQR on price/m²).
  3. Geo-enrich: assign every listing to a district with a point-in-polygon
     test (shapely) and compute distance to the city centre (haversine).
  4. Analyse: district ranking, distance curve, building-era segments,
     size effect, floor effect, city comparison.
  5. Model: OLS on log(price/m²) → interpretable premiums (%) used by the
     interactive estimator on the page.

Run:  python pipeline.py --raw ../data/raw/Houses.csv --geo ../data/raw/warszawa-dzielnice.geojson
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point, shape
from shapely.prepared import prep

CENTRES = {  # Palace of Culture / Main Market Square / Old Market Square
    "Warszawa": (52.2318, 21.0060),
    "Kraków": (50.0614, 19.9372),
    "Poznań": (52.4083, 16.9335),
}
CITY_FIX = {"Poznañ": "Poznań", "Krakow": "Kraków"}


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def load(raw: Path) -> pd.DataFrame:
    df = pd.read_csv(raw, index_col=0, encoding="cp1250")
    df["city"] = df["city"].replace(CITY_FIX)
    return df


def clean(df: pd.DataFrame, log: list) -> pd.DataFrame:
    log.append(("Surowe ogłoszenia (3 miasta)", "Raw listings (3 cities)", len(df)))
    df = df.drop_duplicates(subset=["city", "price", "sq", "latitude", "longitude", "floor"])
    log.append(("Po usunięciu duplikatów", "After removing duplicates", len(df)))

    df = df[
        df["price"].between(100_000, 20_000_000)
        & df["sq"].between(15, 250)
        & df["rooms"].between(1, 8)
        & df["year"].between(1850, 2024)
        & df["floor"].between(0, 40)
    ].copy()
    log.append(("Po odrzuceniu błędnych wartości", "After dropping invalid values", len(df)))

    df["ppm"] = df["price"] / df["sq"]
    # IQR outlier filter per city
    grp = df.groupby("city")["ppm"]
    q1, q3 = grp.transform(lambda s: s.quantile(0.25)), grp.transform(lambda s: s.quantile(0.75))
    k = 2.0 * (q3 - q1)
    df = df[df["ppm"].between(q1 - k, q3 + k)]
    log.append(("Po filtrze wartości odstających (IQR)", "After outlier filter (IQR)", len(df)))

    lat_c = df["city"].map(lambda c: CENTRES[c][0])
    lon_c = df["city"].map(lambda c: CENTRES[c][1])
    df["dist_km"] = haversine_km(df["latitude"], df["longitude"], lat_c, lon_c)
    df = df[df["dist_km"] < 25]
    log.append(("W promieniu 25 km od centrum", "Within 25 km of the centre", len(df)))
    return df


def assign_districts(w: pd.DataFrame, geo: Path):
    g = json.loads(geo.read_text(encoding="utf-8"))
    polys = [(f["properties"]["name"], shape(f["geometry"])) for f in g["features"]
             if f["properties"]["name"] != "Warszawa"]
    prepared = [(n, prep(p)) for n, p in polys]

    def which(lat, lon):
        pt = Point(lon, lat)
        for n, p in prepared:
            if p.contains(pt):
                return n
        return None

    w = w.copy()
    w["district"] = [which(a, b) for a, b in zip(w["latitude"], w["longitude"])]
    return w, g


def era(y):
    if y < 1945:
        return "pre1945"
    if y < 1990:
        return "1945_1989"
    if y < 2010:
        return "1990_2009"
    if y < 2019:
        return "2010_2018"
    return "2019plus"


def size_band(s):
    if s < 35:
        return "<35"
    if s < 50:
        return "35-50"
    if s < 70:
        return "50-70"
    if s < 100:
        return "70-100"
    return "100+"


def summary(series):
    return {
        "n": int(series.size),
        "median": round(float(series.median())),
        "q1": round(float(series.quantile(0.25))),
        "q3": round(float(series.quantile(0.75))),
    }


def ols_model(w: pd.DataFrame):
    """log(ppm) ~ district + era + size band + log(1+dist) + floor flags."""
    base = {"district": "Wola", "era": "1945_1989", "size": "50-70"}
    X = pd.DataFrame(index=w.index)
    X["const"] = 1.0
    X["log_dist"] = np.log1p(w["dist_km"])
    X["ground"] = (w["floor"] == 0).astype(float)
    X["high"] = (w["floor"] >= 8).astype(float)
    for col, ref in [("district", base["district"]), ("era", base["era"]), ("size", base["size"])]:
        d = pd.get_dummies(w[col], prefix=col, dtype=float)
        d = d.drop(columns=[f"{col}_{ref}"])
        X = X.join(d)
    y = np.log(w["ppm"].values)
    A = X.values
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ beta
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot
    mape = float(np.mean(np.abs(np.exp(pred) - w["ppm"].values) / w["ppm"].values))
    coefs = dict(zip(X.columns, beta.tolist()))
    return {
        "reference": base,
        "r2": round(r2, 3),
        "mape": round(mape, 3),
        "n": int(len(w)),
        "coef": {k: round(v, 5) for k, v in coefs.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--geo", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent.parent / "data" / "results.json")
    a = ap.parse_args()

    log = []
    df = clean(load(a.raw), log)
    w = df[df["city"] == "Warszawa"].copy()
    w, geo = assign_districts(w, a.geo)
    unassigned = int(w["district"].isna().sum())
    w = w.dropna(subset=["district"])
    log.append(("Warszawa – przypisane do dzielnicy", "Warsaw – matched to a district", len(w)))

    w["era"] = w["year"].map(era)
    w["size"] = w["sq"].map(size_band)

    by_district = (
        w.groupby("district")["ppm"].apply(summary).unstack().reset_index()
        .sort_values("median", ascending=False)
    )
    districts = [
        {"name": r.district, "n": int(r.n), "median": int(r.median), "q1": int(r.q1), "q3": int(r.q3)}
        for r in by_district.itertuples()
    ]

    bins = [0, 2, 4, 6, 8, 10, 12, 15, 25]
    w["dist_bin"] = pd.cut(w["dist_km"], bins=bins, right=False)
    distance = []
    for iv, g in w.groupby("dist_bin", observed=True):
        if len(g) >= 30:
            distance.append({"label": f"{int(iv.left)}–{int(iv.right)}", **summary(g["ppm"])})

    era_order = ["pre1945", "1945_1989", "1990_2009", "2010_2018", "2019plus"]
    eras = [{"key": k, **summary(w.loc[w["era"] == k, "ppm"])} for k in era_order]

    size_order = ["<35", "35-50", "50-70", "70-100", "100+"]
    sizes = [{"key": k, **summary(w.loc[w["size"] == k, "ppm"])} for k in size_order]

    w["floor_band"] = pd.cut(w["floor"], [-1, 0, 2, 4, 7, 40], labels=["0", "1-2", "3-4", "5-7", "8+"])
    floors = [{"key": str(k), **summary(g["ppm"])} for k, g in w.groupby("floor_band", observed=True)]

    cities = []
    for c in ["Warszawa", "Kraków", "Poznań"]:
        g = df[df["city"] == c]
        cities.append({"name": c, **summary(g["ppm"]),
                       "median_price": int(g["price"].median()),
                       "median_sq": round(float(g["sq"].median()), 1)})

    # new-build share per district (supply map insight)
    nb = w.assign(nb=w["year"] >= 2019).groupby("district")["nb"].mean()
    dist_med = w.groupby("district")["dist_km"].median()
    for d in districts:
        d["new_share"] = round(float(nb[d["name"]]), 3)
        d["dist_med"] = round(float(dist_med[d["name"]]), 1)

    model = ols_model(w)

    # trimmed geojson for the map (round coords to keep the file small)
    def rnd(c):
        return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 4), round(c[1], 4)]
    feats = [{"type": "Feature", "properties": {"name": f["properties"]["name"]},
              "geometry": {"type": f["geometry"]["type"], "coordinates": rnd(f["geometry"]["coordinates"])}}
             for f in geo["features"] if f["properties"]["name"] != "Warszawa"]

    # sample of points for the scatter (keeps page light)
    sample = w.sample(n=min(1500, len(w)), random_state=7)
    points = [[round(r.dist_km, 2), int(r.ppm), r.district] for r in sample.itertuples()]

    out = {
        "source": "Kaggle – House prices in Poland (listings scraped ~2021)",
        "pipeline_log": [{"pl": p, "en": e, "n": int(n)} for p, e, n in log],
        "unassigned": unassigned,
        "warsaw": {**summary(w["ppm"]), "median_price": int(w["price"].median()),
                   "median_sq": round(float(w["sq"].median()), 1)},
        "districts": districts,
        "distance": distance,
        "eras": eras,
        "sizes": sizes,
        "floors": floors,
        "cities": cities,
        "model": model,
        "points": points,
        "geo": {"type": "FeatureCollection", "features": feats},
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Saved {a.out} ({a.out.stat().st_size/1024:.0f} KB)")
    for p, _, n in log:
        print(f"  {n:>6}  {p}")
    print(f"  R² = {model['r2']}, MAPE = {model['mape']}")


if __name__ == "__main__":
    main()
