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
    if isinstance(data,dict):sample={k:(v[:1] if isinstance(v,list) else dict(list(v.items())[:1]) if isinstance(v,dict) else v) for k,v in data.items()};shape={k:len(v) if isinstance(v,(list,dict)) else type(v).__name__ for k,v in data.items()}
    else:sample=data[:1];shape={'array':len(data)}
    return {'id':name,'url':url,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'shape':shape},sample
manifest={'generated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'repository':'https://github.com/team-mirai-volunteer/rs-vis','commit':COMMIT,'official':'https://rssystem.go.jp/','basis':'公開保存版・加工済みデータ。公式最新版との再照合は未了。元CSV・APIの全項目を網羅したものではありません。','files':[],'failures':[]};samples={}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures={pool.submit(download,n):n for n in FILES}
    for future in concurrent.futures.as_completed(futures):
        n=futures[future]
        try:r,s=future.result();manifest['files'].append(r);samples[n]=s;print('OK',n,r['shape'],flush=True)
        except Exception as e:manifest['failures'].append({'id':n,'error':str(e)});print('FAILED',n,str(e),flush=True)
manifest['files'].sort(key=lambda x:x['id']);save(ROOT/'manifest.json',manifest)
save(ROOT/'inspection.json',samples)
if manifest['failures']:raise SystemExit('Snapshot files missing')
