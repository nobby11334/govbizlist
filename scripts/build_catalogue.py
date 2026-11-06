"""Build institution-first catalogue, filling fields only from same-year source records."""
import json,gzip,pathlib,hashlib,datetime,collections,re
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'catalogue';OUT.mkdir(parents=True,exist_ok=True)
def load(p):
    b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def put(name,data):
    b=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();(OUT/name).write_bytes(gzip.compress(b,mtime=0) if name.endswith('.gz') else b)
def ext(name):return load(ROOT/'data'/'extended'/(name+'.json.gz'))
def clean(v):return re.sub(r'\s+','',str(v or ''))
def key(s):return hashlib.sha256(s.encode()).hexdigest()[:14]
rs=load(ROOT/'data'/'rs'/'manifest.json');ex=load(ROOT/'data'/'extended'/'manifest.json')
programs={};parent={};root_labels={};roots={};headers={};raw_counts=collections.Counter()
# Read every original CSV row. Same-year facts are never patched with later/earlier amounts.
for f in sorted(rs['files'],key=lambda x:x['code']):
    headers[f['code']]=f['headers']
    for shard in f['shards']:
        table=load(ROOT/'data'/'rs'/shard)
        for row in table['rows']:
            d=dict(zip(table['headers'],row));pid=d.get('予算事業ID')
            if not pid:continue
            p=programs.setdefault((2024,str(pid)),{'id':str(pid),'year':2024,'name':d.get('事業名',''),'ministry':d.get('府省庁',''),'departments':[],'tables':{}})
            p['tables'].setdefault(f['code'],[]).append(row);raw_counts[f['code']]+=1
            if f['code']=='1-1':
                m=d.get('府省庁','');r=d.get('所管府省庁') or m
                if m and r:parent[clean(m)]=r;root_labels[clean(r)]=r
                path=[d.get(x,'') for x in ['府省庁','局・庁','部','課','室','班','係']];path=[v for v in path if v]
                if path and path not in p['departments']:p['departments'].append(path)
base=ext('rs2025-project-details');budget=ext('rs2025-project-budget-history');outcomes=ext('rs2025-project-outcomes');indicators=ext('rs2025-project-indicators');contracts=ext('contract-methods-2025');flows=ext('subcontracts-2025')
for pid,d in base.items():
    graph=flows.get(pid,{})
    bureau=graph.get('bureau') or d.get('bureau') or ''
    path=[d.get('ministry') or graph.get('ministry') or '']+[s.strip() for s in bureau.split('/') if s.strip()]
    programs[(2025,str(pid))]={'id':str(pid),'year':2025,'name':d.get('projectName') or graph.get('projectName') or '', 'ministry':d.get('ministry') or graph.get('ministry') or '', 'departments':[path] if any(path) else [],'overview':d,'budget':budget.get('projects',{}).get(pid,[]),'outcomes':outcomes.get(pid),'indicators':indicators.get(pid),'contracts':contracts.get(pid,[]),'flows':graph}
for pid,d in ext('rs-api-2026-details').items():
    programs[(2026,str(pid))]={'id':str(pid),'year':2026,'name':d.get('name',''),'ministry':d.get('ministry',''),'departments':[[d['ministry']]] if d.get('ministry') else [],'api':d}
funds=ext('funds');fund_payments=ext('fund-payments');segments=ext('agency-segments');fund_by_pid=collections.defaultdict(list);segment_by_pid=collections.defaultdict(list)
for f in funds['funds']:
    for y in f['years']:
        for pid in f.get('relatedPids',[]):fund_by_pid[(y['sheetYear'],str(pid))].append(f['key'])
for s in segments['segments']:
    for pid in s.get('pids',[]):segment_by_pid[(s['sheetYear'],str(pid))].append(s['id'])
def root_for(m):
    name=parent.get(clean(m),m) or '所管の記載なし';rid=key(name)
    roots.setdefault(rid,{'id':rid,'name':name,'years':{},'members':set()});roots[rid]['members'].add(m or name)
    return rid
def nonempty(v):return v not in (None,'',[],{})
indexes={2024:[],2025:[],2026:[]};coverage={};counts={}
for year in indexes:
    ordered=sorted([v for (y,p),v in programs.items() if y==year],key=lambda x:(x['ministry'],int(x['id']) if x['id'].isdigit() else 0))
    counters=collections.Counter()
    for start in range(0,len(ordered),40):
        chunk=ordered[start:start+40];filename=f'programs-{year}-{start//40}.json.gz'
        for offset,p in enumerate(chunk):
            rid=root_for(p['ministry']);p['root']=rid;p['funds']=list(dict.fromkeys(fund_by_pid.get((year,p['id']),[])));p['segments']=list(dict.fromkeys(segment_by_pid.get((year,p['id']),[])))
            if year==2024:
                def rowdict(code):return [dict(zip(headers[code],r)) for r in p['tables'].get(code,[])]
                overview=rowdict('1-2');overview=overview[0] if overview else {}
                flags={'overview':bool(overview.get('事業の概要') or overview.get('事業の目的')),'budget':any(any(r.get(k) not in ('',None) for k in ['当初予算（合計）','執行額（合計）']) for r in rowdict('2-1')),'outcomes':any(r.get('アクティビティ／活動目標／成果目標') or r.get('活動指標／成果指標') for r in rowdict('3-1')),'payments':any(r.get('支出先名') for r in rowdict('5-1')),'evaluation':any(any(v for k,v in r.items() if k not in ('シート種別','事業年度','予算事業ID','事業名','府省庁の建制順','政策所管府省庁','府省庁','局・庁','部','課','室','班','係')) for r in rowdict('4-1')),'funding':bool(p['tables'].get('2-2'))}
            elif year==2025:
                flags={'overview':bool(p['overview'].get('overview') or p['overview'].get('purpose')),'budget':any(any(v is not None for k,v in r.items() if k in ('initialBudget','totalBudget','executedAmount')) for r in p['budget']),'outcomes':any(i.get('goal') or i.get('indicator') for i in (p.get('outcomes') or p.get('indicators') or {}).get('indicators',[])),'payments':bool(p['flows'].get('blocks')),'evaluation':any(v for v in (p.get('outcomes') or {}).get('review',{}).values()),'funding':bool(p['flows'].get('accountCategory'))}
            else:
                a=p['api'];flags={'overview':bool(a.get('overview') or a.get('purpose')),'budget':a.get('execution') is not None,'outcomes':False,'payments':bool(a.get('groups')),'evaluation':False,'funding':False}
            p['coverage']=flags
            for k,v in flags.items():counters[k]+=int(v)
            p['gaps']=[k for k,v in flags.items() if not v]
            indexes[year].append({'id':p['id'],'year':year,'root':rid,'ministry':p['ministry'],'name':p['name'],'departments':p['departments'],'coverage':flags,'file':filename,'offset':offset,'funds':p['funds'],'segments':p['segments']})
            roots[rid]['years'][str(year)]=roots[rid]['years'].get(str(year),0)+1
        put(filename,chunk)
    coverage[str(year)]={'total':len(ordered),**dict(counters)};counts[str(year)]=len(ordered);put(f'index-{year}.json.gz',indexes[year])
for f in funds['funds']:f['root']=root_for(f['ministry'])
for s in segments['segments']:s['root']=root_for(s['ministry'])
for r in roots.values():r['members']=sorted(r['members'])
orgs={}
def add_org(name,corp='',ref=None,fund=None,segment=None,other=False):
    name=str(name or '').strip();corp=str(corp or '').strip()
    if not name or other or re.match(r'^(その他|其他|不明|非公表|複数の|個人等)$',name):return
    valid=bool(re.fullmatch(r'\d{13}',corp)) and len(set(corp))>1
    if valid:
        total=sum(int(n)*(1 if i%2==0 else 2) for i,n in enumerate(reversed(corp[1:])))
        valid=int(corp[0])==9-total%9
    ident='cn:'+corp if valid else 'name:'+clean(name)
    o=orgs.setdefault(ident,{'id':key(ident),'name':name,'corporateNumber':corp if valid else None,'aliases':set(),'refs':set(),'funds':set(),'segments':set()})
    o['aliases'].add(name)
    if ref:o['refs'].add(ref)
    if fund:o['funds'].add(fund)
    if segment:o['segments'].add(segment)
for (year,pid),p in programs.items():
    ref=(year,pid,p['root'])
    if year==2024:
        for code in ('5-1','5-3','5-4'):
            for row in p['tables'].get(code,[]):
                d=dict(zip(headers[code],row));add_org(d.get('支出先名') or d.get('契約先名（国庫債務負担行為等による契約）'),d.get('法人番号') or d.get('契約先の法人番号（国庫債務負担行為等による契約）'),ref,other=d.get('その他支出先')=='TRUE')
    if year==2025:
        for b in p['flows'].get('blocks',[]):
            for o in b.get('recipients',[]):add_org(o.get('name'),o.get('corporateNumber'),ref)
    if year==2026:
        for g in p['api'].get('groups',[]):
            for o in g.get('payments',[]):add_org(o.get('name'),o.get('corporate_number'),ref,other=o.get('is_others',False))
for f in funds['funds']:
    add_org(f.get('owner'),fund=f['key'])
    for y,groups in fund_payments.get('funds',{}).get(f['key'],{}).items():
        for g in groups:
            for o in g.get('payees',[]):add_org(o.get('name'),o.get('corporateNumber'),fund=f['key'],other=o.get('others',False))
for s in segments['segments']:
    add_org(s['agency'],segment=s['id'])
    for g in s.get('groups',[]):
        for o in g.get('payees',[]):add_org(o.get('name'),o.get('corporateNumber'),segment=s['id'],other=o.get('others',False))
org_index=[]
for o in orgs.values():
    for field in ('aliases','refs','funds','segments'):o[field]=sorted(o[field])
    org_index.append(o)
org_index.sort(key=lambda o:o['name']);put('organizations.json.gz',org_index)
meta={'builtAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'counts':counts,'organizationCount':len(org_index),'coverage':coverage,'roots':sorted(roots.values(),key=lambda r:r['name']),'headers':headers,'sources':{'csv':rs,'extended':ex},'notes':['2024年版は公開保存された原CSVの全行を事業単位で接続。','2025・2026年版は加工済みの公開保存版。2026年版の成果・評価・財源はこの保存版に未収録。','別年度の値で空欄を埋めず、関連年度の資料として接続。','支出・契約・基金残高・返納や多段階の支出先を合算しない。']}
put('meta.json',meta);put('funds.json.gz',funds);put('fund-payments.json.gz',fund_payments);put('segments.json.gz',segments)
# Compact representative schemas for verifying complete rendering, never a data cap.
put('schema-samples.json',{n:{'keys':list(d.keys()),'sample':d} for n,d in [('overview',next(iter(base.values()))),('budget',next(iter(budget['projects'].values()))[0]),('outcomes',next(iter(outcomes.values()))),('flow',next(iter(flows.values())))]})
assert len(indexes[2025])==len(base) and len(indexes[2026])==len(ext('rs-api-2026-details'))
print(json.dumps({'counts':counts,'organizationCount':len(org_index),'coverage':coverage,'roots':len(roots),'csvRows':sum(raw_counts.values())},ensure_ascii=False),flush=True)
