import io
import re
import unicodedata

import geopandas as gpd
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from rapidfuzz import fuzz, process


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
    "Eesti": ("EST", "Eesti"),
    "Norra": ("NOR", "Norra"),
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
    ],
    "Yamalo-Nenets Autonomous Okrug": [
        "Yamalo-Nenets Autonomous Okrug",
        "Yamalo-Nenetskiy Avtonomnyy Okrug",
    ],
}


def norm_name(value):
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value).lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(
        r"\b(republic|oblast|krai|kray|autonomous|okrug|district|raion|rayon|municipal|region|of|the)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


@st.cache_data(show_spinner="Laen Venemaa halduspiire…")
def load_boundaries(url):
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    return gpd.read_file(io.BytesIO(response.content)).to_crs(4326)


def best_name_column(gdf):
    for column in ["shapeName", "NAME_1", "NAME_2", "name", "NAME"]:
        if column in gdf.columns:
            return column
    raise KeyError(f"Nimeveergu ei leitud. Veerud: {list(gdf.columns)}")


def match_table(data_names, boundary_names, aliases=None, threshold=68):
    aliases = aliases or {}
    normalized = {name: norm_name(name) for name in boundary_names}
    records = []

    for data_name in sorted(set(x for x in data_names if pd.notna(x))):
        best = None

        for candidate in [data_name] + aliases.get(data_name, []):
            result = process.extractOne(
                norm_name(candidate),
                normalized,
                scorer=fuzz.WRatio,
                score_cutoff=threshold,
            )

            if result:
                _, score, boundary_name = result
                if best is None or score > best[1]:
                    best = (boundary_name, score, candidate)

        records.append(
            {
                "data_name": data_name,
                "boundary_name": best[0] if best else None,
                "match_score": round(best[1], 1) if best else None,
                "matched_from": best[2] if best else None,
            }
        )

    return pd.DataFrame(records)


def prepare_map_data(filtered_df):
    df = filtered_df.copy()

    if "object_id" not in df.columns:
        raise KeyError("Kaardivaate jaoks peab tabelis olema veerg 'object_id'.")

    if "country" not in df.columns:
        df["country"] = pd.NA

    df["country_iso3"] = df["country"].map(
        lambda x: COUNTRY_MAP.get(x, (None, None))[0]
    )
    df["country_clean"] = df["country"].map(
        lambda x: COUNTRY_MAP.get(x, (None, None))[1]
    )

    return df


def render_country_map(df):
    counts = (
        df.dropna(subset=["country_iso3"])
        .groupby(["country_iso3", "country_clean"], as_index=False)
        .agg(museaale=("object_id", "nunique"))
    )

    if counts.empty:
        st.info("Praeguse filtriga ei ole riigikaardile sobivaid andmeid.")
        return

    fig = px.choropleth(
        counts,
        locations="country_iso3",
        color="museaale",
        hover_name="country_clean",
        projection="natural earth",
        labels={"museaale": "Museaalide arv"},
        title="Museaalide arv riigiti",
    )

    fig.update_geos(showcoastlines=True, showframe=False, fitbounds="locations")
    fig.update_layout(margin=dict(l=0, r=0, t=45, b=0))

    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        counts.sort_values("museaale", ascending=False),
        hide_index=True,
        use_container_width=True,
    )


def render_regions_map(df):
    required = {"country", "modern_region_est", "modern_region_eng", "object_id"}
    missing = required - set(df.columns)

    if missing:
        st.warning(
            "Regioonikaardi jaoks puuduvad veerud: "
            + ", ".join(sorted(missing))
        )
        return

    rus = df[
        (df["country"] == "Venemaa")
        & df["modern_region_eng"].notna()
    ].copy()

    if rus.empty:
        st.info("Praeguse filtriga ei ole Venemaa regioonide andmeid.")
        return

    adm1 = load_boundaries(ADM1_URL)
    name_col = best_name_column(adm1)

    counts = (
        rus.groupby(
            ["modern_region_est", "modern_region_eng"],
            as_index=False,
        )
        .agg(museaale=("object_id", "nunique"))
    )

    matches = match_table(
        counts["modern_region_eng"],
        adm1[name_col].dropna().astype(str).tolist(),
        REGION_ALIASES,
    )

    counts = counts.merge(
        matches,
        left_on="modern_region_eng",
        right_on="data_name",
        how="left",
    )

    map_df = adm1.merge(
        counts,
        left_on=name_col,
        right_on="boundary_name",
        how="inner",
    ).reset_index(drop=True)

    if map_df.empty:
        st.warning("Regioonid ei leidnud piirifailis vastet.")
        st.dataframe(counts, hide_index=True, use_container_width=True)
        return

    map_df["map_id"] = map_df.index.astype(str)

    fig = px.choropleth_map(
        map_df,
        geojson=map_df.__geo_interface__,
        locations="map_id",
        featureidkey="properties.map_id",
        color="museaale",
        hover_name="modern_region_est",
        hover_data={
            "modern_region_eng": True,
            "match_score": True,
            "map_id": False,
        },
        map_style="carto-positron",
        center={"lat": 61, "lon": 65},
        zoom=2.2,
        opacity=0.75,
        title="Museaalide arv Venemaa regiooniti",
    )

    fig.update_layout(margin=dict(l=0, r=0, t=45, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        counts.sort_values("museaale", ascending=False),
        hide_index=True,
        use_container_width=True,
    )


def render_districts_map(df):
    required = {
        "country",
        "modern_region_est",
        "modern_region_eng",
        "modern_rajon_est",
        "modern_rajon_eng",
        "object_id",
    }
    missing = required - set(df.columns)

    if missing:
        st.warning(
            "Rajoonikaardi jaoks puuduvad veerud: "
            + ", ".join(sorted(missing))
        )
        return

    rus = df[
        (df["country"] == "Venemaa")
        & df["modern_region_eng"].notna()
        & df["modern_rajon_eng"].notna()
    ].copy()

    if rus.empty:
        st.info("Praeguse filtriga ei ole Venemaa rajoonide andmeid.")
        return

    regions = sorted(rus["modern_region_eng"].dropna().unique())
    selected = st.selectbox(
        "Vali regioon",
        regions,
        key="map_selected_region",
    )

    adm1 = load_boundaries(ADM1_URL)
    adm2 = load_boundaries(ADM2_URL)

    adm1_name = best_name_column(adm1)
    adm2_name = best_name_column(adm2)

    # Väldime nimeveergude konflikti spatial join'i ajal.
    adm2_points = adm2[[adm2_name, "geometry"]].copy()
    adm2_points = adm2_points.rename(
        columns={adm2_name: "adm2_boundary_name"}
    )
    adm2_points["geometry"] = adm2_points.geometry.representative_point()

    adm1_for_join = adm1[[adm1_name, "geometry"]].copy()
    adm1_for_join = adm1_for_join.rename(
        columns={adm1_name: "adm1_boundary_name"}
    )

    parents = gpd.sjoin(
        adm2_points,
        adm1_for_join,
        how="left",
        predicate="within",
    )[
        ["adm2_boundary_name", "adm1_boundary_name"]
    ].drop_duplicates()

    adm2_named = adm2.rename(
        columns={adm2_name: "adm2_boundary_name"}
    )

    adm2_named = adm2_named.merge(
        parents,
        on="adm2_boundary_name",
        how="left",
    )

    region_match = match_table(
        [selected],
        adm1[adm1_name].dropna().astype(str).tolist(),
        REGION_ALIASES,
    )

    if region_match.empty or pd.isna(
        region_match.iloc[0]["boundary_name"]
    ):
        st.warning("Valitud regioon ei leidnud piirifailis vastet.")
        return

    adm2_region = adm2_named[
        adm2_named["adm1_boundary_name"]
        == region_match.iloc[0]["boundary_name"]
    ].copy()

    counts = (
        rus[rus["modern_region_eng"] == selected]
        .groupby(
            [
                "modern_region_est",
                "modern_region_eng",
                "modern_rajon_est",
                "modern_rajon_eng",
            ],
            as_index=False,
        )
        .agg(museaale=("object_id", "nunique"))
    )

    matches = match_table(
        counts["modern_rajon_eng"],
        adm2_region["adm2_boundary_name"]
        .dropna()
        .astype(str)
        .tolist(),
        threshold=62,
    )

    counts = counts.merge(
        matches,
        left_on="modern_rajon_eng",
        right_on="data_name",
        how="left",
    )

    map_df = adm2_region.merge(
        counts,
        left_on="adm2_boundary_name",
        right_on="boundary_name",
        how="inner",
    ).reset_index(drop=True)

    if map_df.empty:
        st.warning(
            "Selle regiooni rajoonid ei leidnud piirifailis vastet."
        )
        st.dataframe(counts, hide_index=True, use_container_width=True)
        return

    map_df["map_id"] = map_df.index.astype(str)
    center = map_df.geometry.union_all().centroid

    fig = px.choropleth_map(
        map_df,
        geojson=map_df.__geo_interface__,
        locations="map_id",
        featureidkey="properties.map_id",
        color="museaale",
        hover_name="modern_rajon_est",
        hover_data={
            "modern_rajon_eng": True,
            "modern_region_est": True,
            "match_score": True,
            "map_id": False,
        },
        map_style="carto-positron",
        center={"lat": center.y, "lon": center.x},
        zoom=4.2,
        opacity=0.78,
        title=f"Rajoonid: {selected}",
    )

    fig.update_layout(margin=dict(l=0, r=0, t=45, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        counts.sort_values("museaale", ascending=False),
        hide_index=True,
        use_container_width=True,
    )


def render_control(df):
    c1, c2, c3 = st.columns(3)

    c1.metric("Museaale filtris", df["object_id"].nunique())

    c2.metric(
        "Tuvastatud riigiga",
        df[df["country_iso3"].notna()]["object_id"].nunique(),
    )

    if "modern_region_eng" in df.columns:
        n_regions = df[
            (df["country"] == "Venemaa")
            & df["modern_region_eng"].notna()
        ]["object_id"].nunique()
    else:
        n_regions = 0

    c3.metric("Venemaa regiooniga", n_regions)


def render_map(filtered_df):
    st.subheader("Soome-ugri museaalide päritolukaart")
    st.caption(
        "Kaart kasutab haldusüksuste polügoone. "
        "Arv näitab unikaalsete museaalide hulka."
    )

    if filtered_df is None or filtered_df.empty:
        st.info("Praeguse filtriga ei ole kaardil museaale.")
        return

    df = prepare_map_data(filtered_df)

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Riigid",
            "Venemaa regioonid",
            "Venemaa rajoonid",
            "Vastete kontroll",
        ]
    )

    with tab1:
        render_country_map(df)

    with tab2:
        render_regions_map(df)

    with tab3:
        render_districts_map(df)

    with tab4:
        render_control(df)
