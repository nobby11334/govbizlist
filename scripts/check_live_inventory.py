"""Stage complete official API inventories atomically; retain prior source histories."""
import urllib.request,urllib.parse,json,gzip,hashlib,pathlib,datetime,concurrent.futures
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'live'
BASE='https://rssystem.go.jp/api/projects/'
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'govbizlist-public-data/1.0'}),timeout=90) as r:
        raw=r.read();kind=r.headers.get('Content-Type','')
    if 'json' not in kind:raise ValueError('Expected JSON, received '+kind)
    return raw,json.loads(raw)
def pack(x):return gzip.compress(json.dumps(x,ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
def collect(pair):
    y,s=pair;page=1;records=[];pages=[];expected=None
    while True:
        url=BASE+'?'+urllib.parse.urlencode({'sheet_type':s,'fiscal_year':y,'page':page,'page_size':1000})
        raw,d=get(url)
        assert isinstance(d.get('results'),list) and isinstance(d.get('count'),int)
        if expected is not None:assert d['count']==expected,'Inventory changed during paging'
        expected=d['count'];rows=d['results'];records.extend(rows)
        pages.append({'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'response':d,'rawResponse':raw.decode('utf-8')})
        if not d.get('next'):break
        assert rows and len(records)<expected;page+=1
    assert len(records)==expected and len({d['id'] for d in records})==expected
    assert all(d['sheet_type']==s and d['fiscal_year']==y and d.get('is_published') is True for d in records)
    filename=f'{y}-{s}.json.gz';raw=pack({'pages':pages,'records':records})
    print('INVENTORY',y,s,expected,flush=True)
    return {'year':y,'type':s,'count':expected,'file':stamp+'/'+filename,'sha256':hashlib.sha256(raw).hexdigest(),'missingNames':sum(not d.get('name') for d in records)},raw,records
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for result in pool.map(collect,[(y,s) for y in (2025,2026) for s in ('RS','KS','SS')]):results.append(result)
old=json.loads(gzip.decompress((ROOT/'data/extended/rs-api-2026-details.json.gz').read_bytes()))
old_ids={d['id'] for d in old.values()};rs=next(r for f,b,r in results if f['year']==2026 and f['type']=='RS')
new=[d for d in rs if d['id'] not in old_ids];details={}
for d in new:
    url=BASE+d['id']+'/';raw,value=get(url)
    assert value['id']==d['id'] and value['fiscal_year']==2026 and value['sheet_type']=='RS'
    details[d['id']]={'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'data':value}
# No money conversion is made: preserve API numerical fields as original values.
manifest={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':BASE,'files':[f for f,b,r in results],'new2026':[{'id':d['id'],'projectNumber':d['project_number'],'name':d['name']} for d in new],'missingPrior2026':sorted(old_ids-{d['id'] for d in rs}),'scope':'公式一覧の全ページを直接保存。新規RS事業のみ詳細を取得。既存の支出先・成果・評価の全数再照合ではない。金額は原値を保持し、この一覧から合計しない。'}
# Publish only after every required inventory and new-detail request has passed.
for f,b,r in results:
    p=OUT/f['file'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
p=OUT/stamp/'new-details.json.gz';p.write_bytes(pack(details));manifest['details']={'file':stamp+'/new-details.json.gz','sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(OUT/stamp/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(json.dumps(manifest,ensure_ascii=False),flush=True)
