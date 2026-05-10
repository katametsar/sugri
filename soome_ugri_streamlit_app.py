
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# ─────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Soome-ugri museaalide explorer",
    page_icon="🧭",
    layout="wide",
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "app_ready_tables"


# ─────────────────────────────────────────────────────────
# Light visual styling
# ─────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1350px;
    }

    .hero-box {
        background: linear-gradient(135deg, #f5efe6 0%, #eef4ef 100%);
        padding: 1.8rem 2rem;
        border-radius: 22px;
        margin-bottom: 1.2rem;
        border: 1px solid rgba(80, 70, 50, 0.12);
    }

    .hero-title {
        font-size: 2.35rem;
        font-weight: 760;
        margin-bottom: 0.35rem;
        color: #2f3a2f;
    }

    .hero-subtitle {
        font-size: 1.02rem;
        color: #5e665e;
        max-width: 850px;
        line-height: 1.5;
    }

    .section-note {
        background: #faf7f0;
        border-left: 4px solid #b79b65;
        padding: 0.8rem 1rem;
        border-radius: 12px;
        color: #4c4538;
    }

    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid rgba(49, 58, 49, 0.10);
        padding: 1rem;
        border-radius: 18px;
        box-shadow: 0 3px 14px rgba(0,0,0,0.04);
    }

    .small-muted {
        color: #6b6f6b;
        font-size: 0.9rem;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.4rem;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 999px;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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

    # IDs as strings
    for table in [objects, materials, collectors, places, best_place]:
        if "object_id" in table.columns:
            table["object_id"] = table["object_id"].astype(str)

    # Year as numeric
    if "year" in objects.columns:
        objects["year"] = pd.to_numeric(objects["year"], errors="coerce")

    # Clean text columns
    for table in [objects, materials, collectors, places, best_place]:
        for col in table.select_dtypes(include="object").columns:
            table[col] = (
                table[col]
                .astype(str)
                .str.strip()
                .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "NaN": pd.NA})
            )

    # Long-table joins for easier display/search
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
                "has_coordinates", "koht"
            ]
            if c in best_place.columns
        ]
        objects = objects.merge(best_place[keep], on="object_id", how="left")

    return objects, materials, collectors, places, best_place


objects, materials, collectors, places, best_place = load_data()


# ─────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────

def looks_like_bad_place_value(value):
    """
    Filters out values that are probably codes accidentally sitting in place columns.
    Example: 52367, 37, 911 etc.
    """
    if pd.isna(value):
        return True

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "teadmata"}:
        return True

    # pure numeric values are probably codes, not place names
    normalized = text.replace(".", "").replace(",", "").replace("-", "").strip()
    if normalized.isdigit():
        return True

    # very short values are suspicious as locations, except normal abbreviations are rare here
    if len(text) <= 1:
        return True

    return False


def unique_clean(series, limit=None):
    if series is None:
        return []

    values = []
    for x in series.dropna().unique():
        if not looks_like_bad_place_value(x):
            values.append(str(x).strip())

    values = sorted(set(values), key=lambda x: x.lower())
    if limit:
        values = values[:limit]
    return values


def safe_contains(series, query):
    return series.fillna("").astype(str).str.contains(query, case=False, na=False, regex=False)


def ids_for_long_filter(long_df, value_col, selected_values):
    if not selected_values or long_df.empty or value_col not in long_df.columns:
        return None
    return set(long_df[long_df[value_col].isin(selected_values)]["object_id"].astype(str))


def apply_all_filters(
    source_df,
    search_text=None,
    year_range=None,
    selected_ethnic=None,
    selected_material_categories=None,
    selected_materials=None,
    selected_collectors=None,
    selected_country=None,
    selected_region=None,
    selected_rajon=None,
    selected_village=None,
    exclude=None,
):
    """
    Applies all active filters. `exclude` lets each multiselect calculate its options
    from all other filters, so filters update each other in any order.
    """
    exclude = exclude or set()
    filtered = source_df.copy()

    if "search" not in exclude and search_text:
        mask = pd.Series(False, index=filtered.index)
        for col in [
            "title", "description", "ethnic_group", "museal_number",
            "materials_joined", "material_categories_joined", "collectors_joined",
            "best_place", "country", "region", "rajon", "village",
            "places_not_cleaned", "comments", "legend", "text_on_object"
        ]:
            if col in filtered.columns:
                mask = mask | safe_contains(filtered[col], search_text)
        filtered = filtered[mask]

    if "year" not in exclude and year_range and "year" in filtered.columns:
        filtered = filtered[
            filtered["year"].isna()
            | filtered["year"].between(year_range[0], year_range[1])
        ]

    if "ethnic_group" not in exclude and selected_ethnic and "ethnic_group" in filtered.columns:
        filtered = filtered[filtered["ethnic_group"].isin(selected_ethnic)]

    if "material_category" not in exclude and selected_material_categories:
        ids = ids_for_long_filter(materials, "material_category", selected_material_categories)
        if ids is not None:
            filtered = filtered[filtered["object_id"].isin(ids)]

    if "material" not in exclude and selected_materials:
        ids = ids_for_long_filter(materials, "material", selected_materials)
        if ids is not None:
            filtered = filtered[filtered["object_id"].isin(ids)]

    collector_col = "collector_normalized" if "collector_normalized" in collectors.columns else "collector"
    if "collector" not in exclude and selected_collectors and collector_col in collectors.columns:
        ids = ids_for_long_filter(collectors, collector_col, selected_collectors)
        if ids is not None:
            filtered = filtered[filtered["object_id"].isin(ids)]

    place_filters = [
        ("country", selected_country),
        ("region", selected_region),
        ("rajon", selected_rajon),
        ("village", selected_village),
    ]

    for col, selected in place_filters:
        if col not in exclude and selected and col in filtered.columns:
            filtered = filtered[filtered[col].isin(selected)]

    return filtered


def clean_selection(key, valid_options):
    """Remove stale selections after another filter makes them impossible."""
    if key in st.session_state:
        st.session_state[key] = [x for x in st.session_state[key] if x in valid_options]


def option_df_for(exclude_name):
    return apply_all_filters(
        objects,
        search_text=st.session_state.get("search_text", ""),
        year_range=st.session_state.get("year_range", None),
        selected_ethnic=st.session_state.get("ethnic_group", []),
        selected_material_categories=st.session_state.get("material_category", []),
        selected_materials=st.session_state.get("material", []),
        selected_collectors=st.session_state.get("collector", []),
        selected_country=st.session_state.get("country", []),
        selected_region=st.session_state.get("region", []),
        selected_rajon=st.session_state.get("rajon", []),
        selected_village=st.session_state.get("village", []),
        exclude={exclude_name},
    )


def long_options_for(long_df, value_col, base_df):
    if long_df.empty or value_col not in long_df.columns:
        return []
    ids = set(base_df["object_id"].astype(str))
    subset = long_df[long_df["object_id"].isin(ids)]
    return unique_clean(subset[value_col])


def readable_count(n):
    return f"{n:,}".replace(",", " ")


# ─────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────

st.markdown(
    """
    <div class="hero-box">
        <div class="hero-title">Soome-ugri museaalide explorer</div>
        <div class="hero-subtitle">
            Prototüüp ERMi/MuISi soome-ugri kogude uurimiseks: rahvarühmad, kogujad,
            materjalid, ajastus ja kohainfo. Kaardivaade tuleb hiljem, kui asukohad
            on eraldi puhastatud ja kontrollitud.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────
# Sidebar filters — interdependent
# ─────────────────────────────────────────────────────────

st.sidebar.title("Filtrid")
st.sidebar.caption("Valikud uuenevad üksteise põhjal. Võimatud kombinatsioonid kaovad valikust.")

st.sidebar.text_input(
    "Otsi tekstist",
    placeholder="nt tagapõll, neenets, Tiia Pedorelli...",
    key="search_text",
    help="Otsib nimetuse, kirjelduse, rahvarühma, museaalinumbri, materjali, koguja ja kohainfo seest.",
)

# Year range
if "year" in objects.columns and objects["year"].notna().any():
    min_year = int(objects["year"].dropna().min())
    max_year = int(objects["year"].dropna().max())

    if "year_range" not in st.session_state:
        st.session_state["year_range"] = (min_year, max_year)

    st.sidebar.slider(
        "Aasta",
        min_year,
        max_year,
        key="year_range",
    )

# Ethnic group
if "ethnic_group" in objects.columns:
    opts = unique_clean(option_df_for("ethnic_group")["ethnic_group"])
    clean_selection("ethnic_group", opts)
    st.sidebar.multiselect("Rahvarühm", opts, key="ethnic_group")

# Material category
if "material_category" in materials.columns:
    opts = long_options_for(materials, "material_category", option_df_for("material_category"))
    clean_selection("material_category", opts)
    st.sidebar.multiselect("Materjalikategooria", opts, key="material_category")

# Material
if "material" in materials.columns:
    opts = long_options_for(materials, "material", option_df_for("material"))
    clean_selection("material", opts)
    st.sidebar.multiselect("Materjal", opts, key="material")

# Collector
collector_filter_col = "collector_normalized" if "collector_normalized" in collectors.columns else "collector"
if collector_filter_col in collectors.columns:
    opts = long_options_for(collectors, collector_filter_col, option_df_for("collector"))
    clean_selection("collector", opts)
    st.sidebar.multiselect("Koguja", opts, key="collector")

# Place filters
for label, col, key in [
    ("Riik", "country", "country"),
    ("Regioon", "region", "region"),
    ("Rajoon", "rajon", "rajon"),
    ("Küla", "village", "village"),
]:
    if col in objects.columns:
        opts = unique_clean(option_df_for(key)[col])
        clean_selection(key, opts)
        st.sidebar.multiselect(label, opts, key=key)

if st.sidebar.button("Tühjenda filtrid"):
    for key in [
        "search_text", "ethnic_group", "material_category", "material",
        "collector", "country", "region", "rajon", "village"
    ]:
        if key in st.session_state:
            if key == "search_text":
                st.session_state[key] = ""
            else:
                st.session_state[key] = []
    if "year_range" in st.session_state and "year" in objects.columns:
        st.session_state["year_range"] = (
            int(objects["year"].dropna().min()),
            int(objects["year"].dropna().max()),
        )
    st.rerun()


# Final filtered dataframe
df = apply_all_filters(
    objects,
    search_text=st.session_state.get("search_text", ""),
    year_range=st.session_state.get("year_range", None),
    selected_ethnic=st.session_state.get("ethnic_group", []),
    selected_material_categories=st.session_state.get("material_category", []),
    selected_materials=st.session_state.get("material", []),
    selected_collectors=st.session_state.get("collector", []),
    selected_country=st.session_state.get("country", []),
    selected_region=st.session_state.get("region", []),
    selected_rajon=st.session_state.get("rajon", []),
    selected_village=st.session_state.get("village", []),
)


# ─────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

kpi1.metric("Museaale filtris", readable_count(len(df)))
kpi2.metric("Museaale kokku", readable_count(len(objects)))

if "ethnic_group" in df.columns:
    kpi3.metric("Rahvarühmi filtris", df["ethnic_group"].dropna().nunique())
else:
    kpi3.metric("Rahvarühmi filtris", "—")

mat_ids = set(df["object_id"].astype(str))
if "material" in materials.columns:
    kpi4.metric(
        "Materjaliga museaale",
        readable_count(materials[materials["object_id"].isin(mat_ids)]["object_id"].nunique())
    )
else:
    kpi4.metric("Materjaliga museaale", "—")

if "best_place" in df.columns:
    # This is NOT objects with place info; it is distinct place names in the filtered set.
    kpi5.metric("Eri asukohti filtris", readable_count(df["best_place"].dropna().nunique()))
else:
    kpi5.metric("Eri asukohti filtris", "—")

if len(df) == 0:
    st.warning("Ühtegi museaali ei vasta praegusele filtrikombinatsioonile. Eemalda mõni filter.")


# ─────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Ülevaade",
    "Rahvarühmad",
    "Materjalid",
    "Kogujad",
    "Kohad",
    "Galerii / lingid",
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
            fig.update_layout(height=420)
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
            fig.update_layout(yaxis={"autorange": "reversed"}, height=420)
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
        fig.update_layout(yaxis={"autorange": "reversed"}, height=650)
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

    ids = set(df["object_id"].astype(str))
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
            fig.update_layout(yaxis={"autorange": "reversed"}, height=480)
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
            fig.update_layout(yaxis={"autorange": "reversed"}, height=480)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Materjalide tabel")
    st.dataframe(mat_filtered.head(500), use_container_width=True, hide_index=True)


with tab4:
    st.subheader("Kogujad")

    ids = set(df["object_id"].astype(str))
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
        fig.update_layout(yaxis={"autorange": "reversed"}, height=650)
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

    place_filtered = df.copy()

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
            fig.update_layout(yaxis={"autorange": "reversed"}, height=420)
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
            fig.update_layout(height=420)
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
        fig.update_layout(yaxis={"autorange": "reversed"}, height=620)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Üks parim koht museaali kohta")
    keep_cols = [
        c for c in [
            "object_id", "museal_number", "title", "ethnic_group",
            "best_place", "place_precision", "country",
            "region", "district", "rajon", "village", "lat", "lon",
            "has_coordinates", "koht"
        ]
        if c in place_filtered.columns
    ]
    st.dataframe(place_filtered[keep_cols].head(500), use_container_width=True, hide_index=True)

    st.markdown(
        """
        <div class="section-note">
        Kaarti siin versioonis veel ei kuvata. Kohainfo on tekstina juba kasutatav,
        aga koordinaadid ja kohatasemed tuleks enne kaardivaadet eraldi üle kontrollida.
        </div>
        """,
        unsafe_allow_html=True,
    )


with tab6:
    st.subheader("Galerii / lingid")

    st.markdown(
        """
        <div class="section-note">
        MuISi pildilingid ei pruugi alati olla otse pildifailid, vaid võivad olla media-list lehed.
        Seetõttu on siin esmalt turvaline lingivaade. Kui hiljem tekivad otsepildid,
        saab siia lisada päris pildikaardid.
        </div>
        """,
        unsafe_allow_html=True,
    )

    gallery_cols = [
        c for c in [
            "museal_number", "title", "ethnic_group", "year",
            "materials_joined", "collectors_joined", "best_place",
            "object_url", "image_url"
        ]
        if c in df.columns
    ]

    gallery_df = df[gallery_cols].head(200).copy()
    st.dataframe(
        gallery_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "object_url": st.column_config.LinkColumn("Museaal MuISis"),
            "image_url": st.column_config.LinkColumn("Pildid / media"),
        },
    )


with tab7:
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

    st.markdown(f"Näidatakse **{readable_count(len(df))}** rida")

    if selected_cols:
        st.dataframe(
            df[selected_cols].head(1000),
            use_container_width=True,
            hide_index=True,
            column_config={
                "object_url": st.column_config.LinkColumn("Museaal MuISis"),
                "image_url": st.column_config.LinkColumn("Pildid / media"),
            },
        )

        csv = df[selected_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Lae filtreeritud andmed CSV-na alla",
            data=csv,
            file_name="soome_ugri_filtreeritud.csv",
            mime="text/csv",
        )
    else:
        st.info("Vali vähemalt üks veerg.")
