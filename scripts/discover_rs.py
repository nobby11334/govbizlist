"""Inspect public frontend assets for the currently advertised CSV distribution."""
import urllib.request,urllib.parse,re,collections
base='https://rssystem.go.jp'
queue=collections.deque([base+'/download-csv/2025']);seen=set()
while queue and len(seen)<35:
    url=queue.popleft()
    if url in seen:continue
    seen.add(url)
    try:
        with urllib.request.urlopen(url,timeout=30) as r:
            b=r.read();text=b.decode('utf-8');print('ASSET',url,r.status,r.headers.get('Content-Type'),len(b),text[:100],flush=True)
        refs=re.findall(r'(?:src=["\']|from["\']|import\(["\']|["\'])([^"\'\s<>]+\.js)(?:["\'])',text)
        for ref in refs:
            target=urllib.parse.urljoin(url,ref)
            if target.startswith(base) and target not in seen:queue.append(target)
        matches=list(re.finditer(r'\.zip|ndjson|download-csv|downloadCsv|csvFile|csv-file|csv_file|/api/',text,re.I))
        for m in matches[:45]:print('CONTEXT',text[max(0,m.start()-180):m.end()+250],flush=True)
    except Exception as e:print('ERROR',url,str(e),flush=True)
