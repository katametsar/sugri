
from pathlib import Path
import io
import re
import unicodedata
import requests
import pandas as pd
import geopandas as gpd
import plotly.express as px
import streamlit as st
from rapidfuzz import fuzz, process

st.set_page_config(page_title="Soome-ugri kogude kaart", layout="wide")

BASE = Path(__file__).resolve().parent
DATA = BASE / "object_best_place_modern_regions_raions.csv"

ADM1_URL = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/RUS/ADM1/geoBoundaries-RUS-ADM1_simplified.geojson"
ADM2_URL = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/RUS/ADM2/geoBoundaries-RUS-ADM2_simplified.geojson"

COUNTRY_MAP = {
    "Venemaa": ("RUS", "Venemaa"),
    "Soome": ("FIN", "Soome"),
    "Läti": ("LVA", "Läti"),
    "Rootsi": ("SWE", "Rootsi"),
    "Ungari": ("HUN", "Ungari"),
    "Ukraina": ("UKR", "Ukraina"),
    "Moldova": ("MDA", "Moldova"),
}

REGION_ALIASES = {
    "Republic of Karelia": ["Karelia", "Respublika Kareliya"],
    "Komi Republic": ["Komi", "Respublika Komi"],
    "Mari El Republic": ["Mari El", "Respublika Mariy El"],
    "Udmurt Republic": ["Udmurtia", "Udmurtskaya Respublika"],
    "Republic of Mordovia": ["Mordovia", "Respublika Mordoviya"],
    "Republic of Bashkortostan": ["Bashkortostan", "Respublika Bashkortostan"],
    "Republic of Tatarstan": ["Tatarstan", "Respublika Tatarstan"],
    "Khanty-Mansi Autonomous Okrug – Yugra": [
        "Khanty-Mansi Autonomous Okrug",
        "Khanty-Mansiyskiy Avtonomnyy Okrug-Yugra",
        "Khanty-Mansiyskiy avtonomnyy okrug"
    ],
    "Yamalo-Nenets Autonomous Okrug": [
        "Yamalo-Nenets Autonomous Okrug",
        "Yamalo-Nenetskiy Avtonomnyy Okrug"
    ],
}

def norm_name(value):
    if pd.isna(value):
        return ""
    s = str(value).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\b(republic|oblast|krai|autonomous|okrug|district|raion|rayon|municipal|of|the)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())

@st.cache_data(show_spinner=False)
def load_objects():
    return pd.read_csv(DATA)

@st.cache_data(show_spinner="Laen Venemaa halduspiire…")
def load_boundaries(url):
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    return gpd.read_file(io.BytesIO(r.content)).to_crs(4326)

def best_name_column(gdf):
    for col in ["shapeName", "NAME_1", "NAME_2", "name", "NAME"]:
        if col in gdf.columns:
            return col
    raise KeyError(f"Nimeveergu ei leitud. Veerud: {list(gdf.columns)}")

def match_table(data_names, boundary_names, aliases=None, threshold=68):
    aliases = aliases or {}
    bnorm = {name: norm_name(name) for name in boundary_names}
    records = []
    for data_name in sorted(set(x for x in data_names if pd.notna(x))):
        candidates = [data_name] + aliases.get(data_name, [])
        best = None
        for candidate in candidates:
            q = norm_name(candidate)
            result = process.extractOne(
                q,
                bnorm,
                scorer=fuzz.WRatio,
                score_cutoff=threshold
            )
            if result:
                _, score, boundary_name = result
                if best is None or score > best[1]:
                    best = (boundary_name, score, candidate)
        records.append({
            "data_name": data_name,
            "boundary_name": best[0] if best else None,
            "match_score": round(best[1], 1) if best else None,
            "matched_from": best[2] if best else None,
        })
    return pd.DataFrame(records)

df = load_objects()
df["country_iso3"] = df["country"].map(lambda x: COUNTRY_MAP.get(x, (None, None))[0])
df["country_clean"] = df["country"].map(lambda x: COUNTRY_MAP.get(x, (None, None))[1])

st.title("Soome-ugri museaalide päritolukaart")
st.caption(
    "Kaart kasutab haldusüksuste polügoone, mitte museaalide latitude–longitude punkte. "
    "Arv näitab unikaalsete museaalide hulka."
)

with st.sidebar:
    st.header("Filtrid")
    statuses = st.multiselect(
        "Normaliseerimise staatus",
        ["kindel", "tõenäoline", "vajab kontrolli"],
        default=["kindel", "tõenäoline"],
    )
    filtered = df[df["normalization_status"].isin(statuses)].copy()
    st.metric("Museaale filtris", filtered["object_id"].nunique())
    st.info(
        "Riikide kaardile lähevad ainult tuvastatud riiginimed. "
        "Arvkoodid ja tundmatud väärtused jäetakse kaardilt välja."
    )

tab1, tab2, tab3, tab4 = st.tabs(
    ["Riigid", "Venemaa regioonid", "Venemaa rajoonid", "Vastete kontroll"]
)

with tab1:
    counts = (
        filtered.dropna(subset=["country_iso3"])
        .groupby(["country_iso3", "country_clean"], as_index=False)
        .agg(museaale=("object_id", "nunique"))
    )
    fig = px.choropleth(
        counts,
        locations="country_iso3",
        color="museaale",
        hover_name="country_clean",
        projection="natural earth",
        title="Museaalide arv riigiti",
    )
    fig.update_geos(showcoastlines=True, showframe=False, fitbounds="locations")
    fig.update_layout(margin=dict(l=0, r=0, t=45, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(counts.sort_values("museaale", ascending=False), hide_index=True)

with tab2:
    rus = filtered[
        (filtered["country"] == "Venemaa") &
        filtered["modern_region_eng"].notna()
    ].copy()
    adm1 = load_boundaries(ADM1_URL)
    adm1_name = best_name_column(adm1)
    region_counts = (
        rus.groupby(["modern_region_est", "modern_region_eng"], as_index=False)
        .agg(museaale=("object_id", "nunique"))
    )
    region_matches = match_table(
        region_counts["modern_region_eng"],
        adm1[adm1_name].dropna().astype(str).tolist(),
        aliases=REGION_ALIASES,
    )
    region_counts = region_counts.merge(
        region_matches,
        left_on="modern_region_eng",
        right_on="data_name",
        how="left",
    )
    map_df = adm1.merge(
        region_counts,
        left_on=adm1_name,
        right_on="boundary_name",
        how="inner",
    )
    fig = px.choropleth_map(
        map_df,
        geojson=map_df.geometry.__geo_interface__,
        locations=map_df.index,
        color="museaale",
        hover_name="modern_region_est",
        hover_data={"modern_region_eng": True, "match_score": True},
        map_style="carto-positron",
        center={"lat": 61, "lon": 65},
        zoom=2.2,
        opacity=0.75,
        title="Museaalide arv Venemaa regiooniti",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=45, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        region_counts.sort_values("museaale", ascending=False),
        hide_index=True,
        use_container_width=True,
    )

with tab3:
    rus = filtered[
        (filtered["country"] == "Venemaa") &
        filtered["modern_region_eng"].notna() &
        filtered["modern_rajon_eng"].notna()
    ].copy()
    regions = sorted(rus["modern_region_eng"].dropna().unique())
    selected_region = st.selectbox(
        "Vali regioon",
        regions,
        format_func=lambda x: (
            rus.loc[rus["modern_region_eng"] == x, "modern_region_est"].dropna().iloc[0]
            if not rus.loc[rus["modern_region_eng"] == x, "modern_region_est"].dropna().empty
            else x
        ),
    )

    adm1 = load_boundaries(ADM1_URL)
    adm2 = load_boundaries(ADM2_URL)
    adm1_name = best_name_column(adm1)
    adm2_name = best_name_column(adm2)

    # Assign every ADM2 polygon to its containing ADM1 polygon.
    adm2_points = adm2.copy()
    adm2_points["geometry"] = adm2_points.geometry.representative_point()
    parent = gpd.sjoin(
        adm2_points[[adm2_name, "geometry"]],
        adm1[[adm1_name, "geometry"]],
        how="left",
        predicate="within",
    )[[adm2_name, adm1_name]]
    adm2 = adm2.merge(parent, on=adm2_name, how="left")

    region_match = match_table(
        [selected_region],
        adm1[adm1_name].dropna().astype(str).tolist(),
        aliases=REGION_ALIASES,
    )
    boundary_region = region_match.iloc[0]["boundary_name"]
    adm2_region = adm2[adm2[adm1_name] == boundary_region].copy()

    counts = (
        rus[rus["modern_region_eng"] == selected_region]
        .groupby(
            ["modern_region_est", "modern_region_eng", "modern_rajon_est", "modern_rajon_eng"],
            as_index=False,
        )
        .agg(museaale=("object_id", "nunique"))
    )
    district_matches = match_table(
        counts["modern_rajon_eng"],
        adm2_region[adm2_name].dropna().astype(str).tolist(),
        threshold=62,
    )
    counts = counts.merge(
        district_matches,
        left_on="modern_rajon_eng",
        right_on="data_name",
        how="left",
    )
    map_df = adm2_region.merge(
        counts,
        left_on=adm2_name,
        right_on="boundary_name",
        how="inner",
    )

    if map_df.empty:
        st.warning("Selle regiooni rajoonid ei leidnud piirifailis automaatset vastet.")
    else:
        center = map_df.geometry.unary_union.centroid
        fig = px.choropleth_map(
            map_df,
            geojson=map_df.geometry.__geo_interface__,
            locations=map_df.index,
            color="museaale",
            hover_name="modern_rajon_est",
            hover_data={
                "modern_rajon_eng": True,
                "modern_region_est": True,
                "match_score": True,
            },
            map_style="carto-positron",
            center={"lat": center.y, "lon": center.x},
            zoom=4.2,
            opacity=0.78,
            title=f"Rajoonid: {selected_region}",
        )
        fig.update_layout(margin=dict(l=0, r=0, t=45, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        counts.sort_values("museaale", ascending=False),
        hide_index=True,
        use_container_width=True,
    )

with tab4:
    st.subheader("Kaardile kaasamise ülevaade")
    c1, c2, c3 = st.columns(3)
    c1.metric("Kõik museaalid", df["object_id"].nunique())
    c2.metric(
        "Tuvastatud riigiga",
        df[df["country_iso3"].notna()]["object_id"].nunique(),
    )
    c3.metric(
        "Venemaa tänapäevase regiooniga",
        df[
            (df["country"] == "Venemaa") &
            df["modern_region_eng"].notna()
        ]["object_id"].nunique(),
    )

    bad_countries = (
        df[df["country_iso3"].isna()]
        .groupby("country", dropna=False)
        .agg(museaale=("object_id", "nunique"))
        .reset_index()
        .sort_values("museaale", ascending=False)
    )
    st.markdown("#### Kaardilt välja jäävad riigiväärtused")
    st.dataframe(bad_countries, hide_index=True, use_container_width=True)
