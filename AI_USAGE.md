
# Tehisintellekti kasutamine

## Ülevaade

Eesti Rahva Muuseumi soome-ugri esemekogu andmete ettevalmistamisel ja uurimisrakenduse arendamisel kasutati tehisintellekti kaheks peamiseks tegevuseks:

1. MuISi museaalide vabatekstiliste kirjelduste esmaseks struktureerimiseks Claude API abil.
2. Pythoni koodi koostamise, parandamise, katsetamise ja Streamliti rakenduse arendamise abivahendina Claude'i ja ChatGPT-d.

Tehisintellekti abil saadud tulemusi ei käsitletud kontrollitud algandmete ega lõplike kohavastendustena.

## Claude API kasutamine andmete struktureerimiseks

MuISi RDF-ekspordist eraldati museaalide struktureeritud väljad Pythoniga. Osa uurimiseks vajalikust infost paiknes aga museaalide vabatekstilistes kommentaariväljades.

Ligikaudu detsembris 2025 või jaanuaris 2026 kasutati nende tekstide esmaseks struktureerimiseks tasulist Anthropic Claude API-t.

API-le antud ülesanne oli eraldada kommentaaridest järgmine teave:

- kohanimed;
- rahvus;
- kogumisaeg;
- kogujad.

Tulemused tagastati struktureeritud kujul ja salvestati edasiseks töötlemiseks andmetabelisse.

Kasutatud kood ja päringuviip on säilinud notebook'is `muis_to_rdf.ipynb`.

### Mudel ja seadistused

| Parameeter | Väärtus |
| --- | --- |
| Teenus | Anthropic Claude API |
| Mudeli ID | `claude-sonnet-4-20250514` |
| Maksimaalne väljundi pikkus | `max_tokens=1000` |
| Temperatuur | Koodis eraldi määramata |
| Sisend | MuISi museaalide kommentaariväljade tekst |
| Väljund | Struktureeritud kohanimed, rahvus, kogumisaeg ja kogujad |
| Kasutamise aeg | Detsember 2025 – jaanuar 2026 |

Mudeli täpne ID ja viip pärinevad säilinud notebook'i koodist. Kasutamise ajavahemik põhineb autori tagantjärele antud hinnangul.

### Tulemuste salvestamine

API vastustest eraldatud struktureeritud väljad salvestati Exceli tabelisse. Mudeli algseid vastussõnumeid eraldi logifailina ei salvestatud.

Seetõttu ei ole võimalik taastada iga üksiku API-päringu algset vastust täpselt sellisel kujul, nagu mudel selle tagastas. Säilinud on kasutatud kood ja viip ning hilisema töötluse käigus korrastatud andmed.

Tegemist oli ühekordse esialgse struktureerimisetapiga, mitte praeguse rakenduse käigus toimiva keelemudelipõhise andmetöötlusega. Streamliti rakenduse kasutamine ei nõua Claude API ühendust ega API võtit.

## Tulemuste kontrollimine

Claude API abil tehtud eraldamine ei osutunud piisavalt täielikuks ega usaldusväärseks.

Esines muu hulgas järgmisi probleeme:

- osa andmeid jäi eraldamata;
- mõned väärtused paigutati valedesse väljadesse;
- keerulisema struktuuriga kirjete puhul ei olnud tulemused üheselt tõlgendatavad.

Seetõttu võrreldi struktureeritud andmestikku MuISi algkirjetega.

Ligi 10 000 museaali kontrolliti käsitsi ligikaudu kahe kuu jooksul. Selle käigus parandati ja täiendati eelkõige kogujate, kohtade, kogumisaegade ja materjalide infot.

Käsitsi kontroll oli andmete ettevalmistamise keskne kvaliteedikontrolli etapp. Tehisintellekti esmane väljund ei olnud lõplik uurimisandmestik.

## Koodi arendamine tehisintellekti toel

Pythoni skriptide ning Streamliti uurimisrakenduse arendamisel kasutati abivahendina Claude'i ja ChatGPT-d.

Tehisintellekti kasutati näiteks:

- koodinäidete ja töötlusloogika koostamiseks;
- andmetabelite ühendamise ja teisendamise lahenduste väljatöötamiseks;
- vigade otsimiseks ja parandamiseks;
- Streamliti filtrite, graafikute ja kaardivaate arendamiseks;
- koodi ja dokumentatsiooni selgitamiseks ning täiendamiseks.

Rakenduse funktsionaalsust ja tulemusi kontrolliti arendamise käigus. Kasutatud tööriistade väljundite eest vastutab projekti autor.

## Keelemudeli ja teiste töötlusmeetodite eristamine

Kõik andmete ettevalmistamise etapid ei kasutanud tehisintellekti.

RDF-andmete programmiliseks teisendamiseks, materjalide ja kohanimede standardimiseks, tabelite ühendamiseks ning koordinaatide töötlemiseks kasutati Pythonit, OpenRefine'i ja muid andmetöötlusmeetodeid.

GeoNamesi põhine kohanimede vastendamise skript kasutab kohanimede normaliseerimist, nimekuju sarnasuse võrdlemist ja GeoNamesi andmestikku. See ei kasuta keelemudelit.

Ajalooliste kohanimede sidumine tänapäevaste haldusüksustega toimus eraldi tööetapina, mille puhul kontrolliti allikaid ja arvestati asukohainfo täpsusega.

## Reprodutseeritavuse piirid

Claude API esialgse eraldamise kood ja päringuviip on säilinud, kuid kõiki algseid API vastuseid ei salvestatud. Lisaks ei pruugi sama mudeli hilisem korduskäivitamine anda täpselt samasugust väljundit.

Tänapäevane rakenduse andmestik on kujunenud pärast automaatset eraldamist tehtud käsitsi kontrolli, paranduste ja täiendavate andmetöötlusetappide tulemusena. Seetõttu ei ole API-päringute kordamine vajalik juba ettevalmistatud andmetega Streamliti rakenduse käivitamiseks.

Andmete ettevalmistamise ülejäänud etappe kirjeldab [DATA_PREPARATION.md](DATA_PREPARATION.md).
