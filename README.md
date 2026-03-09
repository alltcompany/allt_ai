# Math Screenshot to HWPX Web App

수학 문제 스크린샷을 업로드하면 OCR 및 수식 추정을 거쳐 `.hwpx` 파일로 내려받게 해주는 Flask 웹 앱입니다.

## 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

브라우저에서 `http://localhost:5000` 접속 후 이미지 파일 업로드.

## 주의
- 한글 OCR 품질은 설치된 Tesseract 언어 데이터(`kor`)에 영향을 받습니다.
- `pix2tex`가 설치되어 있으면 수식 LaTeX 추정을 추가로 시도합니다.
- 생성된 HWPX는 기본 XML 패키지 구조를 사용합니다.
