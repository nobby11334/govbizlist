"""Check catalogue/source coverage and every navigable reference before publication."""
import json,gzip,pathlib
root=pathlib.Path(__file__).resolve().parents[1]/'data'/'catalogue'
def read(f):
    b=(root/f).read_bytes();return json.loads(gzip.decompress(b) if f.endswith('.gz') else b)
m=read('meta.json');roots={r['id'] for r in m['roots']};known={};source_rows=0;official_rows=0
for y,count in m['counts'].items():
    index=read('index-'+y+'.json.gz');assert len(index)==count
    assert len({p['id'] for p in index})==count
    shards={}
    for p in index:
        assert p['root'] in roots
        if p['file'] not in shards:shards[p['file']]=read(p['file'])
        record=shards[p['file']][p['offset']]
        assert record['id']==p['id'] and record['year']==int(y) and record['root']==p['root']
        assert bool(record['name'])
        known[(int(y),p['id'])]=p['root']
        if y=='2025':official_rows+=sum(len(v) for v in record.get('officialTables',{}).values())
        if y=='2024':source_rows+=sum(len(v) for v in record['tables'].values())
        if y=='2025':
            for point in record['budget']:
                for k in ('initialBudget','totalBudget','executedAmount'):assert point.get(k) is None or isinstance(point[k],(int,float))
    for k,n in m['coverage'][y].items():assert 0<=n<=count
expected=sum(f['rows'] for f in m['sources']['csv']['files']);assert source_rows==expected,(source_rows,expected)
if m['sources'].get('official'):assert official_rows==sum(f['rows'] for f in m['sources']['official']['files'])
orgs=read('organizations.json.gz');assert len({o['id'] for o in orgs})==len(orgs)
for o in orgs:
    for y,pid,rid in o['refs']:assert known[(y,pid)]==rid
for f in read('funds.json.gz')['funds']:assert f['root'] in roots
for s in read('segments.json.gz')['segments']:assert s['root'] in roots
print(json.dumps({'programs':sum(m['counts'].values()),'originalCsvRows':source_rows,'directOfficialRows2025':official_rows,'organizations':len(orgs),'roots':len(roots),'allReferencesValid':True}),flush=True)

if m['sources'].get('live'):
    import hashlib
    live=m['sources']['live']; live_root=root.parent/'live'
    for f in live['files']:
        raw=(live_root/f['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==f['sha256']
        d=json.loads(gzip.decompress(raw));rows=d['records']
        assert len(rows)==f['count']==len({v['id'] for v in rows})
        assert all(v['fiscal_year']==f['year'] and v['sheet_type']==f['type'] and v['name'] for v in rows)
        for page in d['pages']:
            if 'rawResponse' in page:assert hashlib.sha256(page['rawResponse'].encode()).hexdigest()==page['sha256']
        if f['type']=='RS':
            for v in rows:assert (f['year'],str(int(v['project_number']))) in known
    assert all((2026,str(int(v['projectNumber']))) in known for v in live['new2026'])
    print('Official inventories: all hashes, counts, years, uniqueness and search references valid')
