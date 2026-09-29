import io, os, re, html, time
from datetime import datetime
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='자산운용 뉴스 PR 모니터', page_icon='📰', layout='wide')

COMPANIES = {
    '신한자산운용':['신한자산운용','SOL ETF','SOL'], '미래에셋자산운용':['미래에셋자산운용','TIGER'],
    '삼성자산운용':['삼성자산운용','KODEX'], 'KB자산운용':['KB자산운용','RISE'],
    '한국투자신탁운용':['한국투자신탁운용','ACE ETF','ACE'], '한화자산운용':['한화자산운용','PLUS ETF'],
    'NH-Amundi자산운용':['NH-Amundi자산운용','HANARO'], '키움투자자산운용':['키움투자자산운용','KOSEF'],
}
TOPICS = {
    'ETF':['ETF','상장지수펀드'], 'TDF·연금':['TDF','퇴직연금','연금','IRP'], '채권':['채권','국채','회사채','금리'],
    '펀드':['펀드','공모펀드','사모펀드'], '대체투자':['대체투자','부동산','인프라','리츠'],
    '인사·경영':['대표','CEO','인사','취임','사장'], '규제·제재':['금감원','금융감독원','제재','검사','과징금','징계']
}
RISK_WORDS = ['횡령','배임','제재','과징금','징계','손실','부진','급락','하락','유출','논란','의혹','중단','사고','피해','적자','위반','경고']
POS_WORDS = ['돌파','증가','성장','호조','수상','1위','최대','신기록','출시','확대','상승','유입','성과','선정','강세','개선']

@st.cache_resource
def load_model():
    try:
        from transformers import pipeline
        return pipeline('text-classification', model='snunlp/KR-FinBert-SC', tokenizer='snunlp/KR-FinBert-SC')
    except Exception:
        return None

def clean(s):
    return re.sub(r'<[^>]+>', '', html.unescape(s or '')).strip()

def classify_company(text):
    found=[]
    for c, keys in COMPANIES.items():
        if any(k.lower() in text.lower() for k in keys): found.append(c)
    return ', '.join(found) if found else '기타/업계'

def classify_topic(text):
    scores={k:sum(text.lower().count(w.lower()) for w in ws) for k,ws in TOPICS.items()}
    best=max(scores, key=scores.get)
    return best if scores[best] else '기타'

def fallback_sentiment(text):
    p=sum(text.count(w) for w in POS_WORDS); n=sum(text.count(w) for w in RISK_WORDS)
    if n>p: return '부정', min(.55+n*.07,.95)
    if p>n: return '긍정', min(.55+p*.07,.95)
    return '중립', .55

def sentiment(model, text):
    if model:
        try:
            r=model(text[:1200], truncation=True, max_length=512)[0]
            m={'positive':'긍정','neutral':'중립','negative':'부정'}
            return m.get(r['label'].lower(), r['label']), float(r['score'])
        except Exception: pass
    return fallback_sentiment(text)

def risk_level(text, sent):
    n=sum(text.count(w) for w in RISK_WORDS)
    if sent=='부정' and n>=2: return 'HIGH'
    if sent=='부정' or n>=1: return 'MEDIUM'
    return 'LOW'

def fetch_news(query, client_id, client_secret, count):
    headers={'X-Naver-Client-Id':client_id,'X-Naver-Client-Secret':client_secret}
    rows=[]
    for start in range(1, min(count,1000)+1, 100):
        display=min(100, count-len(rows))
        if display<=0: break
        r=requests.get('https://openapi.naver.com/v1/search/news.json', headers=headers,
                       params={'query':query,'display':display,'start':start,'sort':'date'}, timeout=15)
        r.raise_for_status()
        items=r.json().get('items',[])
        for x in items:
            rows.append({'게시일':x.get('pubDate'),'제목':clean(x.get('title')),'요약':clean(x.get('description')),
                         '원문URL':x.get('originallink'),'네이버URL':x.get('link')})
        if len(items)<display: break
        time.sleep(.08)
    return pd.DataFrame(rows).drop_duplicates(subset=['제목'])

def excel_bytes(df):
    out=io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as w:
        df.to_excel(w,index=False,sheet_name='전체기사')
        for s in ['긍정','중립','부정']:
            df[df['감성']==s].to_excel(w,index=False,sheet_name=f'{s}기사')
        df.groupby(['관련운용사','감성']).size().unstack(fill_value=0).to_excel(w,sheet_name='운용사요약')
        df.groupby(['주제','감성']).size().unstack(fill_value=0).to_excel(w,sheet_name='이슈요약')
    return out.getvalue()

def get_secret(name, default=''):
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return str(os.getenv(name, default)).strip()

def api_test(client_id, client_secret):
    try:
        r=requests.get('https://openapi.naver.com/v1/search/news.json',
            headers={'X-Naver-Client-Id':client_id.strip(),'X-Naver-Client-Secret':client_secret.strip()},
            params={'query':'자산운용','display':1,'start':1,'sort':'date'}, timeout=15)
        return r.status_code, r.text[:500]
    except Exception as e:
        return 0, str(e)

app_password=get_secret('APP_PASSWORD')
if app_password:
    if 'authenticated' not in st.session_state: st.session_state.authenticated=False
    if not st.session_state.authenticated:
        st.title('🔐 자산운용 AI PR 뉴스모니터')
        pw=st.text_input('접속 비밀번호', type='password')
        if st.button('로그인', type='primary'):
            if pw == app_password:
                st.session_state.authenticated=True; st.rerun()
            else: st.error('비밀번호가 일치하지 않습니다.')
        st.stop()

st.title('📰 자산운용 뉴스 AI PR 모니터')
st.caption('네이버 뉴스 검색 API 기반 · 금융 뉴스 감성분석 · 운용사/이슈/PR 위험 자동 분류')

with st.sidebar:
    st.header('검색 설정')
    query=st.text_input('검색어', '자산운용')
    count=st.slider('수집 기사 수', 50, 1000, 300, 50)
    days=st.selectbox('표시 기간', [1,3,7,14,30], index=2, format_func=lambda x:f'최근 {x}일')
    st.divider(); st.subheader('Naver API')
    cid=get_secret('NAVER_CLIENT_ID'); secret=get_secret('NAVER_CLIENT_SECRET')
    if cid and secret: st.success('서버 Secrets에서 API 인증정보를 불러왔습니다.')
    else: st.error('서버 Secrets에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 설정이 필요합니다.')
    if st.button('🔌 NAVER API 연결 테스트', use_container_width=True):
        if not cid or not secret: st.error('API Secrets가 설정되지 않았습니다.')
        else:
            code, detail=api_test(cid,secret)
            if code == 200: st.success('NAVER Search API 인증 성공 (HTTP 200)')
            elif code == 401: st.error('인증 실패 (HTTP 401): Client ID/Secret을 다시 확인하세요.')
            elif code == 403: st.error('권한 거부 (HTTP 403): 네이버 애플리케이션에서 검색 API 사용 설정을 확인하세요.')
            else: st.error(f'API 연결 실패 (HTTP {code})'); st.code(detail)
    run=st.button('🔎 뉴스 수집·분석', type='primary', use_container_width=True)
    st.caption('API 키는 웹 사용자에게 입력받지 않고 Streamlit Secrets에서만 읽습니다.')

if run:
    if not cid or not secret: st.error('Naver API Secrets를 먼저 설정하세요.')
    else:
        try:
            with st.spinner('뉴스를 수집하고 분석하고 있습니다...'):
                df=fetch_news(query,cid,secret,count)
                df['게시일']=pd.to_datetime(df['게시일'], errors='coerce', utc=True).dt.tz_convert('Asia/Seoul')
                cutoff=pd.Timestamp.now(tz='Asia/Seoul')-pd.Timedelta(days=days)
                df=df[df['게시일']>=cutoff].copy()
                model=load_model(); results=[]; prog=st.progress(0)
                for i,(_,r) in enumerate(df.iterrows()):
                    text=f"{r['제목']} {r['요약']}"; s,score=sentiment(model,text)
                    results.append((s,score,classify_company(text),classify_topic(text),risk_level(text,s)))
                    prog.progress((i+1)/max(len(df),1))
                if results: df[['감성','신뢰도','관련운용사','주제','PR위험도']]=pd.DataFrame(results,index=df.index)
                st.session_state['df']=df
        except Exception as e: st.error(f'수집/분석 중 오류가 발생했습니다: {e}')

df=st.session_state.get('df')
if df is None:
    st.info('왼쪽에서 **NAVER API 연결 테스트**를 먼저 실행한 뒤 **뉴스 수집·분석**을 누르세요.')
else:
    total=len(df); pos=(df['감성']=='긍정').sum(); neu=(df['감성']=='중립').sum(); neg=(df['감성']=='부정').sum(); high=(df['PR위험도']=='HIGH').sum()
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric('전체 기사',f'{total:,}건'); c2.metric('긍정',f'{pos:,}건'); c3.metric('중립',f'{neu:,}건'); c4.metric('부정',f'{neg:,}건'); c5.metric('HIGH 위험',f'{high:,}건')
    tab1,tab2,tab3=st.tabs(['📊 대시보드','🗞 기사 모니터링','🚨 PR 위험'])
    with tab1:
        a,b=st.columns(2)
        with a:
            st.subheader('감성 분포'); st.bar_chart(df['감성'].value_counts())
            st.subheader('주제별 기사량'); st.bar_chart(df['주제'].value_counts())
        with b:
            st.subheader('운용사별 기사량'); st.bar_chart(df['관련운용사'].value_counts().head(12))
            st.subheader('일자별 기사량'); st.line_chart(df.assign(일자=df['게시일'].dt.date).groupby('일자').size())
    with tab2:
        f1,f2,f3=st.columns(3)
        sentiments=f1.multiselect('감성', ['긍정','중립','부정'], default=['긍정','중립','부정'])
        risks=f2.multiselect('위험도',['HIGH','MEDIUM','LOW'],default=['HIGH','MEDIUM','LOW'])
        word=f3.text_input('제목/요약 내 검색')
        view=df[df['감성'].isin(sentiments)&df['PR위험도'].isin(risks)].copy()
        if word: view=view[(view['제목']+' '+view['요약']).str.contains(word,case=False,na=False)]
        show=view[['게시일','감성','PR위험도','관련운용사','주제','제목','신뢰도','네이버URL']].sort_values('게시일',ascending=False)
        st.dataframe(show, use_container_width=True, hide_index=True, column_config={'네이버URL':st.column_config.LinkColumn('기사'),'신뢰도':st.column_config.ProgressColumn('신뢰도',min_value=0,max_value=1,format='%.2f')})
        st.download_button('⬇️ 분석결과 엑셀 다운로드', excel_bytes(df), file_name=f'자산운용_뉴스_PR모니터_{datetime.now():%Y%m%d}.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    with tab3:
        risk=df[df['PR위험도'].isin(['HIGH','MEDIUM'])].sort_values(['PR위험도','게시일'],ascending=[True,False])
        if risk.empty: st.success('현재 분류 기준상 주요 PR 위험 기사가 없습니다.')
        else:
            for _,r in risk.head(30).iterrows():
                icon='🔴' if r['PR위험도']=='HIGH' else '🟠'
                with st.expander(f"{icon} [{r['PR위험도']}] {r['제목']}"):
                    st.write(r['요약']); st.write(f"**관련 운용사:** {r['관련운용사']}  |  **주제:** {r['주제']}  |  **감성:** {r['감성']} ({r['신뢰도']:.1%})")
                    st.link_button('네이버 기사 열기', r['네이버URL'])
