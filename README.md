# Soome-ugri esemekogu uurimisrakendus

Interaktiivne uurimisrakendus Eesti Rahva Muuseumi (ERM) soome-ugri esemekogu metaandmete uurimiseks. Rakendus võimaldab [MuISist](https://www.muis.ee/) pärinevaid museaalikirjeid võrrelda ja filtreerida rahvuse, täpsema rahvarühma, materjali, koguja, kogumisaja ning asukoha järgi.

**[Ava rakendus Streamlitis](https://soome-ugri-esemekogu.streamlit.app/)**

Rakendus on arenev prototüüp. Selle esmane sihtrühm on uurijad; edaspidi on eesmärk muuta kogu paremini ligipääsetavaks ka teistele huvilistele.

## Mida rakenduses teha saab?

- Uurida kogu üldvaateid ja museaalide andmetabeleid ning avada algseid kirjeid MuISis.
- Filtreerida museaale rahvuse ja rahvarühma, materjalikategooria ja materjali, koguja, kogumisaasta, riigi, tänapäevase regiooni ning rajooni/omavalitsuse järgi.
- Vaadata kogujate koosesinemise võrgustikke.
- Uurida kogumiskohtade viitepunkte Foliumi/Leafleti kaardil. Venemaa regioonipiirid laaditakse [geoBoundariesi](https://www.geoboundaries.org/) andmetest. Kaardipunktil klõpsates kuvatakse all tabelis selle punktiga seotud museaalid.

**Kaardipunkt ei tähenda alati eseme täpset kogumiskohta.** Kui usaldusväärselt on teada ainult rajoon, regioon või riik, kasutatakse selle haldusüksuse esinduspunkti. Ajalooliste kohanimede ja tänapäevaste haldusüksuste vastendamisel ei ole asukohta täpsustatud rohkem, kui allikad võimaldavad.

## Andmete päritolu ja ettevalmistamine

Lähteandmed on saadud MuISi soome-ugri esemekogu otsingutulemuste RDF-ekspordist. Töövoog ühendas automaatset teisendamist, keelemudeli abil tehtud esmast vabateksti eraldamist, mahukat käsitsi kontrolli, OpenRefine'i ja Pythoniga puhastamist ning ajalooliste kohanimede vastendamist tänapäevase haldusjaotusega.

Üldistatud töövoog:

**MuISi RDF → Pythoniga struktureerimine (sh Claude API esmane eraldus) → MuISi kirjete käsitsi kontroll → Python/OpenRefine → ajaloolise kohainfo vastendamine → rakenduse andmetabelid → Streamlit**

- RDF-i struktureeritud tunnused eraldati Pythoniga. Museaalide kommentaariväljadest püüti tasulise **Anthropic Claude API** abil eraldada kohanimesid, rahvust, kogumisaega ja kogujaid. Notebook'is `muis_to_rdf.ipynb` on säilinud päringuviip ja mudeli ID `claude-sonnet-4-20250514`. Töötlus toimus detsembris 2025 ja jaanuaris 2026.
- Keelemudeli väljund oli esialgne ja sisaldas nii puuduvaid kui ka valesti paigutatud väärtusi. Seejärel kontrolliti kahe kuu jooksul käsitsi ligi **10 000 museaali** MuISi algkirjete põhjal ning parandati ja täiendati andmeid.
- Materjalide ja kohanimede ühtlustamisel kasutati Pythonit ja OpenRefine'i. Kohainfo puhul eelistati üksiku museaali detailset allikakirjeldust ekspeditsiooni üldisele asukohale. GeoNamesi skriptiga leitud asulavasted olid **kontrollimist vajavad kandidaadid**, mitte automaatselt kinnitatud kogumiskohad.
- Rakenduse jaoks seoti museaalide, materjalide, kogujate ja asukohtade tabelid ühise `object_id` kaudu.

Üksikasjalikumad kirjeldused:

- [Andmete ettevalmistamise töövoog](DATA_PREPARATION.md)
- [Tehisintellekti kasutamine ja tulemuste kontroll](AI_USAGE.md)

Töötlus ei ole täies ulatuses ühe käsuga taasesitatav: lõppandmestik sisaldab käsitsi tehtud kontrolli ja parandusi. Algseid Claude API vastussõnumeid eraldi ei salvestatud; struktureeritud väljund salvestati andmetabelitesse. See ei takista rakenduse käivitamist juba ettevalmistatud andmetega.

## Repositooriumi ülesehitus

| Fail või kaust | Otstarve |
| --- | --- |
| `soome_ugri_streamlit_app.py` | Põhirakendus, andmete laadimine, filtrid ja ülevaated |
| `map_view.py` | Foliumi kaart, geoBoundariesi regioonipiirid ja punktipõhine tabelifilter |
| `collector_network.py` | Kogujate koosesinemise võrgustikuvaade |
| `app_ready_tables/objects_app.csv` | Museaalide põhitabel |
| `app_ready_tables/materials_long.csv` | Museaalide materjalid |
| `app_ready_tables/collectors_long.csv` | Museaalide kogujad |
| `app_ready_tables/museaalide_kogumiskohad.xlsm` | Kohainfo; rakendus loeb lehte `Asukohad` |
| `muis_to_rdf.ipynb` | RDF-i esmane teisendamine ja Claude API abil vabateksti struktureerimine |
| `data cleaning/` | Säilitatud puhastamis- ja vastendamisfailid (sh OpenRefine'i töötlused) |
| `requirements.txt` | Rakenduse Pythoni sõltuvused |
| `Procfile` | Streamliti käivituskäsk Renku keskkonnas |

**Praegune kohainfo allikas on `museaalide_kogumiskohad.xlsm`.** Varasem fail `object_best_place_modern_regions_raions.csv` ei ole enam põhirakenduse kohainfo allikas.

## Rakenduse käivitamine arvutis

Eeldus: Python ja Git on arvutisse paigaldatud. Käsklused on macOS-i/Linuxi terminali jaoks.

```bash
git clone https://github.com/katametsar/sugri.git
cd sugri
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run soome_ugri_streamlit_app.py
```

Rakenduse käivitamiseks peavad eespool loetletud neli andmefaili paiknema kaustas `app_ready_tables/`. Kaardipõhi ja geoBoundariesi piirid vajavad võrguühendust. Rakenduse tavapärane kasutamine ei nõua Claude API võtit: see oli vajalik andmete varasemas ettevalmistusetapis.

`requirements.txt` kirjeldab sõltuvusi, kuid ei lukusta kõiki transitiivseid paketiversioone. Keskkonna täpsemaks taastamiseks vt [keskkonna kirjeldust](ENVIRONMENT.md). Rakenduse käivitamine ja kogu algandmete ettevalmistamine on eri toimingud.

## Renku

Repositooriumi `Procfile` käivitab Streamliti veebirakenduse Renku sessioonis. See ei ole eraldi automatiseeritud andmepuhastuse töövoog. Andmete ettevalmistamise etapid ja nende piirangud on kirjeldatud failis [DATA_PREPARATION.md](DATA_PREPARATION.md).

**Autor ja töövoo kirjeldus:** Kata Maria Metsar, Eesti Rahva Muuseum. Põhjalikum metoodiline ülevaade: *MuISi andmetest soome-ugri esemekogu uurimisrakenduseni* (september 2026).

