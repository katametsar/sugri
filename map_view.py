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


def clean_muis_url(value):
    """Tagastab ainult kasutuskõlbliku MuISi veebiaadressi."""
    if pd.isna(value):
        return pd.NA

    value = str(value).strip()
    if not value or value.lower() in {
        "nan",
        "none",
        "<na>",
    }:
        return pd.NA

    # Mõnes tabelis võib URL olla HTML-lingi sees.
    match = re.search(r'https?://[^\s"\'<>]+', value)
    if match:
        return match.group(0).rstrip(".,;)")

    if value.startswith("//"):
        return "https:" + value

    if value.startswith("www."):
        return "https://" + value

    if value.startswith(("http://", "https://")):
        return value

    return pd.NA


def update_selection_from_chart(
    chart_key,
    lookup_key,
    target_key,
):
    """Kirjutab kaardil klõpsatud ala rippmenüü valikuks."""
    chart_state = st.session_state.get(chart_key)
    lookup = st.session_state.get(lookup_key, {})

    if not chart_state:
        return

    try:
        points = chart_state.selection.points
    except (AttributeError, KeyError, TypeError):
        try:
            points = chart_state["selection"]["points"]
        except (KeyError, TypeError):
            points = []

    if not points:
        return

    point = points[0]
    location = point.get("location")

    if location is None:
        point_index = point.get("point_index")
        if point_index is not None:
            location = str(point_index)

    location = str(location)
    selected_value = lookup.get(location)

    if selected_value is not None:
        st.session_state[target_key] = selected_value


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
        table["MuIS"] = table["MuIS"].map(clean_muis_url)
        column_config["MuIS"] = st.column_config.LinkColumn(
            "MuIS",
            display_text="Ava MuISis",
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
    st.session_state["map_country_lookup"] = dict(
        zip(
            counts["country_iso3"].astype(str),
            counts["country_clean"].astype(str),
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        key="map_country_chart",
        on_select=lambda: update_selection_from_chart(
            "map_country_chart",
            "map_country_lookup",
            "map_country",
        ),
        selection_mode="points",
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


def map_center_and_zoom(gdf, default_center=None, default_zoom=2.2):
    """Arvutab valitud polügoonide järgi kaardi keskpunkti ja ligikaudse suumi."""
    if gdf is None or gdf.empty:
        return default_center or {"lat": 61, "lon": 65}, default_zoom

    minx, miny, maxx, maxy = gdf.total_bounds
    center = {
        "lat": float((miny + maxy) / 2),
        "lon": float((minx + maxx) / 2),
    }
    span = max(float(maxx - minx), float(maxy - miny), 0.01)
    zoom = max(2.0, min(8.0, 7.5 - math.log(span, 2)))
    return center, zoom


def render_regions_map(df):
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
            "Venemaa kaardi jaoks puuduvad veerud: "
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
            "Praeguste filtritega ei ole Venemaa regioonide andmeid."
        )
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
        return

    region_options = (
        counts[["modern_region_est", "modern_region_eng"]]
        .drop_duplicates()
        .sort_values("modern_region_est")
    )
    est_to_eng = dict(
        zip(
            region_options["modern_region_est"],
            region_options["modern_region_eng"],
        )
    )

    if (
        "map_region_est" not in st.session_state
        or st.session_state["map_region_est"] not in est_to_eng
    ):
        st.session_state["map_region_est"] = next(iter(est_to_eng))

    selected_region_est = st.selectbox(
        "Vali regioon või klõpsa kaardil",
        list(est_to_eng.keys()),
        key="map_region_est",
    )
    selected_region_eng = est_to_eng[selected_region_est]

    map_df["map_id"] = map_df.index.astype(str)
    selected_geometry = map_df[
        map_df["modern_region_est"] == selected_region_est
    ]
    center, zoom = map_center_and_zoom(
        selected_geometry,
        default_center={"lat": 61, "lon": 65},
        default_zoom=2.2,
    )

    fig = px.choropleth_map(
        map_df,
        geojson=map_df.__geo_interface__,
        locations="map_id",
        featureidkey="properties.map_id",
        color="museaale",
        hover_name="modern_region_est",
        hover_data={"museaale": True, "map_id": False},
        labels={"museaale": "Museaalide arv"},
        map_style="carto-positron",
        center=center,
        zoom=zoom,
        opacity=0.75,
        title="Venemaa regioonid",
    )
    fig.update_layout(margin=dict(l=0, r=0, t=45, b=0))

    st.session_state["map_region_lookup"] = dict(
        zip(
            map_df["map_id"].astype(str),
            map_df["modern_region_est"].astype(str),
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        key="map_region_chart",
        on_select=lambda: update_selection_from_chart(
            "map_region_chart",
            "map_region_lookup",
            "map_region_est",
        ),
        selection_mode="points",
    )

    st.markdown(f"### {selected_region_est}: rajoonid")

    rajon_rows = rus[
        (rus["modern_region_eng"] == selected_region_eng)
        & rus["modern_rajon_eng"].notna()
        & rus["modern_rajon_est"].notna()
    ].copy()

    if rajon_rows.empty:
        st.info("Selle regiooni museaalidel ei ole rajooni määratud.")
        display_items(
            rus[rus["modern_region_eng"] == selected_region_eng],
            f"{selected_region_est}: museaalid",
        )
        return

    adm1_full, adm1_name, adm2_named = get_adm2_with_parent_regions()
    region_match = match_table(
        [selected_region_eng],
        adm1_full[adm1_name].dropna().astype(str).tolist(),
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

    district_counts = (
        rajon_rows.groupby(
            ["modern_rajon_est", "modern_rajon_eng"],
            as_index=False,
        )
        .agg(museaale=("object_id", "nunique"))
    )

    district_matches = match_table(
        district_counts["modern_rajon_eng"],
        adm2_region["adm2_boundary_name"]
        .dropna()
        .astype(str)
        .tolist(),
        threshold=62,
    )
    district_counts = district_counts.merge(
        district_matches,
        left_on="modern_rajon_eng",
        right_on="data_name",
        how="left",
    )

    district_map = adm2_region.merge(
        district_counts,
        left_on="adm2_boundary_name",
        right_on="boundary_name",
        how="inner",
    ).reset_index(drop=True)

    if district_map.empty:
        st.warning(
            "Selle regiooni rajoonid ei leidnud piirifailis vastet."
        )
        display_items(
            rajon_rows,
            f"{selected_region_est}: museaalid",
        )
        return

    district_options = (
        district_counts[
            ["modern_rajon_est", "modern_rajon_eng"]
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

    district_key = "map_drilldown_district_est"
    if (
        district_key not in st.session_state
        or st.session_state[district_key] not in est_to_eng_district
    ):
        st.session_state[district_key] = next(
            iter(est_to_eng_district)
        )

    selected_district_est = st.selectbox(
        "Vali rajoon või klõpsa rajoonikaardil",
        list(est_to_eng_district.keys()),
        key=district_key,
    )
    selected_district_eng = est_to_eng_district[
        selected_district_est
    ]

    district_map["map_id"] = district_map.index.astype(str)
    selected_district_geometry = district_map[
        district_map["modern_rajon_est"]
        == selected_district_est
    ]
    district_center, district_zoom = map_center_and_zoom(
        selected_district_geometry,
        default_center=center,
        default_zoom=max(zoom, 4.0),
    )

    district_fig = px.choropleth_map(
        district_map,
        geojson=district_map.__geo_interface__,
        locations="map_id",
        featureidkey="properties.map_id",
        color="museaale",
        hover_name="modern_rajon_est",
        hover_data={"museaale": True, "map_id": False},
        labels={"museaale": "Museaalide arv"},
        map_style="carto-positron",
        center=district_center,
        zoom=district_zoom,
        opacity=0.78,
        title=f"{selected_region_est}: rajoonid",
    )
    district_fig.update_layout(
        margin=dict(l=0, r=0, t=45, b=0)
    )

    st.session_state["map_drilldown_district_lookup"] = dict(
        zip(
            district_map["map_id"].astype(str),
            district_map["modern_rajon_est"].astype(str),
        )
    )

    st.plotly_chart(
        district_fig,
        use_container_width=True,
        key="map_drilldown_district_chart",
        on_select=lambda: update_selection_from_chart(
            "map_drilldown_district_chart",
            "map_drilldown_district_lookup",
            district_key,
        ),
        selection_mode="points",
    )

    district_items = rajon_rows[
        rajon_rows["modern_rajon_eng"]
        == selected_district_eng
    ].copy()

    display_items(
        district_items,
        (
            f"{selected_region_est}, "
            f"{selected_district_est}: museaalid"
        ),
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
    st.session_state["map_district_lookup"] = dict(
        zip(
            map_df["map_id"].astype(str),
            map_df["modern_rajon_est"].astype(str),
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        key="map_district_chart",
        on_select=lambda: update_selection_from_chart(
            "map_district_chart",
            "map_district_lookup",
            "map_district_est",
        ),
        selection_mode="points",
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
        "selle piirkonna museaale. Piirkonna saab valida "
        "ka otse kaardil klõpsates."
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

    tab1, tab2 = st.tabs(
        [
            "Riigid",
            "Venemaa: regioonid ja rajoonid",
        ]
    )

    with tab1:
        render_country_map(df)

    with tab2:
        render_regions_map(df)
