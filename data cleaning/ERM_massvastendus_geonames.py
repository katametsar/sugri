#!/usr/bin/env python3
"""Find GeoNames settlement candidates for ERM place worklist. Does NOT edit source data.

Usage:
    python ERM_massvastendus_geonames.py ERM_kulade_massvastenduse_tooleht_v20.csv

Requires Python 3.9+; standard library only. Downloads GeoNames country dumps as needed.
"""
import csv
import difflib
import io
import re
import sys
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

BASE_URL = 'https://download.geonames.org/export/dump/'
COUNTRIES = {'Venemaa': 'RU', 'Soome': 'FI', 'Läti': 'LV', 'Russia': 'RU', 'Finland': 'FI', 'Latvia': 'LV', 'RU': 'RU', 'FI': 'FI', 'LV': 'LV'}
CYR = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
 ['a','b','v','g','d','e','yo','zh','z','i','y','k','l','m','n','o','p','r','s','t','u','f','kh','ts','ch','sh','shch','','y','','e','yu','ya']))

def normalize(value):
    text = str(value or '').casefold().strip()
    text = text.replace('ё', 'е')
    text = re.sub(r'\b(küla|kyla|kylä|village|derevnya|derevnja|деревня|село|поселок|посёлок|rajoon|район|linn)\b', ' ', text)
    text = text.replace('õ', 'o').replace('ä', 'a').replace('ö', 'o').replace('ü', 'u').replace('š', 'sh').replace('ž', 'zh')
    text = ''.join(CYR.get(c, c) for c in text)
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return re.sub('[^a-z0-9]+', '', text)

def download(name, folder):
    path = folder / name
    if path.exists() and path.stat().st_size:
        return path
    url = BASE_URL + name
    print(f'Laadin alla: {url}', flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'ERM-GeoNames-check/1.0 (academic noncommercial geocoding)'})
    try:
        with urllib.request.urlopen(req, timeout=120) as response, path.open('wb') as output:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path

def load_admin(folder):
    a1, a2 = {}, {}
    for filename, dest in [('admin1CodesASCII.txt', a1), ('admin2Codes.txt', a2)]:
        try:
            path = download(filename, folder)
            with path.open(encoding='utf-8') as f:
                for line in f:
                    fields = line.rstrip('\n').split('\t')
                    if len(fields) >= 2:
                        dest[fields[0]] = fields[1]
        except Exception as exc:
            print(f'Hoiatus: {filename} ei õnnestunud laadida ({exc}).', file=sys.stderr)
    return a1, a2

def names_of(record):
    # GeoNames feature name and ascii name, alternate names field
    source = [record[1], record[2]] + record[3].split(',')[:100]
    return {normalize(n) for n in source if normalize(n)}

def main():
    if len(sys.argv) != 2:
        sys.exit('Kasutus: python ERM_massvastendus_geonames.py ERM_kulade_massvastenduse_tooleht_v20.csv')
    source = Path(sys.argv[1]).expanduser().resolve()
    if not source.is_file():
        sys.exit(f'Sisendfaili ei leitud: {source}')
    with source.open(encoding='utf-8-sig', newline='') as f:
        work = list(csv.DictReader(f))
    required = {'country', 'modern_region', 'modern_district_or_municipality', 'modern_settlement', 'museaale'}
    if not work or not required.issubset(work[0]):
        sys.exit(f'Töölehe veerud ei klapi; vaja: {sorted(required)}')
    folder = source.parent / 'geonames_cache'
    folder.mkdir(exist_ok=True)
    a1, a2 = load_admin(folder)
    codes = sorted({COUNTRIES[x['country'].strip()] for x in work if x['country'].strip() in COUNTRIES})
    target_names = {normalize(r['modern_settlement']) for r in work if normalize(r['modern_settlement'])}
    index = defaultdict(list)
    for code in codes:
        try:
            path = download(code + '.zip', folder)
        except Exception as exc:
            print(f'Viga {code}.zip allalaadimisel: {exc}', file=sys.stderr)
            continue
        total = kept = 0
        with zipfile.ZipFile(path) as archive:
            member = code + '.txt'
            with archive.open(member) as binary:
                for line in io.TextIOWrapper(binary, encoding='utf-8', errors='replace'):
                    fields = line.rstrip('\n').split('\t')
                    if len(fields) < 18 or fields[6] != 'P':
                        continue
                    total += 1
                    nms = names_of(fields)
                    matching = nms & target_names
                    if matching:
                        item = {
                            'geonames_id': fields[0], 'geonames_name': fields[1],
                            'latitude': fields[4], 'longitude': fields[5],
                            'country_code': code,
                            'feature_code': fields[7],
                            'admin1_name': a1.get(f'{code}.{fields[10]}', ''),
                            'admin2_name': a2.get(f'{code}.{fields[10]}.{fields[11]}', ''),
                            'population': fields[14] or '0',
                        }
                        for key in matching:
                            index[(code, key)].append(item)
                        kept += 1
        print(f'{code}: {total} asulakirjet; {kept} nimekattuvusega kandidaati', flush=True)
    output = source.with_name(source.stem + '_GeoNames_kandidaadid.csv')
    count_with = 0
    with output.open('w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ['toolehe_rida','country','modern_region','modern_district_or_municipality','modern_settlement',
                      'museaale','kandidaate_kokku','kandidaadi_jrk','geonames_id','geonames_name','latitude','longitude',
                      'country_code','admin1_name','admin2_name','feature_code','population','regiooni_nime_sarnasus',
                      'rajooni_nime_sarnasus','kontrolli_staatus','allika_url']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rowno, row in enumerate(work, 1):
            code = COUNTRIES.get(row['country'].strip())
            key = normalize(row['modern_settlement'])
            candidates = index.get((code, key), []) if code else []
            def similarity(src, dest):
                if not src or not dest:
                    return 0.0
                return difflib.SequenceMatcher(None, normalize(src), normalize(dest)).ratio()
            ranked = sorted(candidates, key=lambda x: (
                similarity(row['modern_region'], x['admin1_name']) + similarity(row['modern_district_or_municipality'], x['admin2_name']),
                int(x['population']) if x['population'].isdigit() else 0), reverse=True)
            if ranked:
                count_with += 1
            for rank, candidate in enumerate(ranked[:20] or [None], 1):
                item = {k: row.get(k, '') for k in ['country','modern_region','modern_district_or_municipality','modern_settlement','museaale']}
                item.update({'toolehe_rida': rowno, 'kandidaate_kokku': len(ranked), 'kandidaadi_jrk': rank if candidate else '',
                             'kontrolli_staatus': 'KÄSITSI KONTROLLIDA' if candidate else 'EI LEITUD'})
                if candidate:
                    item.update(candidate)
                    item['regiooni_nime_sarnasus'] = round(similarity(row['modern_region'], candidate['admin1_name']), 3)
                    item['rajooni_nime_sarnasus'] = round(similarity(row['modern_district_or_municipality'], candidate['admin2_name']), 3)
                    item['allika_url'] = 'https://www.geonames.org/' + candidate['geonames_id']
                writer.writerow(item)
    print(f'Valmis: {output.name}')
    print(f'Nimekattuvusega kombinatsioone: {count_with} / {len(work)}')
    print('NB! Need on KANDIDAADID. Museaalide koordinaate see programm ei muuda.')

if __name__ == '__main__':
    main()
