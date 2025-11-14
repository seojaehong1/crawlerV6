## 설치 방법

### 1. 가상환경 생성 및 활성화

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. 의존성 설치

```powershell
pip install -r require.txt
playwright install
```

## 사용 방법

### 1. 패턴 학습 (PASS1)

카테고리별 체크마크 패턴을 학습하여 JSON 파일로 저장합니다.

```powershell
python pattern_learn_final.py --category-url "https://prod.danawa.com/list/?cate=16249192&15main_16_02" --pages 10 --max-total-items 100 --headless --mapping-output "patterns2\19_유모차.json"
```

**옵션:**
- `--category-url`: 다나와 카테고리 URL (필수)
- `--pages`: 최대 페이지 수 (기본값: 10)
- `--max-total-items`: 최대 상품 수 (0=무제한, 기본값: 0)
- `--headless`: 브라우저를 백그라운드로 실행
- `--mapping-output`: 출력 JSON 파일 경로 (필수)

### 2. 실제 크롤링 (PASS2)

학습된 JSON 패턴을 사용하여 실제 상품 데이터를 크롤링합니다.

```powershell
python crawl_stroller.py --category-url "https://prod.danawa.com/list/?cate=16249192&15main_16_02" --pattern-json "patterns2\19_유모차.json" --output "danawa_유모차_output.csv" --pages 10 --max-total-items 187 --headless --delay-ms 800
```

**옵션:**
- `--category-url`: 다나와 카테고리 URL (필수)
- `--pattern-json`: 패턴 JSON 파일 경로 (필수)
- `--output`: 출력 CSV 파일 경로 (기본값: danawa_output.csv)
- `--pages`: 최대 페이지 수 (기본값: 10)
- `--max-total-items`: 최대 상품 수 (0=무제한, 기본값: 0)
- `--headless`: 브라우저를 백그라운드로 실행
- `--delay-ms`: 요청 간 지연 시간 (ms, 기본값: 1000)

### 3. CSV 후처리

#### pcode 컬럼 추가

```powershell
python add_pcode.py --input "danawa_유모차_output.csv" --output "danawa_유모차_output_with_pcode.csv"
```

#### 이미지 URL 추가

```powershell
python add_images_to_csv.py --input "danawa_유모차_output.csv" --headless --delay-ms 800
```

## 4대 PC 분산 실행

36개 카테고리를 4대 PC로 분산하여 패턴 학습을 수행할 수 있습니다.

자세한 내용은 `리드미드2.md` 파일을 참고하세요.

**PC별 카테고리 분배:**
- PC1: 카테고리 1~9 (분유, 이유식/유아식, 유아간식/영양제, 기저귀, 천기저귀/용품, 물티슈, 인기 캐릭터완구, 레고/블럭, 로봇/배틀카드)
- PC2: 카테고리 10~18 (역할놀이/소꿉놀이, 인형/피규어, 킥보드/승용완구, 음악/미술놀이, 자연/과학완구, 실내대형완구, 놀이방매트/안전용품, 신생아/영유아완구, 물놀이완구)
- PC3: 카테고리 19~27 (유모차, 유모차용품, 카시트, 카시트용품, 아기띠/외출용품, 젖병/수유용품, 이유식용품, 위생/목욕용품, 출산/신생아용품)
- PC4: 카테고리 28~36 (신생아/영유아완구2, 유아완구, 유아동의류, 유아동신발, 신생아의류, 책가방/잡화, 참고서/학습책, 그림/동화/놀이책, 전자펜/학습기/퍼즐)


### 크롤링 CSV 파일

컬럼: `상품명`, `URL`, `상품이미지`, `최저가`, `최고가`, `가격추이`, `상세정보`

### pcode 포함 CSV 파일

컬럼: `pcode`, `상품명`, `URL`, `상품이미지`, `최저가`, `최고가`, `가격추이`, `상세정보`

## 성능 개선 사항

- **비동기 병렬 처리**: 동시 15개 탭 실행으로 처리 속도 18배 향상
- **리소스 차단**: 이미지, 폰트, 스타일시트 등 불필요한 리소스 차단
- **JavaScript 기반 추출**: Python 루프 대신 브라우저 내부 JS로 즉시 추출

## 주의사항

- 대량 크롤링 시 서버 부하를 고려하여 `--delay-ms` 값을 적절히 조정하세요.


