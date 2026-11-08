"""Check official ZIPs; preserve dated corrections separately from prior snapshots."""
import pathlib,json,urllib.request,urllib.parse,hashlib,datetime,concurrent.futures,zipfile,io,csv
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'data/official-checks';stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
rs=json.loads((ROOT/'data/rs/manifest.json').read_text());off=json.loads((ROOT/'data/official/manifest.json').read_text())
tasks=[(2024,f['code'],f['name'].replace('.csv','.zip'),f['sha256']) for f in rs['files']]+[(2025,f['code'],f['csv'].replace('.csv','.zip'),f['sha256']) for f in off['files']]
def check(t):
 y,code,name,prior=t;url=f'https://rssystem.go.jp/files/{y}/rs/'+urllib.parse.quote(name)
 with urllib.request.urlopen(url,timeout=120) as r:raw=r.read()
 assert raw[:2]==b'PK','Non-ZIP response'
 digest=hashlib.sha256(raw).hexdigest();f={'year':y,'code':code,'url':url,'sha256':digest,'priorSha256':prior,'changed':digest!=prior};payload=None
 if f['changed']:
  assert y==2024,'New 2025 data requires explicit schema review'
  z=zipfile.ZipFile(io.BytesIO(raw));names=[n for n in z.namelist() if n.endswith('.csv')];assert len(names)==1
  rows=list(csv.reader(io.StringIO(z.read(names[0]).decode('utf-8-sig'))));headers=rows.pop(0);rows=[r for r in rows if any(r)]
  assert all(len(r)==len(headers) for r in rows) and '予算事業ID' in headers and len(rows)>100
  assert all(r[headers.index('事業年度')]=='2024' and r[headers.index('予算事業ID')] for r in rows)
  f.update({'file':stamp+'/'+name,'headers':headers,'rows':len(rows),'columns':len(headers),'csv':names[0]});payload=raw
 print('CSV',y,code,'changed',f['changed'],flush=True)
 return f,payload
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(check,tasks))
m={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':[f for f,b in results],'scope':'公式ZIP30ファイルのハッシュ照合。差分原ZIPは別途保存し、従来原資料を保持。'}
for f,b in results:
 if b:
  p=OUT/f['file'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
(OUT/stamp).mkdir(parents=True,exist_ok=True)
for p in (OUT/stamp/'manifest.json',OUT/'manifest.json'):p.write_text(json.dumps(m,ensure_ascii=False,indent=2))
