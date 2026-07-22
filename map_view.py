import io
import re
import unicodedata

import geopandas as gpd
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from rapidfuzz import fuzz, process


ADM1_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
    "releaseData/gbOpen/RUS/ADM1/"
    "geoBoundaries-RUS-ADM1_simplified.geojson"
)
ADM2_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
    "releaseData/gbOpen/RUS/ADM2/"
    "geoBoundaries-RUS-ADM2_simplified.geojson"
)

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
    "Republic of Bashkortostan": [
        "Bashkortostan",
        "Respublika Bashkortostan",
    ],
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
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(
        r"\b(republic|oblast|krai|kray|autonomous|okrug|district|"
        r"raion|rayon|municipal|region|of|the)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


@st.cache_data(show_spinner="Laen Venemaa halduspiire…")
def load_boundaries(url):
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    return gpd.read_file(
        io.BytesIO(response.content)
    ).to_crs(4326)


def best_name_column(gdf):
    for column in [
        "shapeName",
        "NAME_1",
        "NAME_2",
        "name",
        "NAME",
    ]:
        if column in gdf.columns:
            return column

    raise KeyError(
        "Halduspiiride nimeveergu ei leitud. "
        f"Veerud: {list(gdf.columns)}"
    )


def match_table(
    data_names,
    boundary_names,
    aliases=None,
    threshold=68,
):
    aliases = aliases or {}
    normalized = {
        name: norm_name(name)
        for name in boundary_names
    }
    records = []

    for data_name in sorted(
        set(value for value in data_names if pd.notna(value))
    ):
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
                    best = (
                        boundary_name,
                        score,
                        candidate,
                    )

        records.append(
            {
                "data_name": data_name,
                "boundary_name": (
                    best[0] if best else None
                ),
                "match_score": (
                    round(best[1], 1) if best else None
                ),
            }
        )

    return pd.DataFrame(records)


def prepare_map_data(filtered_df):
    df = filtered_df.copy()

    if "object_id" not in df.columns:
        raise KeyError(
            "Kaardivaate jaoks peab tabelis olema "
            "veerg 'object_id'."
        )

    if "country" not in df.columns:
        df["country"] = pd.NA

    df["country_iso3"] = df["country"].map(
        lambda value: COUNTRY_MAP.get(
            value,
            (None, None),
        )[0]
    )
    df["country_clean"] = df["country"].map(
        lambda value: COUNTRY_MAP.get(
            value,
            (None, None),
        )[1]
    )

    return df


def first_existing_column(df, candidates):
    for column in candidates:
        if column in df.columns:
            return column
    return None


def display_items(items, heading):
    st.markdown(f"### {heading}")

    if items.empty:
        st.info("Selle valikuga ei leitud museaale.")
        return

    item_count = items["object_id"].nunique()
    st.caption(
        f"Leitud {item_count:,} museaali".replace(",", " ")
    )

    column_choices = {
        "Museaalinumber": [
            "museal_number",
            "museum_number",
            "number",
        ],
        "Eseme nimetus": [
            "title",
            "object_name",
            "name",
            "nimetus",
        ],
        "Kogumise aasta": [
            "year",
            "collection_year",
        ],
        "Koguja": [
            "collectors_joined",
            "collector_normalized",
            "collector",
        ],
        "Rahvarühm": [
            "ethnic_group",
            "ethnicity",
        ],
        "Kogumiskoht": [
            "best_place",
            "koht",
            "place",
        ],
        "MuIS": [
            "object_url",
            "muis_url",
            "url",
        ],
    }

    selected = {}
    for label, candidates in column_choices.items():
        column = first_existing_column(
            items,
            candidates,
        )
        if column:
            selected[column] = label

    if not selected:
        st.warning(
            "Esemete tabeli jaoks ei leitud sobivaid veerge."
        )
        return

    table = (
        items[list(selected.keys())]
        .rename(columns=selected)
        .drop_duplicates()
        .copy()
    )

    if "Kogumise aasta" in table.columns:
        table["Kogumise aasta"] = pd.to_numeric(
            table["Kogumise aasta"],
            errors="coerce",
        ).astype("Int64")

    sort_columns = [
        column
        for column in [
            "Kogumise aasta",
            "Eseme nimetus",
        ]
        if column in table.columns
    ]
    if sort_columns:
        table = table.sort_values(
            sort_columns,
            na_position="last",
        )

    column_config = {}
    if "MuIS" in table.columns:
        column_config["MuIS"] = st.column_config.LinkColumn(
            "MuIS",
            display_text="Ava",
        )

    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        column_config=column_config,
        height=min(
            600,
            38 * (len(table) + 1),
        ),
    )


def render_country_map(df):
    counts = (
        df.dropna(subset=["country_iso3"])
        .groupby(
            ["country_iso3", "country_clean"],
            as_index=False,
        )
        .agg(museaale=("object_id", "nunique"))
    )

    if counts.empty:
        st.info(
            "Praeguste filtritega ei ole "
            "riigikaardile sobivaid andmeid."
        )
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

    fig.update_geos(
        showcoastlines=True,
        showframe=False,
        fitbounds="locations",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=45, b=0)
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    countries = sorted(
        counts["country_clean"]
        .dropna()
        .astype(str)
        .unique()
    )
    selected_country = st.selectbox(
        "Vali riik, mille museaale vaadata",
        countries,
        key="map_country",
    )

    country_items = df[
        df["country_clean"] == selected_country
    ].copy()

    display_items(
        country_items,
        f"{selected_country}: museaalid",
    )


def render_regions_map(df):
    required = {
        "country",
        "modern_region_est",
        "modern_region_eng",
        "object_id",
    }
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
        & df["modern_region_est"].notna()
    ].copy()

    if rus.empty:
        st.info(
            "Praeguste filtritega ei ole "
            "Venemaa regioonide andmeid."
        )
        return

    adm1 = load_boundaries(ADM1_URL)
    name_col = best_name_column(adm1)

    counts = (
        rus.groupby(
            [
                "modern_region_est",
                "modern_region_eng",
            ],
            as_index=False,
        )
        .agg(museaale=("object_id", "nunique"))
    )

    matches = match_table(
        counts["modern_region_eng"],
        adm1[name_col]
        .dropna()
        .astype(str)
        .tolist(),
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
        st.warning(
            "Regioonid ei leidnud piirifailis vastet."
        )
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
            "museaale": True,
            "map_id": False,
        },
        labels={"museaale": "Museaalide arv"},
        map_style="carto-positron",
        center={"lat": 61, "lon": 65},
        zoom=2.2,
        opacity=0.75,
        title="Museaalide arv Venemaa regiooniti",
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=45, b=0)
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    region_options = (
        counts[
            [
                "modern_region_est",
                "modern_region_eng",
            ]
        ]
        .drop_duplicates()
        .sort_values("modern_region_est")
    )

    est_to_eng = dict(
        zip(
            region_options["modern_region_est"],
            region_options["modern_region_eng"],
        )
    )

    selected_region_est = st.selectbox(
        "Vali regioon, mille museaale vaadata",
        list(est_to_eng.keys()),
        key="map_region_est",
    )
    selected_region_eng = est_to_eng[
        selected_region_est
    ]

    region_items = rus[
        rus["modern_region_eng"]
        == selected_region_eng
    ].copy()

    display_items(
        region_items,
        f"{selected_region_est}: museaalid",
    )


def get_adm2_with_parent_regions():
    adm1 = load_boundaries(ADM1_URL)
    adm2 = load_boundaries(ADM2_URL)

    adm1_name = best_name_column(adm1)
    adm2_name = best_name_column(adm2)

    adm2_points = adm2[
        [adm2_name, "geometry"]
    ].copy()
    adm2_points = adm2_points.rename(
        columns={
            adm2_name: "adm2_boundary_name"
        }
    )
    adm2_points["geometry"] = (
        adm2_points.geometry.representative_point()
    )

    adm1_for_join = adm1[
        [adm1_name, "geometry"]
    ].copy()
    adm1_for_join = adm1_for_join.rename(
        columns={
            adm1_name: "adm1_boundary_name"
        }
    )

    parents = gpd.sjoin(
        adm2_points,
        adm1_for_join,
        how="left",
        predicate="within",
    )[
        [
            "adm2_boundary_name",
            "adm1_boundary_name",
        ]
    ].drop_duplicates()

    adm2_named = adm2.rename(
        columns={
            adm2_name: "adm2_boundary_name"
        }
    )
    adm2_named = adm2_named.merge(
        parents,
        on="adm2_boundary_name",
        how="left",
    )

    return (
        adm1,
        adm1_name,
        adm2_named,
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
        & df["modern_region_est"].notna()
        & df["modern_rajon_eng"].notna()
        & df["modern_rajon_est"].notna()
    ].copy()

    if rus.empty:
        st.info(
            "Praeguste filtritega ei ole "
            "Venemaa rajoonide andmeid."
        )
        return

    region_options = (
        rus[
            [
                "modern_region_est",
                "modern_region_eng",
            ]
        ]
        .drop_duplicates()
        .sort_values("modern_region_est")
    )
    est_to_eng = dict(
        zip(
            region_options["modern_region_est"],
            region_options["modern_region_eng"],
        )
    )

    selected_region_est = st.selectbox(
        "Vali regioon",
        list(est_to_eng.keys()),
        key="map_district_region",
    )
    selected_region_eng = est_to_eng[
        selected_region_est
    ]

    adm1, adm1_name, adm2_named = (
        get_adm2_with_parent_regions()
    )

    region_match = match_table(
        [selected_region_eng],
        adm1[adm1_name]
        .dropna()
        .astype(str)
        .tolist(),
        REGION_ALIASES,
    )

    if (
        region_match.empty
        or pd.isna(
            region_match.iloc[0][
                "boundary_name"
            ]
        )
    ):
        st.warning(
            "Valitud regioon ei leidnud "
            "piirifailis vastet."
        )
        return

    boundary_region = region_match.iloc[0][
        "boundary_name"
    ]
    adm2_region = adm2_named[
        adm2_named["adm1_boundary_name"]
        == boundary_region
    ].copy()

    counts = (
        rus[
            rus["modern_region_eng"]
            == selected_region_eng
        ]
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
        adm2_region[
            "adm2_boundary_name"
        ]
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
            "Selle regiooni rajoonid ei "
            "leidnud piirifailis vastet."
        )
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
            "museaale": True,
            "map_id": False,
        },
        labels={"museaale": "Museaalide arv"},
        map_style="carto-positron",
        center={
            "lat": center.y,
            "lon": center.x,
        },
        zoom=4.2,
        opacity=0.78,
        title=f"{selected_region_est}: museaalide arv rajooniti",
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=45, b=0)
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    district_options = (
        counts[
            [
                "modern_rajon_est",
                "modern_rajon_eng",
            ]
        ]
        .drop_duplicates()
        .sort_values("modern_rajon_est")
    )

    est_to_eng_district = dict(
        zip(
            district_options["modern_rajon_est"],
            district_options["modern_rajon_eng"],
        )
    )

    selected_district_est = st.selectbox(
        "Vali rajoon, mille museaale vaadata",
        list(est_to_eng_district.keys()),
        key="map_district_est",
    )
    selected_district_eng = (
        est_to_eng_district[
            selected_district_est
        ]
    )

    district_items = rus[
        (
            rus["modern_region_eng"]
            == selected_region_eng
        )
        & (
            rus["modern_rajon_eng"]
            == selected_district_eng
        )
    ].copy()

    display_items(
        district_items,
        (
            f"{selected_region_est}, "
            f"{selected_district_est}: museaalid"
        ),
    )


def render_map(filtered_df):
    st.subheader(
        "Soome-ugri museaalide päritolukaart"
    )
    st.caption(
        "Kaart arvestab kõiki rakenduse külgribal "
        "valitud filtreid. Kaardi sees saab valida "
        "riigi, regiooni või rajooni ning vaadata "
        "selle piirkonna museaale."
    )

    if (
        filtered_df is None
        or filtered_df.empty
    ):
        st.info(
            "Praeguste filtritega ei ole "
            "kaardil museaale."
        )
        return

    df = prepare_map_data(filtered_df)

    tab1, tab2, tab3 = st.tabs(
        [
            "Riigid",
            "Venemaa regioonid",
            "Venemaa rajoonid",
        ]
    )

    with tab1:
        render_country_map(df)

    with tab2:
        render_regions_map(df)

    with tab3:
        render_districts_map(df)
