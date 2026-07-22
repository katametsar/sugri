
from __future__ import annotations

import math
from itertools import combinations
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


@st.cache_data(show_spinner=False)
def load_collectors(path: str = "collectors_long.csv") -> pd.DataFrame:
    """Load and clean the long collector table once."""
    data = pd.read_csv(path)
    required = {"object_id"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Failist puuduvad veerud: {', '.join(sorted(missing))}")

    # object_id peab olema string, sest peamises rakenduses (soome_ugri_streamlit_app.py)
    # teisendatakse object_id kõikjal stringiks. CSV-st loetuna on see int64,
    # mistõttu allpool tehtav isin() võrdlus visible_ids (stringid) vastu
    # ei leidnud kunagi vasteid ja graafik jäi alati tühjaks.
    data["object_id"] = data["object_id"].astype(str)

    if "collector_normalized" in data.columns:
        normalized = data["collector_normalized"]
    else:
        normalized = pd.Series(index=data.index, dtype="object")

    raw = data["collector"] if "collector" in data.columns else pd.Series(index=data.index, dtype="object")
    data["collector_name"] = normalized.fillna(raw).astype("string").str.strip()
    data = data[
        data["collector_name"].notna()
        & (data["collector_name"] != "")
        & (data["collector_name"].str.lower() != "nan")
    ]
    return data.drop_duplicates(["object_id", "collector_name"])


def _pair_table(collector_rows: pd.DataFrame) -> pd.DataFrame:
    """Create collector pairs from objects that have multiple collectors."""
    pair_counts: dict[tuple[str, str], int] = {}
    for names in collector_rows.groupby("object_id")["collector_name"]:
        unique_names = sorted(set(names[1].dropna()))
        for first, second in combinations(unique_names, 2):
            key = (first, second)
            pair_counts[key] = pair_counts.get(key, 0) + 1

    rows = [
        {"collector_1": first, "collector_2": second, "shared_objects": count}
        for (first, second), count in pair_counts.items()
    ]
    if not rows:
        return pd.DataFrame(columns=["collector_1", "collector_2", "shared_objects"])
    return pd.DataFrame(rows).sort_values("shared_objects", ascending=False)


def _network_figure(
    selected_collector: str,
    partners: pd.DataFrame,
    collector_counts: pd.Series,
) -> go.Figure:
    """Draw a lightweight ego network without NetworkX or PyVis."""
    partners = partners.sort_values("shared_objects", ascending=False).reset_index(drop=True)
    n = len(partners)

    center_x, center_y = 0.0, 0.0
    if n:
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
        partner_xy = {
            row["partner"]: (float(np.cos(angle)), float(np.sin(angle)))
            for (_, row), angle in zip(partners.iterrows(), angles)
        }
    else:
        partner_xy = {}

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    edge_hover_x: list[float] = []
    edge_hover_y: list[float] = []
    edge_hover_text: list[str] = []

    for _, row in partners.iterrows():
        x, y = partner_xy[row["partner"]]
        edge_x.extend([center_x, x, None])
        edge_y.extend([center_y, y, None])
        edge_hover_x.append((center_x + x) / 2)
        edge_hover_y.append((center_y + y) / 2)
        edge_hover_text.append(
            f"{selected_collector} + {row['partner']}<br>"
            f"Ühiseid museaale: {int(row['shared_objects'])}"
        )

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line={"width": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )

    figure.add_trace(
        go.Scatter(
            x=edge_hover_x,
            y=edge_hover_y,
            mode="markers",
            marker={"size": 18, "opacity": 0},
            text=edge_hover_text,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )

    partner_names = partners["partner"].tolist()
    partner_sizes = [
        max(14, min(42, 10 + 5 * np.log1p(float(collector_counts.get(name, 1)))))
        for name in partner_names
    ]

    figure.add_trace(
        go.Scatter(
            x=[partner_xy[name][0] for name in partner_names],
            y=[partner_xy[name][1] for name in partner_names],
            mode="markers+text",
            text=partner_names,
            textposition="top center",
            customdata=np.array(
                [[name, int(shared)] for name, shared in zip(
                    partner_names, partners["shared_objects"]
                )],
                dtype=object,
            ),
            marker={"size": partner_sizes},
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Ühiseid museaale: %{customdata[1]}<extra></extra>"
            ),
            showlegend=False,
        )
    )

    center_size = max(
        24,
        min(55, 18 + 6 * np.log1p(float(collector_counts.get(selected_collector, 1)))),
    )
    figure.add_trace(
        go.Scatter(
            x=[center_x],
            y=[center_y],
            mode="markers+text",
            text=[selected_collector],
            textposition="bottom center",
            marker={"size": [center_size]},
            hovertemplate=f"<b>{selected_collector}</b><extra></extra>",
            showlegend=False,
        )
    )

    figure.update_layout(
        height=560,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        xaxis={"visible": False},
        yaxis={"visible": False, "scaleanchor": "x", "scaleratio": 1},
        dragmode="pan",
    )
    return figure


def _spring_layout(
    node_names: list[str],
    edges_df: pd.DataFrame,
    iterations: int = 150,
    seed: int = 42,
) -> dict[str, tuple[float, float]]:
    """Lihtne Fruchterman-Reingold-tüüpi paigutus ilma NetworkX'ita.

    Kogujate arv on siin väike (kümned-sajad), nii et O(n²) tõukejõu
    arvutus on igal iteratsioonil täiesti kiire.
    """
    n = len(node_names)
    if n == 0:
        return {}
    if n == 1:
        return {node_names[0]: (0.0, 0.0)}

    rng = np.random.default_rng(seed)
    pos = rng.uniform(-1.0, 1.0, size=(n, 2))
    index = {name: i for i, name in enumerate(node_names)}
    k = 1.0 / math.sqrt(n) if n > 0 else 1.0

    edge_pairs = [
        (index[row["collector_1"]], index[row["collector_2"]])
        for _, row in edges_df.iterrows()
        if row["collector_1"] in index and row["collector_2"] in index
    ]

    for iteration in range(iterations):
        diff = pos[:, None, :] - pos[None, :, :]
        dist = np.linalg.norm(diff, axis=2)
        np.fill_diagonal(dist, 1e-6)
        repulsion = ((k * k) / dist)[..., None] * diff / dist[..., None]
        displacement = repulsion.sum(axis=1)

        for i, j in edge_pairs:
            delta = pos[i] - pos[j]
            dist_ij = max(float(np.linalg.norm(delta)), 1e-6)
            force = (dist_ij**2 / k) * (delta / dist_ij)
            displacement[i] -= force
            displacement[j] += force

        temperature = 0.12 * (1 - iteration / iterations)
        lengths = np.linalg.norm(displacement, axis=1)
        lengths[lengths == 0] = 1e-6
        pos += (displacement / lengths[:, None]) * np.minimum(lengths, temperature)[:, None]

    return {name: (float(pos[index[name]][0]), float(pos[index[name]][1])) for name in node_names}


def _overview_network_figure(
    pairs: pd.DataFrame,
    collector_counts: pd.Series,
    max_labels: int = 30,
) -> go.Figure:
    """Joonista terve kogujate koostöövõrgustik (mitte ainult ühe inimese ümber)."""
    nodes = sorted(set(pairs["collector_1"]).union(pairs["collector_2"]))
    positions = _spring_layout(nodes, pairs)

    max_shared = max(1, int(pairs["shared_objects"].max()))
    bins = [
        (1, max(1, max_shared // 3), 1.0, 0.35),
        (max(1, max_shared // 3) + 1, max(1, 2 * max_shared // 3), 2.2, 0.55),
        (max(1, 2 * max_shared // 3) + 1, max_shared, 4.0, 0.8),
    ]

    figure = go.Figure()

    for low, high, width, opacity in bins:
        subset = pairs[(pairs["shared_objects"] >= low) & (pairs["shared_objects"] <= high)]
        if subset.empty:
            continue
        edge_x: list[float | None] = []
        edge_y: list[float | None] = []
        for _, row in subset.iterrows():
            x0, y0 = positions[row["collector_1"]]
            x1, y1 = positions[row["collector_2"]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        figure.add_trace(
            go.Scatter(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line={"width": width, "color": "rgba(120,100,70,0.9)"},
                opacity=opacity,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Nähtamatud hõljutuspunktid iga serva keskel, et näidata ühiste esemete arvu
    hover_x, hover_y, hover_text = [], [], []
    for _, row in pairs.iterrows():
        x0, y0 = positions[row["collector_1"]]
        x1, y1 = positions[row["collector_2"]]
        hover_x.append((x0 + x1) / 2)
        hover_y.append((y0 + y1) / 2)
        hover_text.append(
            f"{row['collector_1']} + {row['collector_2']}<br>"
            f"Ühiseid museaale: {int(row['shared_objects'])}"
        )
    figure.add_trace(
        go.Scatter(
            x=hover_x,
            y=hover_y,
            mode="markers",
            marker={"size": 16, "opacity": 0},
            text=hover_text,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )

    node_sizes = [
        max(10, min(46, 8 + 5 * np.log1p(float(collector_counts.get(name, 1)))))
        for name in nodes
    ]
    # Sildid ainult kõige aktiivsematel kogujatel, muidu läheb suure võrgustiku
    # puhul silt-silma-peale liiga kirjuks; ülejäänud on ikkagi hiirega üle
    # viies loetavad (hover).
    prominent = set(
        collector_counts.reindex(nodes).sort_values(ascending=False).head(max_labels).index
    )
    labels = [name if name in prominent else "" for name in nodes]

    figure.add_trace(
        go.Scatter(
            x=[positions[name][0] for name in nodes],
            y=[positions[name][1] for name in nodes],
            mode="markers+text",
            text=labels,
            textposition="top center",
            textfont={"size": 11},
            customdata=np.array(
                [[name, int(collector_counts.get(name, 0))] for name in nodes],
                dtype=object,
            ),
            marker={"size": node_sizes, "color": "rgba(183,162,122,0.95)", "line": {"width": 1, "color": "#4a4338"}},
            hovertemplate="<b>%{customdata[0]}</b><br>Museaale kokku: %{customdata[1]}<extra></extra>",
            showlegend=False,
        )
    )

    figure.update_layout(
        height=620,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        xaxis={"visible": False},
        yaxis={"visible": False, "scaleanchor": "x", "scaleratio": 1},
        dragmode="pan",
    )
    return figure


def _render_overview(
    pairs: pd.DataFrame,
    collector_counts: pd.Series,
    max_labels: int = 30,
) -> None:
    minimum_shared = st.slider(
        "Vähemalt mitu ühist museaali (koostöö tugevus)",
        min_value=1,
        max_value=max(1, int(pairs["shared_objects"].max())),
        value=1,
        key="collector_network_overview_min_shared",
        help="Näita ainult neid koostöösuhteid, kus kaks kogujat jagavad vähemalt nii mitut museaali.",
    )
    visible_pairs = pairs[pairs["shared_objects"] >= minimum_shared]

    if visible_pairs.empty:
        st.info("Selle lävendiga koostöösuhteid ei jää järele. Proovi väiksemat väärtust.")
        return

    st.caption(
        "Iga punkt on koguja (suurus = kogutud museaalide arv), iga joon tähendab, "
        "et kaks kogujat on märgitud vähemalt ühe sama museaali juurde (paksem joon = rohkem ühiseid esemeid). "
        "Nimed on kirjas kõige aktiivsematel kogujatel, ülejäänud avanevad hiirega üle viies."
    )

    st.plotly_chart(
        _overview_network_figure(visible_pairs, collector_counts, max_labels=max_labels),
        use_container_width=True,
        config={"displayModeBar": False},
    )


def render_collectors_network(
    filtered_objects: pd.DataFrame,
    collectors_path: str = "collectors_long.csv",
    max_partners: int = 20,
) -> None:
    """
    Render collector co-occurrence inside the existing Collectors/Persons tab.

    `filtered_objects` must be the already filtered objects dataframe from the
    main app and contain `object_id`.
    """
    st.subheader("Kes on koos kogunud?")

    if "object_id" not in filtered_objects.columns:
        st.error("Filtreeritud andmetes puudub veerg `object_id`.")
        return

    collector_rows = load_collectors(collectors_path)
    visible_ids = set(filtered_objects["object_id"].dropna().tolist())
    collector_rows = collector_rows[collector_rows["object_id"].isin(visible_ids)]

    if collector_rows.empty:
        st.info("Praeguste filtritega ei leitud kogujate andmeid.")
        return

    collector_counts = (
        collector_rows.groupby("collector_name")["object_id"]
        .nunique()
        .sort_values(ascending=False)
    )
    pairs = _pair_table(collector_rows)

    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("Kogujaid", f"{collector_counts.size:,}".replace(",", " "))
    metric_2.metric(
        "Mitme kogujaga museaale",
        f"{collector_rows.groupby('object_id')['collector_name'].nunique().gt(1).sum():,}".replace(",", " "),
    )
    metric_3.metric("Kogujapaare", f"{len(pairs):,}".replace(",", " "))

    collectors_with_partners = sorted(
        set(pairs["collector_1"]).union(pairs["collector_2"])
    ) if not pairs.empty else []

    if not collectors_with_partners:
        st.info("Praeguste filtritega ei ole museaale, mille juures esineks vähemalt kaks kogujat.")
        return

    view = st.radio(
        "Vaade",
        ["Suur pilt (kõik kogujad)", "Ühe koguja detailvaade"],
        horizontal=True,
        key="collector_network_view",
    )

    if view.startswith("Suur pilt"):
        _render_overview(pairs, collector_counts)
        return

    default_collector = max(
        collectors_with_partners,
        key=lambda name: int(collector_counts.get(name, 0)),
    )
    selected = st.selectbox(
        "Vali koguja",
        collectors_with_partners,
        index=collectors_with_partners.index(default_collector),
        key="collector_network_selected",
    )

    selected_pairs = pairs[
        (pairs["collector_1"] == selected) | (pairs["collector_2"] == selected)
    ].copy()
    selected_pairs["partner"] = np.where(
        selected_pairs["collector_1"] == selected,
        selected_pairs["collector_2"],
        selected_pairs["collector_1"],
    )
    selected_pairs = selected_pairs.sort_values("shared_objects", ascending=False)

    minimum_shared = st.slider(
        "Vähemalt mitu ühist museaali?",
        min_value=1,
        max_value=max(1, int(selected_pairs["shared_objects"].max())),
        value=1,
        key="collector_network_min_shared",
    )
    visible_partners = selected_pairs[
        selected_pairs["shared_objects"] >= minimum_shared
    ].head(max_partners)

    st.caption(
        "Seos tähendab, et kaks kogujat on märgitud vähemalt ühe sama museaali juurde. "
        "See ei tõesta alati, et nad viibisid füüsiliselt samal välitööl."
    )

    st.plotly_chart(
        _network_figure(selected, visible_partners, collector_counts),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    st.markdown("#### Sagedasemad kaaslased")
    partner_table = visible_partners[["partner", "shared_objects"]].rename(
        columns={"partner": "Koguja", "shared_objects": "Ühiseid museaale"}
    )
    st.dataframe(partner_table, hide_index=True, use_container_width=True)

    partner_options = visible_partners["partner"].tolist()
    if not partner_options:
        return

    chosen_partner = st.selectbox(
        "Näita ühiseid museaale kogujaga",
        partner_options,
        key="collector_network_partner",
    )

    first_ids = set(
        collector_rows.loc[
            collector_rows["collector_name"] == selected, "object_id"
        ].tolist()
    )
    second_ids = set(
        collector_rows.loc[
            collector_rows["collector_name"] == chosen_partner, "object_id"
        ].tolist()
    )
    shared_ids = first_ids.intersection(second_ids)
    shared_objects = filtered_objects[
        filtered_objects["object_id"].isin(shared_ids)
    ].copy()

    preferred_columns = [
        "museal_number",
        "title",
        "year",
        "ethnic_group",
        "best_place",
        "object_url",
    ]
    columns = [column for column in preferred_columns if column in shared_objects.columns]
    if "object_id" not in columns:
        columns.insert(0, "object_id")

    st.markdown(
        f"#### {selected} ja {chosen_partner}: "
        f"{len(shared_objects)} ühist museaali"
    )
    st.dataframe(
        shared_objects[columns].drop_duplicates("object_id"),
        hide_index=True,
        use_container_width=True,
        column_config={
            "object_url": st.column_config.LinkColumn("MuISi link", display_text="Ava"),
        } if "object_url" in columns else None,
    )
