"""Preserve additional budget-subject linkage and contract-method evidence."""
import pathlib,json,gzip,urllib.request,hashlib,datetime
root=pathlib.Path(__file__).resolve().parents[1]/'data'/'evidence';root.mkdir(parents=True,exist_ok=True)
commit='92721f7e50ebdd7fa38c29ab36ceb0c4487e182e';files=[]
for name in ['mof-rs-kou-moku-linkage-2025','mof-rs-kou-moku-linkage-2026','contract-methods-2026']:
    url=f'https://raw.githubusercontent.com/team-mirai-volunteer/rs-vis/{commit}/public/data/{name}.json.gz'
    with urllib.request.urlopen(url,timeout=90) as r:raw=r.read()
    data=json.loads(gzip.decompress(raw))
    (root/(name+'.json.gz')).write_bytes(raw)
    f={'id':name,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'metadata':data.get('metadata') if isinstance(data,dict) else None}
    files.append(f);print(name,'links',len(data.get('links',[])),'records',len(data),flush=True)
(root/'manifest.json').write_text(json.dumps({'downloadedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'basis':'加工済み保存版の予算科目対応・契約方式。名寄せ・按分・推定を含み、公式最新版との照合は未了。','commit':commit,'files':files},ensure_ascii=False),encoding='utf-8')
