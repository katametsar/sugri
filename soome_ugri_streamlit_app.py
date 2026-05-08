
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Soome-ugri museaalide explorer",
    page_icon="🧭",
    layout="wide",
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "app_ready_tables"


# ─────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────

@st.cache_data
def load_data():
    objects = pd.read_csv(DATA_DIR / "objects_app.csv")
    materials = pd.read_csv(DATA_DIR / "materials_long.csv")
    collectors = pd.read_csv(DATA_DIR / "collectors_long.csv")
    places = pd.read_csv(DATA_DIR / "places_long_clean.csv")
    best_place = pd.read_csv(DATA_DIR / "object_best_place.csv")

    # Standardize IDs
    for df in [objects, materials, collectors, places, best_place]:
        if "object_id" in df.columns:
            df["object_id"] = df["object_id"].astype(str)

    # Numeric year
    if "year" in objects.columns:
        objects["year"] = pd.to_numeric(objects["year"], errors="coerce")

    # Add object-level helper columns from long tables
    if not materials.empty and "material" in materials.columns:
        mat_join = (
            materials.dropna(subset=["material"])
            .groupby("object_id")["material"]
            .apply(lambda s: ", ".join(sorted(set(s.astype(str)))))
            .reset_index(name="materials_joined")
        )
        objects = objects.merge(mat_join, on="object_id", how="left")

    if not materials.empty and "material_category" in materials.columns:
        mat_cat_join = (
            materials.dropna(subset=["material_category"])
            .groupby("object_id")["material_category"]
            .apply(lambda s: ", ".join(sorted(set(s.astype(str)))))
            .reset_index(name="material_categories_joined")
        )
        objects = objects.merge(mat_cat_join, on="object_id", how="left")

    collector_col = "collector_normalized" if "collector_normalized" in collectors.columns else "collector"
    if not collectors.empty and collector_col in collectors.columns:
        col_join = (
            collectors.dropna(subset=[collector_col])
            .groupby("object_id")[collector_col]
            .apply(lambda s: ", ".join(sorted(set(s.astype(str)))))
            .reset_index(name="collectors_joined")
        )
        objects = objects.merge(col_join, on="object_id", how="left")

    if not best_place.empty:
        keep = [
            c for c in [
                "object_id", "best_place", "place_precision", "country",
                "region", "district", "rajon", "village", "lat", "lon",
                "has_coordinates"
            ]
            if c in best_place.columns
        ]
        objects = objects.merge(best_place[keep], on="object_id", how="left")

    return objects, materials, collectors, places, best_place


objects, materials, collectors, places, best_place = load_data()


# ─────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────

def unique_clean(series):
    if series is None:
        return []
    return sorted(
        [
            str(x)
            for x in series.dropna().unique()
            if str(x).strip() and str(x).strip().lower() != "nan"
        ]
    )


def filter_by_long_table(df, long_df, value_col, selected_values):
    if not selected_values or long_df.empty or value_col not in long_df.columns:
        return df

    ids = long_df[long_df[value_col].isin(selected_values)]["object_id"].astype(str).unique()
    return df[df["object_id"].isin(ids)]


def safe_contains(series, query):
    return series.fillna("").astype(str).str.contains(query, case=False, na=False)


# ─────────────────────────────────────────────────────────
# Sidebar filters
# ─────────────────────────────────────────────────────────

st.sidebar.title("Filtrid")

df = objects.copy()

search = st.sidebar.text_input("Otsi tekstist", placeholder="nt vöö, komi, Art Leete...")

if search:
    mask = pd.Series(False, index=df.index)
    for col in [
        "title", "description", "ethnic_group", "museal_number",
        "materials_joined", "collectors_joined", "best_place",
        "places_not_cleaned"
    ]:
        if col in df.columns:
            mask = mask | safe_contains(df[col], search)
    df = df[mask]

if "ethnic_group" in df.columns:
    ethnic_options = unique_clean(objects["ethnic_group"])
    selected_ethnic = st.sidebar.multiselect("Rahvarühm", ethnic_options)
    if selected_ethnic:
        df = df[df["ethnic_group"].isin(selected_ethnic)]

if "year" in objects.columns and objects["year"].notna().any():
    min_year = int(objects["year"].dropna().min())
    max_year = int(objects["year"].dropna().max())
    year_range = st.sidebar.slider(
        "Aasta",
        min_year,
        max_year,
        (min_year, max_year),
    )
    df = df[
        df["year"].isna()
        | df["year"].between(year_range[0], year_range[1])
    ]

if "material_category" in materials.columns:
    mat_cat_options = unique_clean(materials["material_category"])
    selected_mat_cat = st.sidebar.multiselect("Materjalikategooria", mat_cat_options)
    df = filter_by_long_table(df, materials, "material_category", selected_mat_cat)

if "material" in materials.columns:
    mat_options = unique_clean(materials["material"])
    selected_materials = st.sidebar.multiselect("Materjal", mat_options)
    df = filter_by_long_table(df, materials, "material", selected_materials)

collector_filter_col = "collector_normalized" if "collector_normalized" in collectors.columns else "collector"
if collector_filter_col in collectors.columns:
    collector_options = unique_clean(collectors[collector_filter_col])
    selected_collectors = st.sidebar.multiselect("Koguja", collector_options)
    df = filter_by_long_table(df, collectors, collector_filter_col, selected_collectors)

for label, col in [
    ("Riik", "country"),
    ("Regioon", "region"),
    ("Rajoon", "rajon"),
    ("Küla", "village"),
]:
    if col in objects.columns:
        opts = unique_clean(objects[col])
        selected = st.sidebar.multiselect(label, opts)
        if selected:
            df = df[df[col].isin(selected)]


# ─────────────────────────────────────────────────────────
# Header and KPIs
# ─────────────────────────────────────────────────────────

st.title("Soome-ugri museaalide explorer")
st.caption(
    "Esimene Streamliti prototüüp app_ready tabelite põhjal. "
    "Kaardiloogika on teadlikult välja jäetud, kuni kohainfo on stabiilsem."
)

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

kpi1.metric("Museaale filtris", f"{len(df):,}".replace(",", " "))
kpi2.metric("Museaale kokku", f"{len(objects):,}".replace(",", " "))

if "ethnic_group" in df.columns:
    kpi3.metric("Rahvarühmi", df["ethnic_group"].dropna().nunique())
else:
    kpi3.metric("Rahvarühmi", "—")

if "material" in materials.columns:
    mat_ids = set(df["object_id"])
    kpi4.metric(
        "Materjaliga museaale",
        materials[materials["object_id"].isin(mat_ids)]["object_id"].nunique()
    )
else:
    kpi4.metric("Materjaliga museaale", "—")

if "best_place" in df.columns:
    kpi5.metric("Kohainfoga museaale", df["best_place"].dropna().nunique())
else:
    kpi5.metric("Kohainfoga museaale", "—")


# ─────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Ülevaade",
    "Rahvarühmad",
    "Materjalid",
    "Kogujad",
    "Kohad",
    "Andmetabel",
])


with tab1:
    st.subheader("Ülevaade")

    col1, col2 = st.columns(2)

    with col1:
        if "year" in df.columns and df["year"].notna().any():
            year_counts = (
                df.dropna(subset=["year"])
                .assign(year=lambda x: x["year"].astype(int))
                .groupby("year")
                .size()
                .reset_index(name="count")
                .sort_values("year")
            )
            fig = px.line(
                year_counts,
                x="year",
                y="count",
                markers=True,
                title="Museaalid aastate lõikes",
                labels={"year": "Aasta", "count": "Museaalide arv"},
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aastaandmeid ei leitud.")

    with col2:
        if "title" in df.columns:
            top_titles = df["title"].dropna().value_counts().head(15).reset_index()
            top_titles.columns = ["title", "count"]
            fig = px.bar(
                top_titles,
                x="count",
                y="title",
                orientation="h",
                title="Levinumad nimetused",
                labels={"count": "Arv", "title": "Nimetus"},
            )
            fig.update_layout(yaxis={"autorange": "reversed"})
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Näited filtrisse jäänud museaalidest")
    preview_cols = [
        c for c in [
            "object_id", "museal_number", "title", "ethnic_group",
            "year", "materials_joined", "collectors_joined", "best_place"
        ]
        if c in df.columns
    ]
    st.dataframe(df[preview_cols].head(100), use_container_width=True, hide_index=True)


with tab2:
    st.subheader("Rahvarühmad")

    if "ethnic_group" in df.columns:
        top_ethnic = df["ethnic_group"].dropna().value_counts().head(30).reset_index()
        top_ethnic.columns = ["ethnic_group", "count"]

        fig = px.bar(
            top_ethnic,
            x="count",
            y="ethnic_group",
            orientation="h",
            title="Rahvarühmade jaotus",
            labels={"count": "Museaalide arv", "ethnic_group": "Rahvarühm"},
        )
        fig.update_layout(yaxis={"autorange": "reversed"})
        st.plotly_chart(fig, use_container_width=True)

        selected_group = st.selectbox(
            "Vaata ühe rahvarühma museaale",
            [""] + top_ethnic["ethnic_group"].tolist(),
        )

        if selected_group:
            group_df = df[df["ethnic_group"] == selected_group]
            st.markdown(f"Leitud **{len(group_df)}** museaali rahvarühmaga **{selected_group}**.")
            cols = [
                c for c in [
                    "object_id", "museal_number", "title", "year",
                    "materials_joined", "collectors_joined", "best_place",
                    "object_url", "image_url"
                ]
                if c in group_df.columns
            ]
            st.dataframe(group_df[cols].head(300), use_container_width=True, hide_index=True)
    else:
        st.info("Rahvarühma veergu ei leitud.")


with tab3:
    st.subheader("Materjalid")

    ids = set(df["object_id"])
    mat_filtered = materials[materials["object_id"].isin(ids)].copy()

    col1, col2 = st.columns(2)

    with col1:
        if "material_category" in mat_filtered.columns:
            cat_counts = mat_filtered["material_category"].dropna().value_counts().head(20).reset_index()
            cat_counts.columns = ["material_category", "count"]
            fig = px.bar(
                cat_counts,
                x="count",
                y="material_category",
                orientation="h",
                title="Materjalikategooriad",
                labels={"count": "Esinemiste arv", "material_category": "Kategooria"},
            )
            fig.update_layout(yaxis={"autorange": "reversed"})
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if "material" in mat_filtered.columns:
            material_counts = mat_filtered["material"].dropna().value_counts().head(25).reset_index()
            material_counts.columns = ["material", "count"]
            fig = px.bar(
                material_counts,
                x="count",
                y="material",
                orientation="h",
                title="Levinumad materjalid",
                labels={"count": "Esinemiste arv", "material": "Materjal"},
            )
            fig.update_layout(yaxis={"autorange": "reversed"})
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Materjalide tabel")
    st.dataframe(mat_filtered.head(500), use_container_width=True, hide_index=True)


with tab4:
    st.subheader("Kogujad")

    ids = set(df["object_id"])
    collectors_filtered = collectors[collectors["object_id"].isin(ids)].copy()
    collector_col = "collector_normalized" if "collector_normalized" in collectors_filtered.columns else "collector"

    if collector_col in collectors_filtered.columns:
        top_collectors = collectors_filtered[collector_col].dropna().value_counts().head(30).reset_index()
        top_collectors.columns = ["collector", "count"]

        fig = px.bar(
            top_collectors,
            x="count",
            y="collector",
            orientation="h",
            title="Top kogujad",
            labels={"count": "Esinemiste arv", "collector": "Koguja"},
        )
        fig.update_layout(yaxis={"autorange": "reversed"})
        st.plotly_chart(fig, use_container_width=True)

        selected_collector = st.selectbox(
            "Vaata ühe koguja museaale",
            [""] + top_collectors["collector"].tolist(),
        )

        if selected_collector:
            collector_ids = collectors_filtered[
                collectors_filtered[collector_col] == selected_collector
            ]["object_id"].unique()
            collector_df = df[df["object_id"].isin(collector_ids)]
            st.markdown(f"Leitud **{len(collector_df)}** museaali kogujaga **{selected_collector}**.")
            cols = [
                c for c in [
                    "object_id", "museal_number", "title", "ethnic_group",
                    "year", "materials_joined", "best_place", "object_url"
                ]
                if c in collector_df.columns
            ]
            st.dataframe(collector_df[cols].head(300), use_container_width=True, hide_index=True)
    else:
        st.info("Koguja veergu ei leitud.")


with tab5:
    st.subheader("Kohad")

    ids = set(df["object_id"])
    place_filtered = best_place[best_place["object_id"].isin(ids)].copy()

    c1, c2 = st.columns(2)

    with c1:
        if "country" in place_filtered.columns:
            country_counts = place_filtered["country"].dropna().value_counts().head(20).reset_index()
            country_counts.columns = ["country", "count"]
            fig = px.bar(
                country_counts,
                x="count",
                y="country",
                orientation="h",
                title="Riigid",
                labels={"count": "Museaalide arv", "country": "Riik"},
            )
            fig.update_layout(yaxis={"autorange": "reversed"})
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if "place_precision" in place_filtered.columns:
            precision_counts = place_filtered["place_precision"].dropna().value_counts().reset_index()
            precision_counts.columns = ["place_precision", "count"]
            fig = px.bar(
                precision_counts,
                x="place_precision",
                y="count",
                title="Kohainfo täpsus",
                labels={"place_precision": "Täpsus", "count": "Museaalide arv"},
            )
            st.plotly_chart(fig, use_container_width=True)

    if "region" in place_filtered.columns:
        region_counts = place_filtered["region"].dropna().value_counts().head(30).reset_index()
        region_counts.columns = ["region", "count"]
        fig = px.bar(
            region_counts,
            x="count",
            y="region",
            orientation="h",
            title="Top regioonid",
            labels={"count": "Museaalide arv", "region": "Regioon"},
        )
        fig.update_layout(yaxis={"autorange": "reversed"})
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Parim koht museaali kohta")
    keep_cols = [
        c for c in [
            "object_id", "best_place", "place_precision", "country",
            "region", "district", "rajon", "village", "lat", "lon",
            "has_coordinates", "koht"
        ]
        if c in place_filtered.columns
    ]
    st.dataframe(place_filtered[keep_cols].head(500), use_container_width=True, hide_index=True)

    st.info(
        "Kaarti siin prototüübis veel ei kuvata. Lat/lon on kaasas, "
        "aga enne kaardistamist tuleks koordinaadid ja kohatasemed eraldi üle kontrollida."
    )


with tab6:
    st.subheader("Andmetabel")

    default_cols = [
        c for c in [
            "object_id", "museal_number", "title", "ethnic_group",
            "year", "materials_joined", "collectors_joined",
            "best_place", "country", "region", "rajon", "village",
            "object_url", "image_url"
        ]
        if c in df.columns
    ]

    selected_cols = st.multiselect(
        "Vali kuvatavad veerud",
        options=list(df.columns),
        default=default_cols,
    )

    st.markdown(f"Näidatakse **{len(df):,}** rida".replace(",", " "))

    if selected_cols:
        st.dataframe(df[selected_cols].head(1000), use_container_width=True, hide_index=True)

        csv = df[selected_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Lae filtreeritud andmed CSV-na alla",
            data=csv,
            file_name="soome_ugri_filtreeritud.csv",
            mime="text/csv",
        )
    else:
        st.info("Vali vähemalt üks veerg.")
