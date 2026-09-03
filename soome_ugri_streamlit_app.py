from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from map_view import render_map
from collector_network import render_collectors_network


# ─────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Soome-ugri museaalid",
    page_icon="🧭",
    layout="wide",
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "app_ready_tables"


# ─────────────────────────────────────────────────────────
# Minimal styling
# ─────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 1.5rem;
        max-width: 1350px;
    }
    h1 { margin-bottom: 0.2rem; }
    .intro-text {
        color: #555;
        font-size: 1.02rem;
        line-height: 1.45;
        margin-bottom: 1rem;
    }
    div[data-testid="stMetric"] {
        border: 1px solid rgba(0,0,0,0.08);
        padding: 0.8rem;
        border-radius: 12px;
        background: #ffffff;
    }
    .note-box {
        border-left: 4px solid #b7a27a;
        background: #faf8f3;
        padding: 0.8rem 1rem;
        border-radius: 8px;
        color: #4a4338;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def normalize_object_id(series):
    """Normaliseeri object_id ühtseks stringiks (nt 123 ja 123.0 -> "123")."""
    values = series.astype("string").str.strip()
    return values.str.replace(r"^(\d+)\.0$", r"\1", regex=True)


# ─────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    objects = pd.read_csv(DATA_DIR / "objects_app.csv")
    materials = pd.read_csv(DATA_DIR / "materials_long.csv")
    collectors = pd.read_csv(DATA_DIR / "collectors_long.csv")

    best_place = pd.read_csv(
        DATA_DIR / "object_best_place_modern_regions_raions.csv"
    )

    for table in [objects, materials, collectors, best_place]:
        if "object_id" in table.columns:
            table["object_id"] = normalize_object_id(table["object_id"])

    if "year" in objects.columns:
        objects["year"] = pd.to_numeric(
            objects["year"],
            errors="coerce",
        )

    for table in [objects, materials, collectors, best_place]:
        for col in table.select_dtypes(include="object").columns:
            table[col] = (
                table[col]
                .astype(str)
                .str.strip()
                .replace(
                    {
                        "": pd.NA,
                        "nan": pd.NA,
                        "None": pd.NA,
                        "NaN": pd.NA,
                    }
                )
            )

    if not materials.empty and "material" in materials.columns:
        mat_join = (
            materials.dropna(subset=["material"])
            .groupby("object_id")["material"]
            .apply(
                lambda s: ", ".join(
                    sorted(set(s.astype(str)))
                )
            )
            .reset_index(name="materials_joined")
        )

        objects = objects.merge(
            mat_join,
            on="object_id",
            how="left",
        )

    if (
        not materials.empty
        and "material_category" in materials.columns
    ):
        mat_cat_join = (
            materials.dropna(subset=["material_category"])
            .groupby("object_id")["material_category"]
            .apply(
                lambda s: ", ".join(
                    sorted(set(s.astype(str)))
                )
            )
            .reset_index(
                name="material_categories_joined"
            )
        )

        objects = objects.merge(
            mat_cat_join,
            on="object_id",
            how="left",
        )

    collector_col = (
        "collector_normalized"
        if "collector_normalized" in collectors.columns
        else "collector"
    )

    if (
        not collectors.empty
        and collector_col in collectors.columns
    ):
        col_join = (
            collectors.dropna(subset=[collector_col])
            .groupby("object_id")[collector_col]
            .apply(
                lambda s: ", ".join(
                    sorted(set(s.astype(str)))
                )
            )
            .reset_index(name="collectors_joined")
        )

        objects = objects.merge(
            col_join,
            on="object_id",
            how="left",
        )

    if not best_place.empty:
        if "object_id" in best_place.columns:
            duplicate_ids = best_place["object_id"].duplicated(keep=False)
            if duplicate_ids.any():
                duplicate_count = int(best_place.loc[duplicate_ids, "object_id"].nunique())
                st.warning(
                    f"Kohatabelis leidus {duplicate_count} dubleeritud object_id väärtust. "
                    "Rakendus kasutab iga museaali kohta esimest rida; palun kontrolli kohatabelit."
                )
                best_place = best_place.drop_duplicates("object_id", keep="first").copy()

        keep = [
            c
            for c in [
                "object_id",
                "best_place",
                "place_precision",
                "country",
                "region",
                "rajon",
                "village",
                "lat",
                "lon",
                "has_coordinates",
                "koht",
                "modern_region_est",
                "modern_region_eng",
                "modern_rajon_est",
                "modern_rajon_eng",
                "map_precision",
                "normalization_status",
                "normalization_note",
            ]
            if c in best_place.columns
        ]

        objects = objects.merge(
            best_place[keep],
            on="object_id",
            how="left",
        )

    return objects, materials, collectors, best_place

objects, materials, collectors, best_place = load_data()


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def looks_like_bad_value(value):
    if pd.isna(value):
        return True
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "teadmata"}:
        return True
    normalized = text.replace(".", "").replace(",", "").replace("-", "").strip()
    if normalized.isdigit():
        return True
    return False


def unique_clean(series):
    if series is None:
        return []
    return sorted(
        {str(x).strip() for x in series.dropna().unique() if not looks_like_bad_value(x)},
        key=str.lower,
    )


def safe_contains(series, query):
    return series.fillna("").astype(str).str.contains(query, case=False, na=False, regex=False)


def readable_count(n):
    return f"{n:,}".replace(",", "\u202f")


TABLE_COLUMN_CONFIG = {
    "museal_number": "Museaali number",
    "title": "Eseme nimi",
    "ethnic_group": "Rahvus",
    "ethnic_group_detail": "Rahvarühm",
    "material_categories_joined": "Materjalikategooria",
    "materials_joined": "Materjal",
    "year": "Kogumisaasta",
    "collectors_joined": "Koguja",
    "country": "Riik",
    "modern_region_est": "Regioon",
    "modern_rajon_est": "Rajoon",
    "object_url": st.column_config.LinkColumn(
        "Museaal MuISis",
        display_text="Ava MuISis",
    ),
}


def museum_table_columns(df):
    """Return the standard user-facing museum table columns that exist in df."""
    wanted = [
        "museal_number",
        "title",
        "ethnic_group",
        "ethnic_group_detail",
        "material_categories_joined",
        "materials_joined",
        "year",
        "collectors_joined",
        "country",
        "modern_region_est",
        "modern_rajon_est",
        "object_url",
    ]
    return [c for c in wanted if c in df.columns]


def show_museum_table(df, limit=500):
    """Display a consistent Estonian-language museum table."""
    cols = museum_table_columns(df)
    if not cols:
        st.info("Kuvatavaid museaaliandmeid ei leitud.")
        return
    st.dataframe(
        df[cols].head(limit),
        use_container_width=True,
        hide_index=True,
        column_config={
            c: TABLE_COLUMN_CONFIG[c]
            for c in cols
            if c in TABLE_COLUMN_CONFIG
        },
    )


def ids_for_long_filter(long_df, value_col, selected_values):
    if not selected_values or long_df.empty or value_col not in long_df.columns:
        return None
    return set(long_df[long_df[value_col].isin(selected_values)]["object_id"].astype(str))


def apply_all_filters(
    source_df,
    search_text=None,
    year_range=None,
    include_unknown_years=False,
    selected_ethnic=None,
    selected_ethnic_detail=None,
    selected_material_categories=None,
    selected_materials=None,
    selected_collectors=None,
    selected_country=None,
    selected_region=None,
    selected_rajon=None,
    selected_village=None,
    exclude=None,
):
    exclude = exclude or set()
    filtered = source_df.copy()

    if "search" not in exclude and search_text:
        mask = pd.Series(False, index=filtered.index)
        for col in [
            "title", "description", "ethnic_group", "ethnic_group_detail", "museal_number",
            "materials_joined", "material_categories_joined", "collectors_joined",
            "best_place", "country",
            "modern_region_est", "modern_rajon_est",
            "region", "rajon", "village",
            "places_not_cleaned", "comments", "legend", "text_on_object",
        ]:
            if col in filtered.columns:
                mask |= safe_contains(filtered[col], search_text)
        filtered = filtered[mask]

    if "year" not in exclude and year_range and "year" in filtered.columns:
        known_years = filtered["year"].dropna()
        if not known_years.empty:
            full_min = int(objects["year"].dropna().min())
            full_max = int(objects["year"].dropna().max())
            is_full_range = (
                int(year_range[0]) == full_min
                and int(year_range[1]) == full_max
            )

            year_mask = filtered["year"].between(
                year_range[0],
                year_range[1],
            )

            # Täisvaates jäävad kogumisaastata annetused nähtavale.
            # Kui kasutaja kitsendab aastavahemikku, ei kuulu teadmata
            # kogumisaastaga museaalid sellesse vahemikku, v.a kui kasutaja
            # need eraldi sisse lülitab.
            if is_full_range or include_unknown_years:
                year_mask |= filtered["year"].isna()

            filtered = filtered[year_mask]

    if "ethnic_group" not in exclude and selected_ethnic and "ethnic_group" in filtered.columns:
        filtered = filtered[filtered["ethnic_group"].isin(selected_ethnic)]

    if (
        "ethnic_group_detail" not in exclude
        and selected_ethnic_detail
        and "ethnic_group_detail" in filtered.columns
    ):
        filtered = filtered[
            filtered["ethnic_group_detail"].isin(selected_ethnic_detail)
        ]

    if "material_category" not in exclude and selected_material_categories:
        ids = ids_for_long_filter(materials, "material_category", selected_material_categories)
        if ids is not None:
            filtered = filtered[filtered["object_id"].isin(ids)]

    if "material" not in exclude and selected_materials:
        ids = ids_for_long_filter(materials, "material", selected_materials)
        if ids is not None:
            filtered = filtered[filtered["object_id"].isin(ids)]

    collector_col = (
        "collector_normalized"
        if "collector_normalized" in collectors.columns
        else "collector"
    )
    if "collector" not in exclude and selected_collectors and collector_col in collectors.columns:
        ids = ids_for_long_filter(collectors, collector_col, selected_collectors)
        if ids is not None:
            filtered = filtered[filtered["object_id"].isin(ids)]

    for col, selected in [
        ("country", selected_country),
        ("modern_region_est", selected_region),
        ("modern_rajon_est", selected_rajon),
    ]:
        if col not in exclude and selected and col in filtered.columns:
            filtered = filtered[filtered[col].isin(selected)]

    return filtered


def option_df_for(exclude_name):
    return apply_all_filters(
        objects,
        search_text=st.session_state.get("search_text", ""),
        year_range=st.session_state.get("year_range", None),
        include_unknown_years=st.session_state.get("include_unknown_years", False),
        selected_ethnic=st.session_state.get("ethnic_group", []),
        selected_ethnic_detail=st.session_state.get("ethnic_group_detail", []),
        selected_material_categories=st.session_state.get("material_category", []),
        selected_materials=st.session_state.get("material", []),
        selected_collectors=st.session_state.get("collector", []),
        selected_country=st.session_state.get("country", []),
        selected_region=st.session_state.get("modern_region_est", []),
        selected_rajon=st.session_state.get("modern_rajon_est", []),
        selected_village=None,
        exclude={exclude_name},
    )


def long_options_for(long_df, value_col, base_df):
    if long_df.empty or value_col not in long_df.columns:
        return []
    ids = set(base_df["object_id"].astype(str))
    return unique_clean(long_df[long_df["object_id"].isin(ids)][value_col])


def clean_stale_selection(key, valid_options):
    if key in st.session_state:
        st.session_state[key] = [x for x in st.session_state[key] if x in valid_options]


def reset_filters():
    st.session_state["search_text"] = ""
    st.session_state["include_unknown_years"] = False
    for key in ["ethnic_group", "ethnic_group_detail", "material_category", "material",
                "collector", "country", "modern_region_est", "modern_rajon_est"]:
        st.session_state[key] = []
    if "year" in objects.columns and objects["year"].notna().any():
        st.session_state["year_range"] = (
            int(objects["year"].dropna().min()),
            int(objects["year"].dropna().max()),
        )


# ─────────────────────────────────────────────────────────
# Default session state
# ─────────────────────────────────────────────────────────

if "search_text" not in st.session_state:
    st.session_state["search_text"] = ""

if "include_unknown_years" not in st.session_state:
    st.session_state["include_unknown_years"] = False

for key in ["ethnic_group", "ethnic_group_detail", "material_category", "material",
            "collector", "country", "modern_region_est", "modern_rajon_est"]:
    if key not in st.session_state:
        st.session_state[key] = []

min_year_default = None
max_year_default = None

if "year" in objects.columns and objects["year"].notna().any():
    min_year_default = int(objects["year"].dropna().min())
    max_year_default = int(objects["year"].dropna().max())
    if "year_range" not in st.session_state:
        st.session_state["year_range"] = (min_year_default, max_year_default)


# ─────────────────────────────────────────────────────────
# Title
# ─────────────────────────────────────────────────────────

st.title("Soome-ugri museaalid")
st.markdown(
    """
    <div class="intro-text">
    Prototüüp Eesti Rahva Muuseumi soome-ugri kogu uurimiseks.
    </div>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────
# Sidebar filters — interdependent
# ─────────────────────────────────────────────────────────

st.sidebar.title("Filtrid")
st.sidebar.caption("Filtrid mõjutavad üksteist ja uuenevad vastavalt valikutele.")
st.sidebar.button("Tühjenda filtrid", on_click=reset_filters)

st.sidebar.text_input(
    "Otsi tekstist",
    placeholder="nt tagapõll, neenets, Tiia Pedorelli...",
    key="search_text",
    help="Otsib nimetuse, kirjelduse, rahvarühma, museaalinumbri, materjali, koguja ja kohainfo seest.",
)

if min_year_default is not None and max_year_default is not None:
    st.sidebar.slider(
        "Kogumisaasta",
        min_year_default,
        max_year_default,
        key="year_range",
    )
    st.sidebar.checkbox(
        "Näita ka kogumisaastata museaale",
        key="include_unknown_years",
        help=(
            "Need on museaalid, millel puudub kogumisaasta – näiteks "
            "muuseumile annetatud esemed, mis ei kuulu kogumisekspeditsiooni. "
            "Täieliku aastavahemiku korral on need niikuinii nähtavad."
        ),
    )

if "ethnic_group" in objects.columns:
    opts = unique_clean(option_df_for("ethnic_group")["ethnic_group"])
    clean_stale_selection("ethnic_group", opts)
    st.sidebar.multiselect("Rahvarühm", opts, key="ethnic_group")

if "ethnic_group_detail" in objects.columns:
    opts = unique_clean(
        option_df_for("ethnic_group_detail")["ethnic_group_detail"]
    )
    clean_stale_selection("ethnic_group_detail", opts)
    st.sidebar.multiselect(
        "Täpsem rahvusrühm",
        opts,
        key="ethnic_group_detail",
    )

if "material_category" in materials.columns:
    opts = long_options_for(materials, "material_category", option_df_for("material_category"))
    clean_stale_selection("material_category", opts)
    st.sidebar.multiselect("Materjalikategooria", opts, key="material_category")

if "material" in materials.columns:
    opts = long_options_for(materials, "material", option_df_for("material"))
    clean_stale_selection("material", opts)
    st.sidebar.multiselect("Materjal", opts, key="material")

collector_filter_col = (
    "collector_normalized"
    if "collector_normalized" in collectors.columns
    else "collector"
)
if collector_filter_col in collectors.columns:
    opts = long_options_for(collectors, collector_filter_col, option_df_for("collector"))
    clean_stale_selection("collector", opts)
    st.sidebar.multiselect("Koguja", opts, key="collector")

for label, col, key in [
    ("Riik", "country", "country"),
    ("Tänapäevane regioon", "modern_region_est", "modern_region_est"),
    ("Tänapäevane rajoon", "modern_rajon_est", "modern_rajon_est"),
]:
    if col in objects.columns:
        opts = unique_clean(option_df_for(key)[col])
        clean_stale_selection(key, opts)
        st.sidebar.multiselect(label, opts, key=key)


# ─────────────────────────────────────────────────────────
# Apply filters
# ─────────────────────────────────────────────────────────

df = apply_all_filters(
    objects,
    search_text=st.session_state.get("search_text", ""),
    year_range=st.session_state.get("year_range", None),
    include_unknown_years=st.session_state.get("include_unknown_years", False),
    selected_ethnic=st.session_state.get("ethnic_group", []),
    selected_ethnic_detail=st.session_state.get("ethnic_group_detail", []),
    selected_material_categories=st.session_state.get("material_category", []),
    selected_materials=st.session_state.get("material", []),
    selected_collectors=st.session_state.get("collector", []),
    selected_country=st.session_state.get("country", []),
    selected_region=st.session_state.get("modern_region_est", []),
    selected_rajon=st.session_state.get("modern_rajon_est", []),
    selected_village=None,
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
        readable_count(materials[materials["object_id"].isin(mat_ids)]["object_id"].nunique()),
    )
else:
    kpi4.metric("Materjaliga museaale", "—")

if "best_place" in df.columns:
    kpi5.metric("Eri asukohti filtris", readable_count(df["best_place"].dropna().nunique()))
else:
    kpi5.metric("Eri asukohti filtris", "—")

if len(df) == 0:
    st.warning("Ühtegi museaali ei vasta praegusele filtrikombinatsioonile. Eemalda mõni filter.")


# ─────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Ülevaade",
        "Rahvarühmad",
        "Materjalid",
        "Kogujad",
        "Kohad",
        "Andmetabel",
    ]
)


# ── Tab 1: Ülevaade ──────────────────────────────────────

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
                year_counts, x="year", y="count", markers=True,
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
                top_titles, x="count", y="title", orientation="h",
                title="Levinumad nimetused",
                labels={"count": "Arv", "title": "Nimetus"},
            )
            fig.update_layout(yaxis={"autorange": "reversed"}, height=420)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Näited filtrisse jäänud museaalidest")
    show_museum_table(df, limit=100)


# ── Tab 2: Rahvarühmad ────────────────────────────────────

with tab2:
    st.subheader("Rahvarühmad")

    if "ethnic_group" in df.columns:
        top_ethnic = df["ethnic_group"].dropna().value_counts().head(30).reset_index()
        top_ethnic.columns = ["ethnic_group", "count"]
        fig = px.bar(
            top_ethnic, x="count", y="ethnic_group", orientation="h",
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
            show_museum_table(group_df, limit=300)
    else:
        st.info("Rahvarühma veergu ei leitud.")


# ── Tab 3: Materjalid ─────────────────────────────────────

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
                cat_counts, x="count", y="material_category", orientation="h",
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
                material_counts, x="count", y="material", orientation="h",
                title="Levinumad materjalid",
                labels={"count": "Esinemiste arv", "material": "Materjal"},
            )
            fig.update_layout(yaxis={"autorange": "reversed"}, height=480)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Materjalidega museaalid")

    material_object_ids = set(mat_filtered["object_id"].astype(str))
    material_objects = df[
        df["object_id"].astype(str).isin(material_object_ids)
    ].copy()

    show_museum_table(material_objects.drop_duplicates("object_id"), limit=500)


# ── Tab 4: Kogujad ────────────────────────────────────────

with tab4:
    st.subheader("Kogujad")

    ids = set(df["object_id"].astype(str))
    collectors_filtered = collectors[
        collectors["object_id"].isin(ids)
    ].copy()

    collector_col = (
        "collector_normalized"
        if "collector_normalized" in collectors_filtered.columns
        else "collector"
    )

    if collector_col in collectors_filtered.columns:
        top_collectors = (
            collectors_filtered[collector_col]
            .dropna()
            .value_counts()
            .head(30)
            .reset_index()
        )
        top_collectors.columns = ["collector", "count"]

        fig = px.bar(
            top_collectors,
            x="count",
            y="collector",
            orientation="h",
            title="Top kogujad",
            labels={
                "count": "Esinemiste arv",
                "collector": "Koguja",
            },
        )
        fig.update_layout(
            yaxis={"autorange": "reversed"},
            height=650,
        )
        st.plotly_chart(fig, use_container_width=True)

        selected_collector = st.selectbox(
            "Vaata ühe koguja museaale",
            [""] + top_collectors["collector"].tolist(),
        )

        if selected_collector:
            collector_ids = collectors_filtered[
                collectors_filtered[collector_col]
                == selected_collector
            ]["object_id"].unique()

            collector_df = df[
                df["object_id"].isin(collector_ids)
            ]

            st.markdown(
                f"Leitud **{len(collector_df)}** museaali "
                f"kogujaga **{selected_collector}**."
            )

            show_museum_table(collector_df, limit=300)
    else:
        st.info("Koguja veergu ei leitud.")

    st.divider()

    render_collectors_network(
        df,
        collectors_path=DATA_DIR / "collectors_long.csv",
    )

# ── Tab 5: Kohad ──────────────────────────────────────────

with tab5:
    st.subheader("Kohad")

    render_map(df)

    st.divider()

    c1, c2 = st.columns(2)

    with c1:
        if "country" in df.columns:
            country_counts = (
                df["country"]
                .dropna()
                .value_counts()
                .head(20)
                .reset_index()
            )
            country_counts.columns = ["country", "count"]

            fig = px.bar(
                country_counts,
                x="count",
                y="country",
                orientation="h",
                title="Riigid",
                labels={
                    "count": "Museaalide arv",
                    "country": "Riik",
                },
            )
            fig.update_layout(
                yaxis={"autorange": "reversed"},
                height=420,
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
            )

    with c2:
        if "map_precision" in df.columns:
            precision_labels = {
                "country": "Riik",
                "region": "Regioon",
                "district": "Rajoon",
                "settlement": "Asula",
            }

            precision_counts = (
                df["map_precision"]
                .dropna()
                .map(
                    lambda x: precision_labels.get(
                        str(x),
                        str(x),
                    )
                )
                .value_counts()
                .reset_index()
            )
            precision_counts.columns = [
                "map_precision",
                "count",
            ]

            fig = px.bar(
                precision_counts,
                x="map_precision",
                y="count",
                title="Kohainfo täpsus",
                labels={
                    "map_precision": "Täpsus",
                    "count": "Museaalide arv",
                },
            )
            fig.update_layout(height=420)
            st.plotly_chart(
                fig,
                use_container_width=True,
            )


# ── Tab 6: Andmetabel ─────────────────────────────────────

with tab6:
    st.subheader("Andmetabel")

    default_cols = museum_table_columns(df)

    selected_cols = st.multiselect(
        "Vali kuvatavad veerud",
        options=list(df.columns),
        default=default_cols,
        format_func=lambda c: (
            TABLE_COLUMN_CONFIG[c]
            if c in TABLE_COLUMN_CONFIG
            and isinstance(TABLE_COLUMN_CONFIG[c], str)
            else c
        ),
    )

    if len(df) > 1000:
        st.markdown(
            f"Kuvatakse esimesed **1000** rida **{readable_count(len(df))}** reast. "
            "CSV allalaadimine sisaldab kõiki filtreeritud ridu."
        )
    else:
        st.markdown(
            f"Kuvatakse **{readable_count(len(df))}** rida. "
            "CSV allalaadimine sisaldab kõiki filtreeritud ridu."
        )

    if selected_cols:
        st.dataframe(
            df[selected_cols].head(1000),
            use_container_width=True,
            hide_index=True,
            column_config={
                c: TABLE_COLUMN_CONFIG[c]
                for c in selected_cols
                if c in TABLE_COLUMN_CONFIG
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
