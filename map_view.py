from __future__ import annotations

import io
import re
import unicodedata
from typing import Iterable

import geopandas as gpd
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from rapidfuzz import fuzz, process


# -------------------------------------------------------------------
# HALDUSPIIRIDE ALLIKAD
# -------------------------------------------------------------------

ADM1_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/"
    "9469f09/releaseData/gbOpen/RUS/ADM1/"
    "geoBoundaries-RUS-ADM1_simplified.geojson"
)

ADM2_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/"
    "9469f09/releaseData/gbOpen/RUS/ADM2/"
    "geoBoundaries-RUS-ADM2_simplified.geojson"
)


# -------------------------------------------------------------------
# RIIGIKOODID
# -------------------------------------------------------------------

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


# -------------------------------------------------------------------
# REGIOONIDE NIMEVARIANDID
# -------------------------------------------------------------------

REGION_ALIASES = {
    "Republic of Karelia": [
        "Karelia",
        "Respublika Kareliya",
        "Republic of Kareliya",
    ],
    "Komi Republic": [
        "Komi",
        "Respublika Komi",
        "Republic of Komi",
    ],
    "Mari El Republic": [
        "Mari El",
        "Respublika Mariy El",
        "Republic of Mari El",
    ],
    "Udmurt Republic": [
        "Udmurtia",
        "Udmurtskaya Respublika",
        "Republic of Udmurtia",
    ],
    "Republic of Mordovia": [
        "Mordovia",
        "Respublika Mordoviya",
        "Republic of Mordoviya",
    ],
    "Republic of Bashkortostan": [
        "Bashkortostan",
        "Respublika Bashkortostan",
    ],
    "Republic of Tatarstan": [
        "Tatarstan",
        "Respublika Tatarstan",
    ],
    "Chuvash Republic": [
        "Chuvashia",
        "Chuvash Republic",
        "Chuvashskaya Respublika",
    ],
    "Perm Krai": [
        "Permskiy Kray",
        "Perm Kray",
        "Perm Krai",
    ],
    "Khanty-Mansi Autonomous Okrug – Yugra": [
        "Khanty-Mansi Autonomous Okrug",
        "Khanty-Mansiyskiy Avtonomnyy Okrug-Yugra",
        "Khanty-Mansiyskiy avtonomnyy okrug",
        "Khanty-Mansi Autonomous Okrug - Yugra",
    ],
    "Yamalo-Nenets Autonomous Okrug": [
        "Yamalo-Nenets Autonomous Okrug",
        "Yamalo-Nenetskiy Avtonomnyy Okrug",
        "Yamalo-Nenets Autonomous District",
    ],
}


# -------------------------------------------------------------------
# ABIFUNKTSIOONID
# -------------------------------------------------------------------

def norm_name(value: object) -> str:
    """
    Muudab haldusüksuse nime võrdlemiseks lihtsamaks.

    Näiteks:
    'Republic of Karelia' -> 'karelia'
    'Medvezhyegorsky District' -> 'medvezhyegorsky'
    """
    if pd.isna(value):
        return ""

    text = str(value).lower().strip()

    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    text = text.replace("–", "-").replace("—", "-")

    removable_words = (
        r"\b("
        r"republic|oblast|krai|kray|autonomous|okrug|district|"
        r"raion|rayon|municipal|region|territory|of|the"
        r")\b"
    )

    text = re.sub(removable_words, " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)

    return " ".join(text.split())


@st.cache_data(show_spinner="Laen Venemaa halduspiire…")
def load_boundaries(url: str) -> gpd.GeoDataFrame:
    """
    Laeb geoBoundariesi GeoJSON-faili ja tagastab GeoDataFrame'i.
    """
    response = requests.get(url, timeout=180)
    response.raise_for_status()

    return gpd.read_file(
        io.BytesIO(response.content)
    ).to_crs(4326)


def best_name_column(gdf: gpd.GeoDataFrame) -> str:
    """
    Leiab GeoJSON-ist haldusüksuse nime sisaldava veeru.
    """
    possible_columns = [
        "shapeName",
        "NAME_1",
        "NAME_2",
        "name",
        "NAME",
    ]

    for column in possible_columns:
        if column in gdf.columns:
            return column

    raise KeyError(
        "Haldusüksuse nimeveergu ei leitud. "
        f"GeoJSON-i veerud: {list(gdf.columns)}"
    )


def match_table(
    data_names: Iterable[str],
    boundary_names: Iterable[str],
    aliases: dict[str, list[str]] | None = None,
    threshold: int = 68,
) -> pd.DataFrame:
    """
    Seob andmestiku haldusüksuste nimed piirifaili nimedega.

    Tagastab tabeli:
    - data_name
    - boundary_name
    - match_score
    - matched_from
    """
    aliases = aliases or {}

    boundary_names = [
        str(name)
        for name in boundary_names
        if pd.notna(name)
    ]

    normalized_boundaries = {
        name: norm_name(name)
        for name in boundary_names
    }

    records: list[dict[str, object]] = []

    unique_data_names = sorted(
        {
            str(name)
            for name in data_names
            if pd.notna(name) and str(name).strip()
        }
    )

    for data_name in unique_data_names:
        candidates = [data_name] + aliases.get(data_name, [])

        best_match = None

        for candidate in candidates:
            normalized_candidate = norm_name(candidate)

            if not normalized_candidate:
                continue

            result = process.extractOne(
                normalized_candidate,
                normalized_boundaries,
                scorer=fuzz.WRatio,
                score_cutoff=threshold,
            )

            if result is None:
                continue

            _, score, boundary_name = result

            if best_match is None or score > best_match[1]:
                best_match = (
                    boundary_name,
                    score,
                    candidate,
                )

        records.append(
            {
                "data_name": data_name,
                "boundary_name": (
                    best_match[0]
                    if best_match is not None
                    else None
                ),
                "match_score": (
                    round(float(best_match[1]), 1)
                    if best_match is not None
                    else None
                ),
                "matched_from": (
                    best_match[2]
                    if best_match is not None
                    else None
                ),
            }
        )

    return pd.DataFrame(records)


def prepare_map_data(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """
    Valmistab põhiäpist saadud filtreeritud tabeli kaardi jaoks ette.
    """
    map_df = filtered_df.copy()

    if "country" not in map_df.columns:
        map_df["country"] = pd.NA

    if "object_id" not in map_df.columns:
        raise KeyError(
            "Kaardivaate jaoks peab tabelis olema veerg 'object_id'."
        )

    map_df["country_iso3"] = map_df["country"].map(
        lambda value: COUNTRY_MAP.get(
            value,
            (None, None),
        )[0]
    )

    map_df["country_clean"] = map_df["country"].map(
        lambda value: COUNTRY_MAP.get(
            value,
            (None, None),
        )[1]
    )

    return map_df


def region_display_name(
    df: pd.DataFrame,
    english_name: str,
) -> str:
    """
    Tagastab regiooni eestikeelse nime selectbox'i jaoks.
    """
    if "modern_region_est" not in df.columns:
        return english_name

    names = (
        df.loc[
            df["modern_region_eng"] == english_name,
            "modern_region_est",
        ]
        .dropna()
        .astype(str)
    )

    if names.empty:
        return english_name

    return names.iloc[0]


# -------------------------------------------------------------------
# RIIGIKAART
# -------------------------------------------------------------------

def render_country_map(map_df: pd.DataFrame) -> None:
    st.subheader("Riigid")

    counts = (
        map_df.dropna(
            subset=["country_iso3", "country_clean"]
        )
        .groupby(
            ["country_iso3", "country_clean"],
            as_index=False,
        )
        .agg(
            museaale=("object_id", "nunique")
        )
        .sort_values(
            "museaale",
            ascending=False,
        )
    )

    if counts.empty:
        st.info(
            "Praeguse filtriga ei ole riigikaardile "
            "sobivaid andmeid."
        )
        return

    figure = px.choropleth(
        counts,
        locations="country_iso3",
        color="museaale",
        hover_name="country_clean",
        hover_data={
            "country_iso3": False,
            "museaale": True,
        },
        projection="natural earth",
        labels={
            "museaale": "Museaalide arv",
        },
        title="Museaalide arv riigiti",
    )

    figure.update_geos(
        showcoastlines=True,
        showframe=False,
        fitbounds="locations",
    )

    figure.update_layout(
        margin=dict(
            left=0,
            right=0,
            top=50,
            bottom=0,
        )
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
    )

    st.dataframe(
        counts.rename(
            columns={
                "country_clean": "Riik",
                "museaale": "Museaalide arv",
            }
        )[
            [
                "Riik",
                "Museaalide arv",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


# -------------------------------------------------------------------
# VENEMAA REGIOONIDE KAART
# -------------------------------------------------------------------

def render_russia_regions_map(map_df: pd.DataFrame) -> None:
    st.subheader("Venemaa regioonid")

    required_columns = {
        "country",
        "modern_region_est",
        "modern_region_eng",
        "object_id",
    }

    missing_columns = required_columns - set(map_df.columns)

    if missing_columns:
        st.warning(
            "Regioonikaarti ei saa kuvada, sest puuduvad veerud: "
            + ", ".join(sorted(missing_columns))
        )
        return

    russian_objects = map_df[
        (map_df["country"] == "Venemaa")
        & map_df["modern_region_eng"].notna()
    ].copy()

    if russian_objects.empty:
        st.info(
            "Praeguse filtriga ei ole Venemaa regioonide "
            "kaardile sobivaid andmeid."
        )
        return

    try:
        adm1 = load_boundaries(ADM1_URL)
    except Exception as error:
        st.error(
            "Venemaa regioonide piiride laadimine ebaõnnestus."
        )
        st.exception(error)
        return

    adm1_name_column = best_name_column(adm1)

    region_counts = (
        russian_objects.groupby(
            [
                "modern_region_est",
                "modern_region_eng",
            ],
            as_index=False,
        )
        .agg(
            museaale=("object_id", "nunique")
        )
        .sort_values(
            "museaale",
            ascending=False,
        )
    )

    region_matches = match_table(
        data_names=region_counts["modern_region_eng"],
        boundary_names=adm1[
            adm1_name_column
        ].dropna().astype(str),
        aliases=REGION_ALIASES,
        threshold=68,
    )

    region_counts = region_counts.merge(
        region_matches,
        left_on="modern_region_eng",
        right_on="data_name",
        how="left",
    )

    matched_regions = region_counts[
        region_counts["boundary_name"].notna()
    ].copy()

    map_regions = adm1.merge(
        matched_regions,
        left_on=adm1_name_column,
        right_on="boundary_name",
        how="inner",
    )

    if map_regions.empty:
        st.warning(
            "Ükski andmestiku regioon ei leidnud "
            "piirifailis automaatset vastet."
        )
    else:
        map_regions = map_regions.reset_index(drop=True)
        map_regions["map_id"] = map_regions.index.astype(str)

        figure = px.choropleth_map(
            map_regions,
            geojson=map_regions.geometry.__geo_interface__,
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
            center={
                "lat": 61,
                "lon": 65,
            },
            zoom=2.2,
            opacity=0.75,
            labels={
                "museaale": "Museaalide arv",
                "modern_region_eng": "Ingliskeelne nimi",
                "match_score": "Vaste skoor",
            },
            title="Museaalide arv Venemaa regiooniti",
        )

        figure.update_layout(
            margin=dict(
                left=0,
                right=0,
                top=50,
                bottom=0,
            )
        )

        st.plotly_chart(
            figure,
            use_container_width=True,
        )

    st.dataframe(
        region_counts.rename(
            columns={
                "modern_region_est": "Regioon",
                "modern_region_eng": "Ingliskeelne nimi",
                "museaale": "Museaalide arv",
                "boundary_name": "Piirifaili vaste",
                "match_score": "Vaste skoor",
            }
        )[
            [
                "Regioon",
                "Ingliskeelne nimi",
                "Museaalide arv",
                "Piirifaili vaste",
                "Vaste skoor",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


# -------------------------------------------------------------------
# VENEMAA RAJOONIDE KAART
# -------------------------------------------------------------------

def render_russia_districts_map(map_df: pd.DataFrame) -> None:
    st.subheader("Venemaa rajoonid")

    required_columns = {
        "country",
        "modern_region_est",
        "modern_region_eng",
        "modern_rajon_est",
        "modern_rajon_eng",
        "object_id",
    }

    missing_columns = required_columns - set(map_df.columns)

    if missing_columns:
        st.warning(
            "Rajoonikaarti ei saa kuvada, sest puuduvad veerud: "
            + ", ".join(sorted(missing_columns))
        )
        return

    russian_objects = map_df[
        (map_df["country"] == "Venemaa")
        & map_df["modern_region_eng"].notna()
        & map_df["modern_rajon_eng"].notna()
    ].copy()

    if russian_objects.empty:
        st.info(
            "Praeguse filtriga ei ole Venemaa rajoonide "
            "kaardile sobivaid andmeid."
        )
        return

    regions = sorted(
        russian_objects[
            "modern_region_eng"
        ].dropna().unique()
    )

    selected_region = st.selectbox(
        "Vali regioon",
        options=regions,
        format_func=lambda value: region_display_name(
            russian_objects,
            value,
        ),
        key="map_selected_russia_region",
    )

    try:
        adm1 = load_boundaries(ADM1_URL)
        adm2 = load_boundaries(ADM2_URL)
    except Exception as error:
        st.error(
            "Venemaa rajoonipiiride laadimine ebaõnnestus."
        )
        st.exception(error)
        return

    adm1_name_column = best_name_column(adm1)
    adm2_name_column = best_name_column(adm2)

    # Seome iga ADM2 polügooni tema ADM1 vanemregiooniga.
    adm2_points = adm2[
        [
            adm2_name_column,
            "geometry",
        ]
    ].copy()

    adm2_points["geometry"] = (
        adm2_points.geometry.representative_point()
    )

    parent_regions = gpd.sjoin(
        adm2_points,
        adm1[
            [
                adm1_name_column,
                "geometry",
            ]
        ],
        how="left",
        predicate="within",
    )[
        [
            adm2_name_column,
            adm1_name_column,
        ]
    ].drop_duplicates()

    adm2_with_parent = adm2.merge(
        parent_regions,
        on=adm2_name_column,
        how="left",
    )

    region_match = match_table(
        data_names=[selected_region],
        boundary_names=adm1[
            adm1_name_column
        ].dropna().astype(str),
        aliases=REGION_ALIASES,
        threshold=68,
    )

    if (
        region_match.empty
        or region_match.iloc[0]["boundary_name"] is None
        or pd.isna(
            region_match.iloc[0]["boundary_name"]
        )
    ):
        st.warning(
            "Valitud regioon ei leidnud piirifailis vastet."
        )
        return

    boundary_region_name = (
        region_match.iloc[0]["boundary_name"]
    )

    adm2_region = adm2_with_parent[
        adm2_with_parent[
            adm1_name_column
        ] == boundary_region_name
    ].copy()

    if adm2_region.empty:
        st.warning(
            "Valitud regiooni alla ei leitud "
            "ADM2 rajoonipiire."
        )
        return

    district_counts = (
        russian_objects[
            russian_objects[
                "modern_region_eng"
            ] == selected_region
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
        .agg(
            museaale=("object_id", "nunique")
        )
        .sort_values(
            "museaale",
            ascending=False,
        )
    )

    district_matches = match_table(
        data_names=district_counts[
            "modern_rajon_eng"
        ],
        boundary_names=adm2_region[
            adm2_name_column
        ].dropna().astype(str),
        threshold=62,
    )

    district_counts = district_counts.merge(
        district_matches,
        left_on="modern_rajon_eng",
        right_on="data_name",
        how="left",
    )

    matched_districts = district_counts[
        district_counts["boundary_name"].notna()
    ].copy()

    map_districts = adm2_region.merge(
        matched_districts,
        left_on=adm2_name_column,
        right_on="boundary_name",
        how="inner",
    )

    if map_districts.empty:
        st.warning(
            "Selle regiooni rajoonid ei leidnud "
            "piirifailis automaatset vastet."
        )
    else:
        map_districts = map_districts.reset_index(
            drop=True
        )

        map_districts["map_id"] = (
            map_districts.index.astype(str)
        )

        center_geometry = (
            map_districts.geometry
            .unary_union
            .centroid
        )

        figure = px.choropleth_map(
            map_districts,
            geojson=(
                map_districts.geometry
                .__geo_interface__
            ),
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
            center={
                "lat": center_geometry.y,
                "lon": center_geometry.x,
            },
            zoom=4.2,
            opacity=0.78,
            labels={
                "museaale": "Museaalide arv",
                "modern_rajon_eng": "Ingliskeelne nimi",
                "modern_region_est": "Regioon",
                "match_score": "Vaste skoor",
            },
            title=(
                "Rajoonid: "
                + region_display_name(
                    russian_objects,
                    selected_region,
                )
            ),
        )

        figure.update_layout(
            margin=dict(
                left=0,
                right=0,
                top=50,
                bottom=0,
            )
        )

        st.plotly_chart(
            figure,
            use_container_width=True,
        )

    st.dataframe(
        district_counts.rename(
            columns={
                "modern_rajon_est": "Rajoon",
                "modern_rajon_eng": "Ingliskeelne nimi",
                "museaale": "Museaalide arv",
                "boundary_name": "Piirifaili vaste",
                "match_score": "Vaste skoor",
            }
        )[
            [
                "Rajoon",
                "Ingliskeelne nimi",
                "Museaalide arv",
                "Piirifaili vaste",
                "Vaste skoor",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


# -------------------------------------------------------------------
# KONTROLLVAADE
# -------------------------------------------------------------------

def render_match_control(map_df: pd.DataFrame) -> None:
    st.subheader("Kaardile kaasamise ülevaade")

    column1, column2, column3 = st.columns(3)

    column1.metric(
        "Museaale filtris",
        map_df["object_id"].nunique(),
    )

    column2.metric(
        "Tuvastatud riigiga",
        map_df[
            map_df["country_iso3"].notna()
        ]["object_id"].nunique(),
    )

    if {
        "country",
        "modern_region_eng",
    }.issubset(map_df.columns):
        russian_region_count = map_df[
            (map_df["country"] == "Venemaa")
            & map_df["modern_region_eng"].notna()
        ]["object_id"].nunique()
    else:
        russian_region_count = 0

    column3.metric(
        "Venemaa regiooniga",
        russian_region_count,
    )

    bad_countries = (
        map_df[
            map_df["country_iso3"].isna()
        ]
        .groupby(
            "country",
            dropna=False,
        )
        .agg(
            museaale=("object_id", "nunique")
        )
        .reset_index()
        .sort_values(
            "museaale",
            ascending=False,
        )
    )

    st.markdown(
        "#### Kaardilt välja jäävad riigiväärtused"
    )

    if bad_countries.empty:
        st.success(
            "Kõik praeguse filtri riigiväärtused "
            "leidsid kaardil vaste."
        )
    else:
        st.dataframe(
            bad_countries.rename(
                columns={
                    "country": "Riigiväärtus",
                    "museaale": "Museaalide arv",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )


# -------------------------------------------------------------------
# PÕHIFUNKTSIOON, MIDA PÕHIÄPP VÄLJA KUTSUB
# -------------------------------------------------------------------

def render_map(filtered_df: pd.DataFrame) -> None:
    """
    Kuvab kaardivaate olemasoleva Streamliti rakenduse sees.

    Parameeter
    ----------
    filtered_df:
        Põhiäpis juba filtreeritud objektide tabel.
    """
    st.subheader("Soome-ugri museaalide päritolukaart")

    st.caption(
        "Kaart kasutab haldusüksuste polügoone, "
        "mitte museaalide latitude–longitude punkte. "
        "Arv näitab unikaalsete museaalide hulka."
    )

    if filtered_df is None or filtered_df.empty:
        st.info(
            "Praeguse filtriga ei ole kaardil "
            "kuvamiseks museaale."
        )
        return

    try:
        map_df = prepare_map_data(filtered_df)
    except Exception as error:
        st.error(
            "Kaardiandmete ettevalmistamine ebaõnnestus."
        )
        st.exception(error)
        return

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Riigid",
            "Venemaa regioonid",
            "Venemaa rajoonid",
            "Vastete kontroll",
        ]
    )

    with tab1:
        render_country_map(map_df)

    with tab2:
        render_russia_regions_map(map_df)

    with tab3:
        render_russia_districts_map(map_df)

    with tab4:
        render_match_control(map_df)    "Republic of Bashkortostan": ["Bashkortostan", "Respublika Bashkortostan"],
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
