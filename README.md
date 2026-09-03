# Soome-ugri esemekogu uurimise rakendus#

Interaktiivne prototüüp Eesti Rahva Muuseumi (ERM) soome-ugri esemekogu uurimiseks.

Rakendus võimaldab MuISist pärinevat esemekogu uurida kogu tasandil ning filtreerida museaale rahvuse ja rahvarühma, materjali, koguja, kogumisaja ning geograafilise asukoha järgi.

**[Ava rakendus Streamlitis](https://soome-ugri-esemekogu.streamlit.app/)**

## Andmed ja töövoog

Algandmed pärinevad [MuISist](https://www.muis.ee/) RDF-formaadis.

Andmete ettevalmistamise üldine töövoog:

**MuIS → RDF → Python → struktureeritud tabelid → OpenRefine ja käsitsi kontroll → Streamlit**

Andmete korrastamisel on muu hulgas:

- teisendatud RDF-andmed analüüsiks sobivateks tabeliteks;
- puhastatud ja ühtlustatud materjale ja materjalikategooriaid;
- korrastatud ajaloolisi kohanimesid ning seostatud neid tänapäevaste regioonide ja rajoonidega;
- lisatud osade museaalide puhul täpsem rahvarühm;
- kasutatud puudulike kirjete kontrollimiseks ka kogude ja ekspeditsioonide konteksti.

Kohainfo korrastamisel lähtuti põhimõttest, et asukohta ei täpsustata rohkem, kui allikad võimaldavad. Kui teada on ainult regioon, jääb museaali asukoha täpsuseks regioon.

## Rakendus

Rakenduses saab kogu uurida ja filtreerida näiteks järgmiste tunnuste järgi:

- rahvus ja rahvarühm;
- materjalikategooria ja materjal;
- koguja;
- kogumisaasta;
- riik, tänapäevane regioon ja rajoon.

Rakendus sisaldab kogu üldvaateid, museaalide tabeleid, kogujatega seotud vaateid ja kaardivaadet. Üksikute museaalide juurest saab liikuda edasi nende algsete kirjete juurde MuISis.

## Failid

- `soome_ugri_streamlit_app.py` – Streamliti põhirakendus
- `map_view.py` – kaardivaate loogika
- `collector_network.py` – kogujate võrgustikuvaade
- `app_ready_tables/objects_app.csv` – museaalide põhitabel
- `app_ready_tables/materials_long.csv` – materjalid
- `app_ready_tables/collectors_long.csv` – kogujad
- `app_ready_tables/object_best_place_modern_regions_raions.csv` – korrastatud kohainfo

## Käivitamine lokaalselt

```bash
git clone https://github.com/katametsar/sugri.git
cd sugri

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

streamlit run soome_ugri_streamlit_app.py
