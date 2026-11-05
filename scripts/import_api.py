"""Import pinned public RS-derived snapshots, without claiming current API validation."""
import urllib.request,json,gzip,pathlib,hashlib,datetime,concurrent.futures
ROOT=pathlib.Path(__file__).resolve().parents[1]/'data'/'extended';ROOT.mkdir(parents=True,exist_ok=True)
COMMIT='92721f7e50ebdd7fa38c29ab36ceb0c4487e182e'
FILES=['rs2025-project-details','rs2025-project-budget-history','rs2025-project-indicators','rs2025-project-outcomes','contract-methods-2025','subcontracts-2025','recipient-index-2025','rs-api-2026-details','rs-api-2026-provenance','funds','fund-payments','agency-segments']
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
def download(name):
    url=f'https://raw.githubusercontent.com/team-mirai-volunteer/rs-vis/{COMMIT}/public/data/{name}.json.gz'
    with urllib.request.urlopen(url,timeout=90) as r:b=r.read()
    data=json.loads(gzip.decompress(b));(ROOT/(name+'.json.gz')).write_bytes(b)
    if isinstance(data,dict):sample={k:(v[:1] if isinstance(v,list) else dict(list(v.items())[:1]) if isinstance(v,dict) else v) for k,v in list(data.items())[:3]};shape={k:len(v) if isinstance(v,(list,dict)) else type(v).__name__ for k,v in data.items()}
    else:sample=data[:1];shape={'array':len(data)}
    return {'id':name,'url':url,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'shape':shape},sample,data
manifest={'generated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'repository':'https://github.com/team-mirai-volunteer/rs-vis','commit':COMMIT,'official':'https://rssystem.go.jp/','basis':'公開保存版・加工済みデータ。公式最新版との再照合は未了。元CSV・APIの全項目を網羅したものではありません。','files':[],'failures':[]};samples={};all_data={}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures={pool.submit(download,n):n for n in FILES}
    for future in concurrent.futures.as_completed(futures):
        n=futures[future]
        try:r,s,data=future.result();manifest['files'].append(r);samples[n]=s;all_data[n]=data;print('OK',n,'top-level keys',len(r['shape']),flush=True)
        except Exception as e:manifest['failures'].append({'id':n,'error':str(e)});print('FAILED',n,str(e),flush=True)
# Index every record in each preserved dataset; all fields remain in compressed shards.
base=all_data.get('rs2025-project-details',{})
funds={f['key']:f for f in all_data.get('funds',{}).get('funds',[])}
def entries(name,data):
    if name=='funds':return [(f['key'],f) for f in data['funds']]
    if name=='fund-payments':return list(data['funds'].items())
    if name=='agency-segments':return [(f['id'],f) for f in data['segments']]
    if name=='recipient-index-2025':
        v=data['recipients'];return list(v.items()) if isinstance(v,dict) else [(str(i),f) for i,f in enumerate(v)]
    if name=='rs2025-project-budget-history':return list(data['projects'].items())
    if name=='rs-api-2026-provenance':return list(enumerate(data['sources'])) if isinstance(data['sources'],list) else list(data['sources'].items())
    return list(data.items())
def names(value):
    found=[]
    if isinstance(value,dict):
        for k,v in value.items():
            if isinstance(v,str) and any(w in k.lower() for w in ('name','agency','owner','corporate','ministry')):found.append(v)
            elif isinstance(v,(dict,list)):found.extend(names(v))
    elif isinstance(value,list):
        for v in value:found.extend(names(v))
    return list(dict.fromkeys(found))
for file in manifest['files']:
    name=file['id'];data=all_data[name];items=entries(name,data);index=[];file['records']=len(items);file['metadata']=data.get('metadata') if isinstance(data,dict) else None
    for start in range(0,len(items),100):
        chunk=items[start:start+100];filename=f'{name}-{start//100}.json.gz'
        payload=json.dumps([{'key':str(k),'data':v} for k,v in chunk],ensure_ascii=False,separators=(',',':')).encode()
        (ROOT/filename).write_bytes(gzip.compress(payload,mtime=0))
        for offset,(key,value) in enumerate(chunk):
            record=value if isinstance(value,dict) else {};reference=base.get(str(key),{});fund=funds.get(str(key),{})
            title=record.get('projectName') or record.get('name') or fund.get('name') or reference.get('projectName') or str(key)
            ministry=record.get('ministry') or fund.get('ministry') or reference.get('ministry') or ''
            year=record.get('sheetYear') or (2026 if '2026' in name else 2025 if '2025' in name else '')
            search=' '.join(names(value)+names(fund))
            index.append({'key':str(key),'title':title,'ministry':ministry,'year':year,'search':search,'file':filename,'offset':offset})
    save(ROOT/f'index-{name}.json',index)
    print('INDEX',name,len(index),flush=True)
manifest['files'].sort(key=lambda x:x['id']);save(ROOT/'manifest.json',manifest)
save(ROOT/'inspection.json',samples)
if manifest['failures']:raise SystemExit('Snapshot files missing')
