"""Import complete official RS CSV files; retain all rows and original columns."""
import csv,io,json,zipfile,urllib.request,urllib.parse,hashlib,re,datetime,pathlib,concurrent.futures
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'rs';OUT.mkdir(parents=True,exist_ok=True)
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'govbizlist public-data-import/1.0'}),timeout=120) as r:return r.read()
def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
urls=set()
for year in (2024,2025):
    for stem in ('1-1_基本情報_組織情報','1-2_基本情報_事業概要等','5-1_支出先_支出情報'):
        code,rest=stem.split('_',1);urls.add(f'https://rssystem.go.jp/files/{year}/rs/{code}_RS_{year}_{rest}.zip')
    # Discover every ZIP advertised by the official download page and its JS bundles.
    try:
        page=get(f'https://rssystem.go.jp/download-csv/{year}').decode('utf-8')
        print('OFFICIAL PAGE',year,page[:16000],flush=True)
        texts=[page]
        assets=re.findall(r'<script[^>]+src=["\']([^"\']+)',page)
        for asset in assets:
            try:texts.append(get(urllib.parse.urljoin('https://rssystem.go.jp',asset)).decode('utf-8'))
            except Exception:pass
        for text in texts:
            for link in re.findall(r'(?:https://rssystem.go.jp)?/files/[^\s"\'<>`]+?\.zip',text):
                if '/'+str(year)+'/' in link:urls.add(urllib.parse.urljoin('https://rssystem.go.jp',link))
    except Exception as exc:print('Discovery:',year,str(exc),flush=True)
manifest={'generated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'https://rssystem.go.jp/download-csv','years':[2024,2025],'files':[],'failures':[],'scope':'取得できた公式CSVは全行・全列を保持。全国の全支払・全再委託先の網羅ではありません。'}
projects=[];payees=[];ministries=set()
def task(url):
    raw=get(urllib.parse.quote(url,safe=':/%'))
    if not raw.startswith(b'PK'):raise ValueError('Non-ZIP response: '+raw[:1800].decode('utf-8',errors='replace'))
    z=zipfile.ZipFile(io.BytesIO(raw));result=[]
    for entry in z.namelist():
        if not entry.lower().endswith('.csv'):continue
        b=z.read(entry)
        for encoding in ('utf-8-sig','cp932'):
            try:text=b.decode(encoding);break
            except UnicodeDecodeError:continue
        rows=list(csv.reader(io.StringIO(text)))
        while rows and not any(rows[0]):rows.pop(0)
        if not rows:continue
        headers=rows.pop(0);rows=[r for r in rows if any(r)]
        result.append((entry,headers,rows,encoding))
    return url,raw,result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures={pool.submit(task,u):u for u in sorted(urls)}
    for future in concurrent.futures.as_completed(futures):
        url=futures[future]
        try:url,raw,tables=future.result()
        except Exception as exc:manifest['failures'].append({'url':url,'error':str(exc)});print('FAILED',url,str(exc),flush=True);continue
        year=int(re.search(r'/files/(\d+)/',url)[1]);code=re.search(r'/rs/([^_]+)',url)[1]
        for ti,(name,headers,rows,enc) in enumerate(tables):
            base=f'{year}-{code}-{ti}';shards=[]
            for start in range(0,len(rows),1500):
                filename=f'{base}-{start//1500}.json';dump(OUT/filename,{'headers':headers,'rows':rows[start:start+1500]});shards.append(filename)
            record={'id':base,'year':year,'code':code,'url':url,'name':name,'encoding':enc,'sha256':hashlib.sha256(raw).hexdigest(),'rows':len(rows),'columns':len(headers),'headers':headers,'shards':shards};manifest['files'].append(record)
            print(year,code,len(rows),headers,flush=True)
            def col(*names):
                return next((i for n in names for i,h in enumerate(headers) if h==n),None)
            def val(row,i):return row[i] if i is not None and i<len(row) else ''
            ministry=col('府省庁','府省庁名');title=col('事業名','事業名称');pid=col('予算事業ID','事業ID','事業番号');recipient=col('支出先名','支出先','支出先の名称');corp=col('法人番号')
            for ri,row in enumerate(rows):
                m=val(row,ministry);ministries.add(m)
                item=[val(row,title),m,val(row,pid),year,base,ri//1500,ri%1500]
                if code=='1-2':projects.append(item)
                if code=='5-1':
                    # Keep each record separately. Missing/dummy corporation IDs never merge entities.
                    payees.append([val(row,recipient),val(row,corp)]+item)
        print('OK',url,flush=True)
manifest['files'].sort(key=lambda x:x['id']);manifest['ministries']=sorted(ministries-{''});manifest['projectRows']=len(projects);manifest['payeeRows']=len(payees)
# One compact index per year; every raw row is lazy-loaded from its source shard.
for year in (2024,2025):
    dump(OUT/f'projects-{year}.json',[r for r in projects if r[3]==year]);dump(OUT/f'payees-{year}.json',[r for r in payees if r[5]==year])
dump(OUT/'manifest.json',manifest)
required={(y,c) for y in (2024,2025) for c in ('1-1','1-2','5-1')}
actual={(f['year'],f['code']) for f in manifest['files']}
if not required<=actual:raise SystemExit('Required datasets missing: '+str(required-actual))
if not payees or not any(r[0] for r in payees):raise SystemExit('Payee name schema not recognized; inspect headers')
