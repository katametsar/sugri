
# Andmete ettevalmistamine

See dokument kirjeldab Eesti Rahva Muuseumi (ERM) soome-ugri esemekogu uurimisrakenduse andmete ettevalmistamist, kasutatud tööriistu ja tööetappe.

Andmete korrastamine sisaldas nii automaatseid teisendusi kui ka mahukat käsitsi kontrolli. Seetõttu ei ole kogu lõppandmestiku loomine ühe käsuga täielikult automaatselt korratav.

## 1. MuISi lähteandmed

Algandmed pärinevad [Muuseumide Infosüsteemist MuIS](https://www.muis.ee/).

MuISi veebiliideses tehti soome-ugri esemekogu otsing ja salvestati tulemused funktsiooniga **„Salvesta tulemused RDF kujul”**.

Saadud RDF sisaldas kogusse kuuluvate museaalide viiteid, mille põhjal oli võimalik hankida üksikute museaalide kirjed.

MuISi andmestik võib aja jooksul muutuda, mistõttu ei pruugi sama otsingu hilisem kordamine anda täiesti identset tulemust.

## 2. RDF-i teisendamine ja esmane struktureerimine

Esialgne andmetöötlus toimus Pythonis, kasutades Google Colabi notebook'i `muis_to_rdf.ipynb`.

Notebook'i töövoog:

1. Loeb MuISist eksporditud RDF-faili.
2. Eraldab museaalide identifikaatorid ja viited.
3. Hangib üksikute museaalide RDF-andmed.
4. Eraldab RDF-i struktureeritud väljadest museaalide metaandmed.
5. Kasutab vajaduse korral Claude API-t vabatekstilise info esmaseks struktureerimiseks.
6. Salvestab tulemused Exceli tabelitesse.

Museaali unikaalne identifikaator `object_id` võimaldab hiljem eri andmetabeleid omavahel ühendada.

### Claude API kasutamine

Museaalide kommentaariväljadest eraldati tasulise Anthropic Claude API abil:

- kohanimed;
- rahvus;
- kogumisaeg;
- kogujad.

Kasutatud mudel oli `claude-sonnet-4-20250514`. Päringuviip ja API kasutamise kood on säilinud notebook'is `muis_to_rdf.ipynb`.

Notebook salvestas tulemusi partiidena Exceli failidesse (`muis_batch_...xlsx`), mis ühendati hiljem lõpptabeliks (`muis_FINAL_v5_...xlsx`).

API toorvastuseid eraldi ei salvestatud. Eraldatud väljad salvestati andmetabelitesse.

Täpsem kirjeldus on failis [AI_USAGE.md](AI_USAGE.md).

## 3. Museaalide käsitsi kontrollimine

Esialgse automaatse struktureerimise käigus ilmnes andmekvaliteedi probleeme:

- osa väärtusi jäi eraldamata;
- osa väärtusi sattus valesse välja;
- keerulisema struktuuriga kirjete puhul ei olnud automaatne tõlgendus usaldusväärne;
- osa väärtusi puudus juba MuISi algkirjetes.

Seetõttu kontrolliti ligi 10 000 museaali ükshaaval MuISi algkirjete põhjal.

Kontroll kestis ligikaudu kaks kuud. Selle käigus parandati ja täiendati eelkõige:

- kogujaid;
- kogumiskohti;
- kogumisaegu;
- materjale.

Automaatne eraldamine oli abivahend algandmete esmaseks struktureerimiseks. Praegune uurimisandmestik põhineb sellele järgnenud käsitsi kontrollil ning täiendavatel andmetöötlusetappidel.

## 4. Materjalide ja kohainfo puhastamine

Pärast käsitsi kontrolli kasutati andmete ühtlustamiseks Pythonit ja [OpenRefine'i](https://openrefine.org/).

Puhastamisel:

- ühtlustati sama tähendusega väärtuste erinevaid kirjapilte;
- parandati ilmseid kirjavigu;
- eemaldati või korrastati ebasobivaid väärtusi;
- kontrolliti duplikaate;
- standarditi materjalide ja kohanimede vorminguid.

Säilinud OpenRefine'i töötlusfailide hulgas on:

- `material_cleaning_openrefine.json`
- `detail_from_place_cleaning_openrefine.json`

Need sisaldavad konkreetseid massparandusi ja väärtuste asendusi.

OpenRefine'i operatsioonide failid kirjeldavad tehtud teisendusi, kuid nende uuesti rakendamine eeldab vastava lähteandmestiku olemasolu. Need ei sisalda kõiki käsitsi tehtud parandusi.

## 5. Sisuliste tunnuste korrastamine

Materjalide puhul eristati detailseid materjaliväärtusi ning laiemaid materjalikategooriaid.

Kontrolliti ka juhtumeid, kus materjalina oli märgitud hoopis valmistamistehnika, eseme detail, värvus või muu omadus.

Rahvusega seotud andmetes eristati võimaluse korral üldisem rahvus ja täpsem rahvarühm.

Puuduvate või ebaselgete väärtuste kontrollimiseks kasutati vajaduse korral museaali kogumiskonteksti ja ERMi varasemaid uurimistabeleid.

Kogumiskonteksti põhjal ei täidetud puuduvaid andmeid automaatselt: võimalikke seoseid ja erandeid kontrolliti eraldi.

## 6. Ajalooliste kohanimede vastendamine

MuISi kohakirjeldused pärinevad eri ajastutest ja kasutavad erinevaid haldusjaotusi ning nimekujusid.

Sama koht võis olla kirjeldatud näiteks:

- riigi;
- kubermangu;
- autonoomse vabariigi;
- oblasti või regiooni;
- rajooni;
- valla või omavalitsuse;
- küla või asula tasemel.

Eesmärk oli seostada ajaloolised kohakirjeldused tänapäevaste haldusüksustega, säilitades algse kohainfo ja selle täpsuse.

### Vastendamise põhimõtted

1. Esmase allikana kasutati konkreetse museaali detailset kohakirjeldust.
2. Ekspeditsiooni või kogu üldist asukohta kasutati täiendava allikana siis, kui detailne info puudus.
3. Ajaloolisi kohanimesid võrreldi tänapäevaste haldusüksuste andmetega.
4. Ebakindlad ja vastuolulised vasted kontrolliti eraldi.
5. Asukohta ei täpsustatud rohkem, kui allikad võimaldasid.

Kui usaldusväärselt oli võimalik määrata ainult regioon, jäi museaali asukohatäpsuseks regioon. Rajooni või küla ei lisatud oletuse põhjal.

Kaardil kasutatav koordinaat võib tähistada haldusüksuse esinduspunkti, mitte museaali täpset ajaloolist kogumiskohta.

### Kasutatud võrdlusandmed

Tänapäevase haldusjaotuse kontrollimisel kasutati muu hulgas Venemaa ja Läti haldusüksuste avaandmeid.

Töö käigus koostati eraldi kohanimede võrdlus- ja vastendustabeleid.

Üks kasutatud kontrolltabelitest on `ERM_ajalooliste_kohanimede_kokkuvote.xlsx.xlsm`.

## 7. GeoNamesi kandidaatide otsimine

Asulanimede võimalike vastete leidmiseks kasutati skripti `ERM_massvastendus_geonames.py`.

Skript:

- laadib vajaduse korral GeoNamesi riigipõhised andmefailid;
- normaliseerib kohanimesid;
- otsib nimekattuvusega asulaid;
- võrdleb võimalike vastete regiooni- ja rajooniinfot;
- järjestab leitud kandidaadid;
- salvestab tulemused kontrollimiseks CSV-faili.

Näide käivitamisest:

```bash
python ERM_massvastendus_geonames.py ERM_kulade_massvastenduse_tooleht_v20.csv
```

Tulemuseks luuakse fail:

`ERM_kulade_massvastenduse_tooleht_v20_GeoNames_kandidaadid.csv`

Vajaduse korral salvestatakse GeoNamesi allalaaditud andmed kausta `geonames_cache/`.

**Skript ei muuda automaatselt museaalide asukohti ega koordinaate.**

Leitud vasted on kandidaadid, mille sobivust tuleb kontrollida ajaloolise kohakirjelduse ja haldusliku kuuluvuse alusel.

Selles etapis ei kasutatud keelemudelit.

## 8. Rakenduse andmemudel

Puhastatud andmetest koostati Streamliti rakenduse jaoks omavahel seotud tabelid.

Museaalide põhitabel sisaldab üht kirjet iga museaali kohta. Korduvad tunnused, näiteks materjalid ja kogujad, paiknevad eraldi pikkades tabelites.

Rakendus kasutab kaustas `app_ready_tables/` järgmisi faile:

| Fail | Sisu |
| --- | --- |
| `objects_app.csv` | Museaalide põhitabel |
| `materials_long.csv` | Museaalide materjalid |
| `collectors_long.csv` | Museaalide kogujad |
| `museaalide_kogumiskohad.xlsm` | Algne ja tänapäevane kohainfo koos asukohatäpsusega |

Kohatabelist loetakse leht `Asukohad`.

Tabelid ühendatakse museaali identifikaatori `object_id` abil. Rakenduses ühtlustatakse identifikaatorid stringikujule.

Varasem fail `object_best_place_modern_regions_raions.csv` ei ole enam põhirakenduse kohainfo allikas.

## 9. Streamliti rakenduse käivitamine

Rakenduse kasutamiseks ei ole vaja kogu andmete ettevalmistamise protsessi korrata.

Kui vajalikud andmetabelid paiknevad kaustas `app_ready_tables/`, saab rakenduse käivitada järgmiselt:

```bash
python -m pip install -r requirements.txt
streamlit run soome_ugri_streamlit_app.py
```

Rakendus kasutab ettevalmistatud andmeid ega tee tavakasutuse käigus uusi Claude API päringuid.

Andmete algusest peale uuesti ettevalmistamine on eraldi tööprotsess, mis sisaldab RDF-andmete hankimist, automaatset teisendamist, käsitsi kontrolli, andmete puhastamist ning kohavastenduste hindamist.

Olemasolev Renku `Procfile` käivitab Streamliti rakenduse, mitte kogu eelnevat andmetöötlust.

## 10. Töövoo iteratiivsus

Rakenduse arendamine toimis ühtlasi andmekvaliteedi kontrollina.

Filtrid, koondarvud, museaalide tabelid ja kaardivaade aitasid tuvastada:

- ühe piirkonna erinevaid nimekujusid;
- puudulikke või vastuolulisi kohavastendusi;
- ootamatult puuduvaid väärtusi;
- vigaseid haldusüksuste seoseid;
- tabelite ühendamisel tekkinud ebakõlasid.

Probleemide ilmnemisel pöörduti tagasi varasemate puhastamise ja vastendamise etappide juurde.

Seetõttu on töövoog iteratiivne: andmete visualiseerimine aitab andmestikku kontrollida ja parandatud andmed omakorda täiendavad rakendust.

## Seotud materjalid

- [Rakenduse GitHubi repositoorium](https://github.com/katametsar/sugri)
- [Streamliti uurimisrakendus](https://soome-ugri-esemekogu.streamlit.app/)
- [Tehisintellekti kasutamise kirjeldus](AI_USAGE.md)
- Kata Maria Metsar (2026). *MuISi andmetest soome-ugri esemekogu uurimisrakenduseni*. Töövookirjeldus, Eesti Rahva Muuseum.
- [MuIS](https://www.muis.ee/)
- [GeoNames](https://www.geonames.org/)
