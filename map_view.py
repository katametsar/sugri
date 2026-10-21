"""Interactive Folium map for ERM Finno-Ugric objects.

Coordinates are reference points, not necessarily exact collection locations.
Location workbook is loaded in soome_ugri_streamlit_app.py.
"""
from html import escape

import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium


@st.cache_data(ttl=86400, show_spinner="Laen Venemaa regioonipiire…")
def load_russian_regions():
    """Load simplified ADM1 boundaries using geoBoundaries metadata API."""
    metadata_url = "https://www.geoboundaries.org/api/current/gbOpen/RUS/ADM1/"
    response = requests.get(metadata_url, timeout=30)
    response.raise_for_status()
    metadata = response.json()
    url = (metadata.get("simplifiedGeometryGeoJSON")
           or metadata.get("gjDownloadURL"))
    if not url:
        raise ValueError("geoBoundaries API ei tagastanud piirifaili aadressi")
    data_response = requests.get(url, timeout=90)
    data_response.raise_for_status()
    geojson = data_response.json()
    if not geojson.get("features"):
        raise ValueError("Piirifailis puuduvad regioonid")
    return geojson


def valid_values(series):
    return sorted(
        {str(v).strip() for v in series.dropna() if str(v).strip()},
        key=str.casefold,
    )


def display_items(items, heading):
    st.markdown(f"#### {heading}")
    if items.empty:
        st.info("Selle valikuga museaale ei leitud.")
        return
    st.caption(f"{items['object_id'].nunique():,} museaali".replace(",", " "))
    columns = {
        "museal_number": "Museaalinumber", "title": "Eseme nimetus",
        "year": "Kogumisaasta", "collectors_joined": "Koguja",
        "ethnic_group": "Rahvus", "ethnic_group_detail": "Rahvarühm",
        "best_place": "Algne kohakirjeldus", "modern_region_est": "Regioon",
        "modern_rajon_est": "Rajoon / omavalitsus", "village": "Küla / asula",
        "map_precision": "Kaardipunkti tase", "object_url": "MuIS",
    }
    found = [c for c in columns if c in items.columns]
    if not found:
        return
    view = (items[found]
            .drop_duplicates(subset=["museal_number"] if "museal_number" in found else None)
            .rename(columns=columns))
    config = ({"MuIS": st.column_config.LinkColumn("MuIS", display_text="Ava MuISis")}
              if "MuIS" in view.columns else {})
    st.dataframe(view.head(500), hide_index=True, width="stretch", column_config=config)
    if len(view) > 500:
        st.caption("Tabelis kuvatakse esimesed 500 museaali.")


def render_reference_map(items, context):
    coords = items.copy()
    for col in ("lat", "lon"):
        if col not in coords.columns:
            coords[col] = pd.NA
        coords[col] = pd.to_numeric(coords[col], errors="coerce")
    coords = coords.dropna(subset=["lat", "lon"])
    coords = coords[coords.lat.between(-90, 90) & coords.lon.between(-180, 180)].copy()
    if coords.empty:
        st.info("Selle valiku museaalidel puuduvad kasutatavad kaardikoordinaadid.")
        return None

    if "map_precision" not in coords.columns:
        coords["map_precision"] = "Määramata"
    coords["map_precision"] = coords["map_precision"].fillna("Määramata")

    # One clickable marker per physical reference point, even if the point
    # belongs to museaals with different reported precision levels.
    pts = coords.groupby(["lat", "lon"], dropna=False).agg(
        museaale=("object_id", "nunique")
    ).reset_index()
    for col in ("modern_region_est", "modern_rajon_est", "village", "map_precision"):
        if col in coords.columns:
            labels = coords.groupby(["lat", "lon"])[col].agg(
                lambda series: ", ".join(valid_values(series)[:4])
            ).reset_index(name=col)
            pts = pts.merge(labels, on=["lat", "lon"], how="left")

    center = [float(pts.lat.median()), float(pts.lon.median())]
    m = folium.Map(
        location=center, zoom_start=4, tiles="OpenStreetMap",
        control_scale=True, prefer_canvas=True,
    )
    try:
        borders = load_russian_regions()
        folium.GeoJson(
            borders,
            name="Venemaa regioonipiirid",
            style_function=lambda feature: {
                "color": "#303a46", "weight": 2, "opacity": 0.9,
                "fillOpacity": 0,
            },
            highlight_function=lambda feature: {
                "color": "#e27432", "weight": 3, "fillOpacity": 0.08,
            },
            tooltip=folium.GeoJsonTooltip(fields=["shapeName"], aliases=["Regioon:"]),
            # Boundary clicks are NOT selection events; point clicks are.
            control=True,
        ).add_to(m)
    except Exception as exc:
        st.warning(f"Venemaa regioonipiiride laadimine ebaõnnestus: {exc}")

    palette = {"asula": "#278660", "rajoon": "#356bb3",
               "regioon": "#d48525", "riik": "#9951a8"}
    for row in pts.itertuples(index=False):
        precision = str(getattr(row, "map_precision", "Määramata") or "Määramata")
        primary = precision.split(",")[0].strip().lower()
        color = palette.get(primary, "#666666")
        place = []
        for col in ("modern_region_est", "modern_rajon_est", "village"):
            label = getattr(row, col, "")
            if isinstance(label, str) and label:
                place.append(escape(label))
        popup = (("<b>" + " / ".join(place) + "</b><br>") if place else "")
        popup += (f"Museaale: {int(row.museaale)}<br>Kaardipunkti tase: "
                  f"{escape(precision)}<br><small>Esinduspunkt, mitte tingimata "
                  "täpne kogumiskoht.</small>")
        folium.CircleMarker(
            location=[float(row.lat), float(row.lon)],
            radius=min(13, 5 + int(row.museaale) ** 0.35),
            color=color, weight=2, fill=True,
            fill_color=color, fill_opacity=0.85,
            tooltip=f"Vali {int(row.museaale)} museaali · {precision}",
            popup=folium.Popup(popup, max_width=350),
        ).add_to(m)

    if len(pts) > 1:
        m.fit_bounds(
            [[float(pts.lat.min()), float(pts.lon.min())],
             [float(pts.lat.max()), float(pts.lon.max())]],
            padding=(25, 25),
        )
    else:
        m.location = [float(pts.iloc[0].lat), float(pts.iloc[0].lon)]
        m.options["zoom"] = 6
    folium.LayerControl(collapsed=True).add_to(m)

    # st_folium sends a marker click back to Streamlit; components.html doesn't.
    # Stable per-context key prevents carrying a click between different regions.
    import hashlib
    context_key = hashlib.sha1(context.encode("utf-8")).hexdigest()[:12]
    event = st_folium(
        m, height=565, width=950, key=f"erm_places_{context_key}_{st.session_state.get(f'map_reset_{context_key}', 0)}",
        returned_objects=["last_object_clicked"],
    )
    st.caption(
        f"Kaardil {len(pts)} viitepunkti ja {coords['object_id'].nunique()} "
        "koordinaatidega museaali. Punkt võib tähistada rajooni, regiooni "
        "või omavalitsuse esinduspunkti, mitte täpset kogumiskohta."
    )
    click = (event or {}).get("last_object_clicked")
    if click and "lat" in click and "lng" in click:
        lat, lon = float(click["lat"]), float(click["lng"])
        # Match to the exact marker; small tolerance for JS floating point values.
        points_near = pts[
            (pts["lat"] - lat).abs().lt(1e-5)
            & (pts["lon"] - lon).abs().lt(1e-5)
        ]
        if not points_near.empty:
            p = points_near.iloc[0]
            selected = coords[
                (coords["lat"] - float(p.lat)).abs().lt(1e-7)
                & (coords["lon"] - float(p.lon)).abs().lt(1e-7)
            ]
            st.info(f"Valitud kaardipunkt: {len(selected)} museaali. Allolev tabel näitab ainult selle punkti museaale.")
            if st.button("Näita uuesti kõiki piirkonna museaale", key=f"reset_{context_key}"):
                # Increment key to mount a fresh map without a retained click.
                st.session_state[f"map_reset_{context_key}"] = st.session_state.get(f"map_reset_{context_key}", 0) + 1
                st.rerun()
            return selected
    return None


def render_map(filtered_df):
    st.subheader("Soome-ugri museaalide päritolukaart")
    st.caption(
        "Kaart arvestab külgriba filtreid. Klõpsa viitepunktil, et näha "
        "allolevas tabelis ainult selle punktiga seotud museaale."
    )
    if filtered_df is None or filtered_df.empty:
        st.info("Praeguste filtritega pole museaale.")
        return
    df = filtered_df.copy()
    if "country" not in df.columns:
        st.warning("Puudub veerg country.")
        return
    view = st.radio("Vaade", ["Riigid", "Venemaa: regioonid ja rajoonid"],
                    horizontal=True, key="folium_view")
    if view == "Riigid":
        countries = valid_values(df["country"])
        if not countries:
            st.info("Riigiinfoga museaale ei leitud.")
            return
        country = st.selectbox("Vali riik", countries, key="folium_country")
        chosen = df[df["country"] == country]
        st.metric("Museaale valitud riigis", f"{chosen['object_id'].nunique():,}".replace(",", " "))
        selected = render_reference_map(chosen, f"country:{country}")
        display_items(selected if selected is not None else chosen,
                      f"{country}: {'valitud punkti' if selected is not None else 'kõik'} museaalid")
        return
    rus = df[df["country"] == "Venemaa"].copy()
    if "modern_region_est" not in rus or rus["modern_region_est"].dropna().empty:
        st.info("Filtri museaalidel puudub Venemaa regiooniteave.")
        return
    level = st.radio("Piirkonna tase", ["Regioonid", "Rajoonid"],
                     horizontal=True, key="folium_level")
    region = st.selectbox("Vali regioon", valid_values(rus["modern_region_est"]),
                          key="folium_region")
    in_region = rus[rus["modern_region_est"] == region]
    district = "Kõik"
    if level == "Rajoonid" and "modern_rajon_est" in in_region.columns:
        district = st.selectbox("Vali rajoon või omavalitsus",
                                ["Kõik"] + valid_values(in_region["modern_rajon_est"]),
                                key="folium_district")
    chosen = (in_region if district == "Kõik" else
              in_region[in_region["modern_rajon_est"] == district])
    st.metric("Museaale valitud piirkonnas", f"{chosen['object_id'].nunique():,}".replace(",", " "))
    selected = render_reference_map(chosen, f"region:{region}:district:{district}")
    display_items(selected if selected is not None else chosen,
                  f"{region}: {'valitud punkti' if selected is not None else 'kõik'} museaalid")
