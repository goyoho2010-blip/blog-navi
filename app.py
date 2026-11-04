import os, re, io, csv, json, sqlite3, html, hashlib, zipfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlparse
import requests
import streamlit as st

st.set_page_config(page_title='블로그 NAVI | 천명의선택', page_icon='🧭', layout='wide')
st.markdown('''<style>.block-container{padding-top:1.6rem;max-width:1250px}h1,h2,h3{letter-spacing:-.04em}div[data-testid="stMetric"]{border:1px solid #dfebf0;padding:14px;border-radius:12px}</style>''',unsafe_allow_html=True)
APP_DIR=Path(__file__).parent
DB_PATH=Path(os.getenv('BLOG_NAVI_DB', str(APP_DIR/'data'/'blog_navi.sqlite3')))
DB_PATH.parent.mkdir(parents=True,exist_ok=True)
BRANDS={'네이버 입시':'https://blog.naver.com/goyoho','네이버 경제':'https://blog.naver.com/lykeion1','티스토리':'https://goyoho2000.tistory.com'}
TOPICS=['2028 대입','고교학점제','5등급제 내신','대학별 입학전형','학생부종합전형','모의고사 해석','진로·학과 탐색']
CTA={'공식 홈페이지':'https://choice1000.com','진로NAVI':'https://choice1000-career-navi.streamlit.app/','입시NAVI':'https://1000premium-mod5qgreanjrs2uvhfquad.streamlit.app/'}
STATUS=['아이디어','작성 중','검수 대기','수정 필요','승인','예약 등록','게시 완료']

def conn():
    c=sqlite3.connect(str(DB_PATH),timeout=20)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('''CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, channel TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', keywords TEXT NOT NULL DEFAULT '', sources TEXT NOT NULL DEFAULT '', claims TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT '아이디어', publish_at TEXT DEFAULT '', published_url TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY AUTOINCREMENT, post_id INTEGER NOT NULL, recorded_at TEXT NOT NULL, impressions INTEGER NOT NULL DEFAULT 0, clicks INTEGER NOT NULL DEFAULT 0, visitors INTEGER NOT NULL DEFAULT 0, inquiries INTEGER NOT NULL DEFAULT 0, revenue REAL NOT NULL DEFAULT 0, UNIQUE(post_id,recorded_at))''')
    c.commit();return c

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def all_posts():
    with conn() as c: return [dict(r) for r in c.execute('SELECT * FROM posts ORDER BY updated_at DESC,id DESC')]
def get_post(pid):
    with conn() as c:
        r=c.execute('SELECT * FROM posts WHERE id=?',(int(pid),)).fetchone()
        return dict(r) if r else None

def save(post,pid=None):
    fields=['topic','channel','title','body','keywords','sources','claims','status','publish_at','published_url']
    values=[post.get(k,'') for k in fields];ts=now()
    with conn() as c:
        if pid:
            c.execute('UPDATE posts SET '+','.join(f'{k}=?' for k in fields)+',updated_at=? WHERE id=?',values+[ts,int(pid)])
            return int(pid)
        cur=c.execute('INSERT INTO posts('+','.join(fields)+',created_at,updated_at) VALUES('+','.join(['?']*(len(fields)+2))+')',values+[ts,ts]);return cur.lastrowid

def delete(pid):
    with conn() as c:
        c.execute('DELETE FROM metrics WHERE post_id=?',(pid,));c.execute('DELETE FROM posts WHERE id=?',(pid,))

def load_api_key():
    try: return st.secrets.get('OPENAI_API_KEY','') or os.getenv('OPENAI_API_KEY','')
    except Exception: return os.getenv('OPENAI_API_KEY','')

def ai_draft(topic,channel,keywords,sources,model):
    key=load_api_key()
    if not key: raise ValueError('OPENAI_API_KEY가 설정되지 않았습니다. 아래의 기본 초안 생성 기능을 이용할 수 있습니다.')
    instructions='''당신은 한국 대입 진학 컨설팅 분야의 전문 편집자입니다. 한국어 존댓말, 사실과 추정의 분리, 클릭 유도 과장 금지. 구체적 연도별 전형 일정/숫자/대학 기준은 제공된 원문으로 검증된 것만 사용하십시오. 외부 실시간 검색 기능이 없으니 제공하지 않은 근거를 임의로 만들거나 '확정'이라고 표현하지 마십시오. 2028학년도 관련 제도와 개별 대학의 모집요강을 혼동하지 마십시오. 미확인 사실은 [공식 원문 확인 필요]로 표시하십시오. 학생 개인정보 노출 금지. 텍스트로만 출력하고 마크다운 소제목을 활용하십시오. 본문 마지막에 공식 자료 확인 안내와 선택한 CTA 링크를 포함하십시오.'''
    user=f'''주제: {topic}\n채널: {channel}\n키워드: {keywords}\n사용자가 제공한 원문/출처 URL(실시간 내용 검증을 보장하지 않음):\n{sources}\n\n다음 순서로 작성: 제목 후보 3개, 핵심 요약, 본문(도입, 제도 설명, 학부모 점검표, 사례/상담 방향, 결론), 출처 확인 필요 항목, 메타 설명(120자 이내), 태그 8개. 아래 공식 링크 중 문맥에 맞는 것을 1~2개 포함: {json.dumps(CTA,ensure_ascii=False)}'''
    response=requests.post('https://api.openai.com/v1/responses',headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},json={'model':model,'instructions':instructions,'input':user,'max_output_tokens':3200},timeout=100)
    if not response.ok: raise RuntimeError(f'AI 요청 오류 {response.status_code}: {response.text[:250]}')
    data=response.json()
    output=data.get('output_text','')
    if not output:
        output='\n'.join(block.get('text','') for item in data.get('output',[]) for block in item.get('content',[]) if block.get('type')=='output_text')
    if not output.strip(): raise RuntimeError('AI 응답에서 텍스트를 추출하지 못했습니다.')
    return output

def scaffold(topic, keywords):
    ks=[x.strip() for x in keywords.split(',') if x.strip()]
    return f'''# {topic}: 학부모와 학생이 먼저 확인해야 할 기준\n\n## 핵심 요약\n- 제도와 대학별 선발기준을 구분해서 확인합니다.\n- 적용 학년도와 전형 유형을 반드시 명시합니다.\n- 대학 입학처의 공식 원문을 최종 기준으로 삼습니다.\n\n## 1. 왜 이 주제를 확인해야 할까요?\n{topic}에 관한 변화가 학생의 학습·지원 전략에 미치는 영향을 살펴봅니다. [구체적 사실은 공식 원문 확인 필요]\n\n## 2. 확인할 주요 항목\n1. 적용 학년도와 대상 학년\n2. 제도 공통 기준과 대학별 차이\n3. 교과/학생부/수능/면접에서 확인할 조건\n4. 최신 시행계획과 모집요강의 차이\n\n## 3. 상담에서 점검할 질문\n- 학생의 현재 학년과 지원 목표는 무엇인가요?\n- 내신 및 모의고사 분석 결과가 일치하나요?\n- 선택과목·탐구활동·학습완성도에서 보완점은 무엇인가요?\n\n## 4. 공식 자료 확인\n[여기에 교육부·한국대학교육협의회·대학 입학처의 해당 학년도 원문과 확인일을 기록하세요.]\n\n## 5. 추가 분석 및 상담\n- 진로NAVI: {CTA['진로NAVI']}\n- 입시NAVI: {CTA['입시NAVI']}\n- 천명의선택: {CTA['공식 홈페이지']}\n\n추천 키워드: {', '.join(ks)}\n\n※ 본 글은 사전 기획 초안입니다. 공식 원문 검수 전 게시하지 마세요.'''

def check(post):
    body=post.get('body','');sources=post.get('sources',''); findings=[]
    def add(level,msg):findings.append((level,msg))
    if len(body.strip())<600:add('주의','본문이 짧습니다(600자 미만). 상세 근거와 사례를 추가하세요.')
    if not re.search(r'https?://\S+',sources):add('차단','공식 근거 URL이 없습니다. 원문 URL과 확인일을 남기세요.')
    if '확인일' not in sources and '열람일' not in sources:add('주의','출처별 확인일이 누락되었습니다.')
    if not any(x in sources.lower() for x in ['go.kr','ac.kr','kcue.or.kr','adiga.kr']):add('주의','출처에 정부·대교협·대학 입학처 자료가 있는지 확인하세요.')
    if re.search(r'확정|전원 합격|100%|무조건|반드시 합격',body):add('주의','확정적·과장 표현을 점검하세요.')
    if re.search(r'\[.*?(확인 필요|기록하세요|여기에).*?\]',body):add('차단','검증 전용 플레이스홀더가 본문에 남아 있습니다.')
    if 'choice1000.com' not in body and not any(url in body for url in CTA.values()):add('주의','상담 전환 링크(CTA)가 없습니다.')
    if not post.get('keywords','').strip():add('주의','검색 키워드가 없습니다.')
    if not post.get('claims','').strip():add('차단','핵심 수치·규정에 대한 수동 사실확인 기록이 없습니다.')
    if not post.get('title','').strip():add('차단','제목이 없습니다.')
    if not findings:add('통과','형식·기본 검수 조건을 충족합니다. 내용의 진위는 담당자가 원문 대조해야 합니다.')
    return findings

def html_export(post):
    text=post['body']
    lines=[]
    for line in text.splitlines():
        if line.startswith('### '): lines.append('<h3>'+html.escape(line[4:])+'</h3>')
        elif line.startswith('## '): lines.append('<h2>'+html.escape(line[3:])+'</h2>')
        elif line.startswith('# '):lines.append('<h1>'+html.escape(line[2:])+'</h1>')
        elif line.strip():
            escaped=html.escape(line)
            escaped=re.sub(r'(https?://[^\s&lt;]+)',r'<a href="\1" rel="noopener noreferrer">\1</a>',escaped)
            lines.append('<p>'+escaped+'</p>')
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>'+html.escape(post['title'])+'</title></head><body><article>\n'+'\n'.join(lines)+'\n</article></body></html>'

def ics_event(post):
    when=datetime.fromisoformat(post['publish_at'])
    end=when+timedelta(minutes=30)
    fmt=lambda d:d.strftime('%Y%m%dT%H%M%S')
    esc=lambda s:str(s).replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\n','\\n')
    return '\r\n'.join(['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Blog NAVI//KR','BEGIN:VEVENT',f'UID:blog-navi-{post["id"]}@choice1000.com',f'DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',f'DTSTART;TZID=Asia/Seoul:{fmt(when)}',f'DTEND;TZID=Asia/Seoul:{fmt(end)}',f'SUMMARY:{esc("[블로그 게시 예약] "+post["title"])}',f'DESCRIPTION:{esc("편집기에서 수동 예약 발행 등록: "+post["channel"])}','END:VEVENT','END:VCALENDAR',''])

def backup_bytes():
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        posts=all_posts()
        z.writestr('posts.json',json.dumps(posts,ensure_ascii=False,indent=2))
        with conn() as c: metrics=[dict(r) for r in c.execute('SELECT * FROM metrics')]
        z.writestr('metrics.json',json.dumps(metrics,ensure_ascii=False,indent=2))
        z.writestr('README.txt','블로그 NAVI 백업. 복원은 관리자 화면에서 JSON 파일을 사용하세요. 개인정보를 기입하지 마세요.')
    return buf.getvalue()

if not os.getenv('BLOG_NAVI_PASSWORD'):
    try: password=st.secrets.get('BLOG_NAVI_PASSWORD','')
    except Exception:password=''
else:password=os.getenv('BLOG_NAVI_PASSWORD','')
if password:
    if not st.session_state.get('authenticated'):
        st.title('🔒 블로그 NAVI')
        with st.form('login'):
            p=st.text_input('접근 비밀번호',type='password')
            if st.form_submit_button('로그인'):
                if hashlib.sha256(p.encode()).digest()==hashlib.sha256(str(password).encode()).digest():st.session_state.authenticated=True;st.rerun()
                else:st.error('비밀번호를 확인하세요.')
        st.stop()
else:st.sidebar.warning('관리자 비밀번호가 설정되지 않았습니다. 공개 배포 전에 BLOG_NAVI_PASSWORD를 설정하세요.')

st.title('🧭 블로그 NAVI')
st.caption('천명의선택 · AI 콘텐츠 제작 → 공식근거 대조 → 승인 → 예약 게시 지원 · v1.0')
page=st.sidebar.radio('관리 메뉴',['대시보드','콘텐츠 기획·생성','원고 편집·검수','예약 발행 지원','성과 분석','설정·백업'])
posts=all_posts()

if page=='대시보드':
    a,b,c,d=st.columns(4)
    a.metric('전체 원고',len(posts));b.metric('승인',sum(p['status']=='승인' for p in posts));c.metric('예약 등록',sum(p['status']=='예약 등록' for p in posts));d.metric('게시 완료',sum(p['status']=='게시 완료' for p in posts))
    st.subheader('입시 콘텐츠 편집 캘린더')
    st.write('권장 흐름: 주제 선정 → 공식 문서 수집 → AI 초안 → 사실 검증 → 승인 → 플랫폼 편집기에서 직접 예약 등록')
    if posts:
        st.dataframe([{'번호':p['id'],'채널':p['channel'],'주제':p['topic'],'제목':p['title'],'단계':p['status'],'예정':p['publish_at']} for p in posts],use_container_width=True,hide_index=True)
    else:st.info('아직 원고가 없습니다. 콘텐츠 기획·생성 메뉴에서 시작하세요.')
    st.subheader('추천 주제 7개')
    st.write(' · '.join(TOPICS))

elif page=='콘텐츠 기획·생성':
    st.subheader('새 콘텐츠 제작')
    channel=st.selectbox('발행 채널',list(BRANDS))
    topic=st.selectbox('콘텐츠 주제',TOPICS+['직접 입력'])
    if topic=='직접 입력':topic=st.text_input('주제 입력')
    title=st.text_input('작업 제목',value=f'{topic} 핵심 분석과 학생별 준비 전략')
    keywords=st.text_input('검색 키워드(쉼표 구분)',value=f'{topic}, 대입, 입시전략, 학생부')
    sources=st.text_area('공식 출처 URL + 확인일 (한 줄당 하나)',placeholder='예: 대학 입학처 2028학년도 시행계획 https://... | 확인일 2026-11-04',height=110)
    mode=st.radio('원고 생성 방식',['기본 구조 초안(API 키 불필요)','AI 초안(OpenAI API 키 필요)'],horizontal=True)
    model=st.text_input('AI 모델',value='gpt-4.1-mini') if mode.startswith('AI') else ''
    if st.button('원고 생성 후 저장',type='primary',disabled=not bool(topic.strip() and title.strip())):
        try:
            body=ai_draft(topic,channel,keywords,sources,model) if mode.startswith('AI') else scaffold(topic,keywords)
            pid=save({'topic':topic,'channel':channel,'title':title,'body':body,'keywords':keywords,'sources':sources,'claims':'','status':'작성 중','publish_at':'','published_url':''})
            st.success(f'원고 #{pid} 저장 완료 — 원고 편집·검수에서 수정하세요.')
            st.text_area('생성 내용',body,height=430)
        except Exception as e:st.error(str(e))
    st.info('생성 AI는 외부 출처를 실시간 대조하지 않습니다. 대학별 수치·전형·일정은 반드시 모집요강 원문과 대조하세요.')

elif page=='원고 편집·검수':
    if not posts:st.info('먼저 원고를 만드세요.')
    else:
        selected=st.selectbox('편집할 원고',posts,format_func=lambda p:f'#{p["id"]} [{p["status"]}] {p["title"]}')
        p=get_post(selected['id'])
        with st.form(f'edit_{p["id"]}'):
            title=st.text_input('제목',value=p['title'])
            topic=st.text_input('주제',value=p['topic'])
            channel=st.selectbox('채널',list(BRANDS),index=list(BRANDS).index(p['channel']) if p['channel'] in BRANDS else 0)
            keywords=st.text_input('키워드',value=p['keywords'])
            body=st.text_area('원고 본문',value=p['body'],height=460)
            sources=st.text_area('근거: 기관·문서명·URL·확인일',value=p['sources'],height=120)
            claims=st.text_area('수동 사실확인 기록 (필수)',value=p['claims'],height=150,help='예: 대학명, 모집요강 학년도, 페이지, 확인한 수치, 확인한 날짜. 사실 검증 여부를 담당자가 기록합니다.')
            status=st.selectbox('작업 단계',STATUS,index=STATUS.index(p['status']) if p['status'] in STATUS else 0)
            submitted=st.form_submit_button('검수 후 저장',type='primary')
            if submitted:
                updated={'title':title,'topic':topic,'channel':channel,'keywords':keywords,'body':body,'sources':sources,'claims':claims,'status':status,'publish_at':p['publish_at'],'published_url':p['published_url']}
                problems=check(updated)
                if status in ['승인','예약 등록','게시 완료'] and any(level=='차단' for level,_ in problems):
                    st.error('차단 항목이 있어 승인할 수 없습니다. 수정 또는 사실검증 기록이 필요합니다.')
                    for level,msg in problems:st.write(f'- [{level}] {msg}')
                else:save(updated,p['id']);st.success('저장되었습니다.');st.rerun()
        st.markdown('#### 검수 리포트 (자동형식 점검)')
        for level,msg in check(p):
            if level=='차단':st.error(msg)
            elif level=='주의':st.warning(msg)
            else:st.success(msg)
        st.caption('자동 점검은 사실 검증을 대신하지 않습니다. 출처의 실재성·원문과 수치 일치는 담당자가 확인해야 합니다.')

elif page=='예약 발행 지원':
    eligible=[p for p in posts if p['status'] in ['승인','예약 등록','게시 완료']]
    if not eligible:st.info('먼저 원고 편집·검수에서 승인 상태로 변경하세요.')
    else:
        s=st.selectbox('게시할 승인 원고',eligible,format_func=lambda p:f'#{p["id"]} {p["title"]}')
        p=get_post(s['id'])
        st.markdown(f'**플랫폼:** {p["channel"]} · [블로그 열기]({BRANDS.get(p["channel"],"https://blog.naver.com")})')
        col1,col2=st.columns(2)
        with col1:publish_day=st.date_input('예약 날짜',value=date.fromisoformat(p['publish_at'][:10]) if p['publish_at'] else date.today()+timedelta(days=1))
        with col2:
            def_t=time.fromisoformat(p['publish_at'][11:16]) if p['publish_at'] else time(9,0)
            publish_time=st.time_input('예약 시각 (한국 시간)',value=def_t)
        pub=st.text_input('실제 게시 URL(게시 완료 후 기입)',value=p['published_url'])
        if st.button('예약 일정 저장(실제 플랫폼 예약과 별도)',type='primary'):
            p['publish_at']=f'{publish_day.isoformat()} {publish_time.strftime("%H:%M")}'
            p['published_url']=pub
            p['status']='게시 완료' if pub.strip() else '예약 등록'
            save(p,p['id']);st.success('NAVI에 예약 일정이 기록되었습니다. 블로그 편집기에서도 예약 발행을 별도로 설정해야 합니다.');st.rerun()
        st.download_button('게시용 HTML 다운로드',html_export(p),file_name=f'blog_navi_{p["id"]}.html',mime='text/html')
        st.download_button('게시용 원고 TXT 다운로드',p['body'],file_name=f'blog_navi_{p["id"]}.txt',mime='text/plain')
        if p['publish_at']:
            st.download_button('예약 캘린더(.ics) 다운로드',ics_event(p),file_name=f'blog_navi_{p["id"]}.ics',mime='text/calendar')
        st.text_area('복사할 원고',p['body'],height=320)
        st.info('자동 게시 기능이 아닙니다. 네이버/티스토리 편집기에 붙여넣기 후 실제 예약 발행 버튼을 누르세요. HTML은 호환성 확인용이며 편집기에서는 일반 텍스트 복사를 권장합니다.')

elif page=='성과 분석':
    st.subheader('게시물별 실측 데이터 수동 입력')
    done=[p for p in posts if p['status']=='게시 완료']
    if not done:st.info('게시 완료 글이 있으면 검색 노출수·클릭수·방문자·상담 건수·수익을 입력할 수 있습니다.')
    else:
        p=st.selectbox('분석 대상',done,format_func=lambda x:f'#{x["id"]} {x["title"]}')
        with st.form('metrics'):
            day=st.date_input('측정일',value=date.today())
            c1,c2,c3=st.columns(3)
            imp=c1.number_input('검색 노출수',min_value=0,step=1)
            clicks=c2.number_input('검색 클릭수',min_value=0,step=1)
            visitors=c3.number_input('방문자 수',min_value=0,step=1)
            d1,d2=st.columns(2)
            inquiries=d1.number_input('상담 문의 수',min_value=0,step=1)
            revenue=d2.number_input('수익(원)',min_value=0.0,step=100.0)
            if st.form_submit_button('측정값 저장'):
                with conn() as c:c.execute('INSERT INTO metrics(post_id,recorded_at,impressions,clicks,visitors,inquiries,revenue) VALUES(?,?,?,?,?,?,?) ON CONFLICT(post_id,recorded_at) DO UPDATE SET impressions=excluded.impressions,clicks=excluded.clicks,visitors=excluded.visitors,inquiries=excluded.inquiries,revenue=excluded.revenue',(p['id'],day.isoformat(),imp,clicks,visitors,inquiries,revenue))
                st.success('측정값 저장 완료')
    with conn() as c:
        rows=[dict(r) for r in c.execute('SELECT m.*,p.title,p.channel FROM metrics m JOIN posts p ON p.id=m.post_id ORDER BY m.recorded_at DESC')]
    if rows:
        st.dataframe([{'날짜':r['recorded_at'],'글':r['title'],'채널':r['channel'],'노출수':r['impressions'],'클릭수':r['clicks'],'CTR(%)':round(r['clicks']/r['impressions']*100,2) if r['impressions'] else 0,'방문자':r['visitors'],'상담':r['inquiries'],'수익(원)':r['revenue']} for r in rows],hide_index=True,use_container_width=True)
        b=io.StringIO();w=csv.writer(b);w.writerow(rows[0].keys());w.writerows([r.values() for r in rows]);st.download_button('성과 CSV 저장',b.getvalue().encode('utf-8-sig'),file_name='blog_navi_metrics.csv',mime='text/csv')
    st.caption('검색노출수/클릭은 검색엔진 관리도구, 방문자/수익은 각 블로그 통계 화면 기준으로 수동 기록합니다. 중복 측정값의 기준 기간을 동일하게 맞추세요.')

else:
    st.subheader('설정 및 데이터 백업')
    st.write('연동 브랜드',BRANDS)
    st.write('상담 CTA',CTA)
    st.write('OpenAI API 설정 여부:', '설정됨' if load_api_key() else '미설정 — 기본 초안만 사용')
    st.download_button('전체 JSON 백업 ZIP 다운로드',backup_bytes(),file_name='blog_navi_backup.zip',mime='application/zip')
    st.markdown('#### 백업 복원 (JSON)')
    upload=st.file_uploader('백업 ZIP 내부 posts.json 업로드',type=['json'])
    if upload is not None and st.button('백업 원고 병합 가져오기'):
        try:
            arr=json.load(upload)
            if not isinstance(arr,list):raise ValueError('JSON 목록이 아닙니다.')
            count=0
            for p in arr:
                if not isinstance(p,dict) or not p.get('title') or not p.get('topic'):continue
                p['status']='작성 중' if p.get('status') not in STATUS else p['status']
                save(p);count+=1
            st.success(f'{count}개 원고를 새 ID로 가져왔습니다. 중복은 자동 제거되지 않습니다.')
        except Exception as e:st.error(f'복원 실패: {e}')
    st.warning('Streamlit Community Cloud의 로컬 SQLite는 재배포·절전·재시작 시 소실될 수 있습니다. 정기 백업 또는 영속 DB(PostgreSQL 등)를 연결해야 합니다.')
    st.caption('앱에서는 공식 API 기반 자동 게시를 제공하지 않습니다. 개인정보·비밀번호·API 키를 원고 본문에 쓰지 마세요.')
    if posts:
        with st.expander('원고 삭제'):
            pid=st.selectbox('삭제 대상',posts,format_func=lambda p:f'#{p["id"]} {p["title"]}',key='del_post')
            confirm=st.checkbox('해당 원고와 측정 데이터를 삭제하는 것에 동의합니다')
            if st.button('영구 삭제',disabled=not confirm):delete(pid['id']);st.success('삭제했습니다.');st.rerun()
