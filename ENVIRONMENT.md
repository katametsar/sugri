
## Pythoni ja teekide versioonid

Rakenduse kohalik arenduskeskkond on Python 3.10.11 (macOS).

Rakenduse otsesed sõltuvused on kirjeldatud failis `requirements.txt`. Kasutatud kohaliku virtuaalkeskkonna täpsed paketiversioonid on salvestatud faili `requirements-lock.txt`.

Olulisemad teegid:

| Teek | Versioon |
| --- | --- |
| Python | 3.10.11 |
| Streamlit | 1.62.0 |
| pandas | 2.3.3 |
| NumPy | 2.2.6 |
| Plotly | 6.9.0 |
| Folium | 0.20.0 |
| streamlit-folium | 0.26.2 |
| openpyxl | 3.1.5 |
| GeoPandas | 1.1.4 |

Pythoni versioon on dokumenteeritud failis `.python-version`.

Kohaliku virtuaalkeskkonna sõltuvuste kontrollimiseks kasutati käsku `python -m pip check`, mis ei tuvastanud katkiseid sõltuvusi.

Täpselt salvestatud paketiversioonide paigaldamiseks võib kasutada käsku:

```bash
python -m pip install -r requirements-lock.txt
```

Streamlit Cloud ja Renku võivad kasutada teistsugust Pythoni versiooni või paketikeskkonda. Siin kirjeldatud versioonid pärinevad kohalikust arenduskeskkonnast.
