# Soome-ugri museaalide Streamlit prototüüp

## Failid

- `soome_ugri_streamlit_app.py` – Streamliti rakendus
- `app_ready_tables/objects_app.csv` – põhitabel, üks rida ühe museaali kohta
- `app_ready_tables/materials_long.csv` – materjalid long-form kujul
- `app_ready_tables/collectors_long.csv` – kogujad long-form kujul
- `app_ready_tables/places_long_clean.csv` – puhastatud kohainfo uurimiseks
- `app_ready_tables/object_best_place.csv` – üks parim koht ühe museaali kohta

## Käivitamine

Pane `soome_ugri_streamlit_app.py` samasse kausta, kus on kaust `app_ready_tables`.

Seejärel käivita terminalis:

```bash
streamlit run soome_ugri_streamlit_app.py
```

## Märkus

See versioon on teadlikult ilma kaardita. Kohainfo on küll kaasas, aga kaardiloogika tuleks lisada alles pärast koordinaatide ja kohatasemete kontrollimist.
