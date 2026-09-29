# 자산운용 AI PR 뉴스모니터 — Cloud Web v1

Streamlit Community Cloud 배포용입니다.

## Streamlit Secrets
배포 화면의 Advanced settings > Secrets에 실제 값을 입력하세요.

```toml
NAVER_CLIENT_ID = "실제_Client_ID"
NAVER_CLIENT_SECRET = "실제_Client_Secret"
APP_PASSWORD = "접속용_비밀번호"
```

실제 API 키는 GitHub 파일에 커밋하지 마세요.

## 실행 파일
Main file path: `streamlit_app.py`

배포 후 앱 왼쪽의 **NAVER API 연결 테스트**를 먼저 실행하여 HTTP 200을 확인하세요.
