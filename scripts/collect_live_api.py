"""Collect public RS API inventories and raw sheet payloads, keeping provenance."""
import urllib.request,urllib.parse,json,pathlib,datetime,hashlib,gzip,time,concurrent.futures
ROOT=pathlib.Path(__file__).resolve().parents[1]/'data'/'rs-api';ROOT.mkdir(parents=True,exist_ok=True)
BASE='https://rssystem.go.jp/api/projects/'
def get(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'govbizlist-public-data/1.0'}),timeout=40) as r:
                raw=r.read()
                if 'json' not in r.headers.get('Content-Type',''):raise ValueError('Not JSON: '+raw[:100].decode(errors='replace'))
                data=json.loads(raw)
            time.sleep(.1)
            return {'url':url,'fetchedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'data':data}
        except Exception:
            if attempt==2:raise
            time.sleep(2**attempt)
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    b=json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
    if p.suffix=='.gz':p.write_bytes(gzip.compress(b,mtime=0))
    else:p.write_bytes(b)
manifest={'generated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':BASE,'datasets':[],'failures':[]}
for year in (2025,2026):
    for sheet in ('RS','KS','SS'):
        group=f'{year}-{sheet}';projects=[];page=1;expected=None
        try:
            while True:
                envelope=get(BASE+'?'+urllib.parse.urlencode({'sheet_type':sheet,'fiscal_year':year,'page':page,'page_size':1000}));d=envelope['data'];save(ROOT/group/f'list-{page}.json.gz',envelope)
                if not isinstance(d.get('results'),list) or not isinstance(d.get('count'),int):raise ValueError('Invalid list schema')
                if expected is not None and expected!=d['count']:raise ValueError('Inventory count changed')
                expected=d['count'];projects.extend(d['results']);print('LIST',group,len(projects),expected,flush=True)
                if not d.get('next'):break
                if not d['results'] or len(projects)>=expected:raise ValueError('Invalid pagination')
                page+=1
            if len(projects)!=expected or len({p['id'] for p in projects})!=expected:raise ValueError('Incomplete or duplicate inventory')
            save(ROOT/group/'projects.json',projects)
            print('SAMPLE',group,json.dumps(projects[:1],ensure_ascii=False)[:16000],flush=True)
            dataset={'id':group,'year':year,'sheet':sheet,'expected':expected,'listed':len(projects),'complete':0,'failures':[]}
            manifest['datasets'].append(dataset)
            # Full detail + all payment blocks and edges; no money or fields discarded.
            def collect(p):
                ident=p['id'];path=ROOT/group/'sheets'/f'{ident}.json.gz'
                if path.exists():
                    x=json.loads(gzip.decompress(path.read_bytes()))
                    if x.get('listUpdatedAt')==p.get('updated_at') and p.get('updated_at'):return True
                payload={'id':ident,'listUpdatedAt':p.get('updated_at'),'responses':{}}
                for endpoint in ('','payment-groups/','payment-edges/'):
                    key=endpoint.strip('/') or 'detail';envelope=get(BASE+ident+'/'+endpoint)
                    if key=='detail' and envelope['data'].get('id')!=ident:raise ValueError('Detail ID mismatch')
                    if key!='detail' and not isinstance(envelope['data'],list):raise ValueError('Invalid payment schema')
                    payload['responses'][key]=envelope
                save(path,payload);return True
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures={pool.submit(collect,p):p for p in projects}
                for future in concurrent.futures.as_completed(futures):
                    p=futures[future]
                    try:future.result();dataset['complete']+=1
                    except Exception as e:dataset['failures'].append({'id':p['id'],'error':str(e)})
                    if (dataset['complete']+len(dataset['failures']))%100==0:print('DETAIL',group,dataset['complete'],'/',expected,'failed',len(dataset['failures']),flush=True)
            dataset['status']='complete' if dataset['complete']==expected else 'partial'
            save(ROOT/'manifest.json',manifest);print('DONE',group,json.dumps(dataset),flush=True)
        except Exception as e:manifest['failures'].append({'id':group,'error':str(e)});print('FAILED',group,str(e),flush=True)
save(ROOT/'manifest.json',manifest)
if not manifest['datasets']:raise SystemExit('No public API inventories retrieved')
