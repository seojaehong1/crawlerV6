import argparse
import csv
import re
import random
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page, BrowserContext


def wait_for_network_idle(page: Page, timeout_ms: int = 3000) -> None:
    start = time.time()
    page.wait_for_load_state("domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass
    finally:
        _ = start


def open_new_context(playwright, headless: bool) -> BrowserContext:
    chromium = playwright.chromium
    browser = chromium.launch(headless=headless)
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    context = browser.new_context(
        user_agent=user_agent,
        viewport={"width": 1366, "height": 800},
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        device_scale_factor=1.0,
        has_touch=False,
    )
    return context


def human_delay(base_delay_ms: int = 500) -> None:
    jitter = random.randint(0, base_delay_ms)
    time.sleep((base_delay_ms + jitter) / 1000.0)


def extract_image_url(page: Page) -> str:
    """페이지에서 이미지 URL 추출"""
    image_url = ""
    image_selectors = [
        "div.thumb_area img#baseImage",
        "div.thumb_area img",
        "div.photo_viewer img",
        "div.photo_area img",
        "img#baseImage",
        "img[class*='prod_image']",
    ]
    for selector in image_selectors:
        try:
            locator = page.locator(selector)
            if locator.count() == 0:
                continue
            candidate = (
                locator.first.get_attribute("src")
                or locator.first.get_attribute("data-src")
                or locator.first.get_attribute("data-origin")
                or ""
            )
            if candidate and candidate.startswith("//"):
                candidate = f"https:{candidate}"
            if candidate:
                image_url = candidate.strip()
                break
        except Exception as e:
            continue
    return image_url


def add_images_to_csv(
    input_file: str,
    output_file: str,
    headless: bool = True,
    delay_ms: int = 800,
    url_column: str = "URL",
    image_column: str = "상품이미지",
):
    """CSV 파일의 URL을 읽어서 이미지 URL을 추출하고 추가"""
    rows = []
    
    # CSV 파일 읽기
    with open(input_file, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        
        if url_column not in fieldnames:
            print(f"오류: '{url_column}' 컬럼을 찾을 수 없습니다.")
            return
        
        # 기존 행 읽기
        for row in reader:
            rows.append(row)
    
    print(f"총 {len(rows)}개 행 처리 시작...")
    
    # Playwright로 이미지 추출
    with sync_playwright() as p:
        context = open_new_context(p, headless=headless)
        
        for idx, row in enumerate(rows, 1):
            url = row.get(url_column, "").strip()
            
            if not url:
                print(f"[{idx}/{len(rows)}] URL이 없어서 스킵")
                continue
            
            # 이미 이미지 URL이 있으면 스킵
            if row.get(image_column, "").strip():
                print(f"[{idx}/{len(rows)}] 이미지 URL이 이미 있어서 스킵")
                continue
            
            try:
                print(f"[{idx}/{len(rows)}] {url[:60]}... 이미지 추출 중...")
                page = context.new_page()
                page.set_default_timeout(15000)
                
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    wait_for_network_idle(page)
                    image_url = extract_image_url(page)
                    
                    if image_url:
                        row[image_column] = image_url
                        print(f"    ✓ 이미지 URL 추출 성공: {image_url[:60]}...")
                    else:
                        print(f"    ✗ 이미지 URL을 찾을 수 없음")
                        row[image_column] = ""
                except Exception as e:
                    print(f"    ✗ 오류: {e}")
                    row[image_column] = ""
                finally:
                    page.close()
                    human_delay(delay_ms)
                    
            except Exception as e:
                print(f"[{idx}/{len(rows)}] 오류 발생: {e}")
                row[image_column] = ""
        
        context.browser.close()
    
    # 결과 저장
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    
    print(f"\n완료! 결과 파일: {output_file}")


def parse_args():
    parser = argparse.ArgumentParser(description="CSV 파일의 URL에서 이미지 URL 추출하여 추가")
    parser.add_argument("--input", help="입력 CSV 파일 경로 (기본값: danawa_유모차_output.csv)")
    parser.add_argument("--output", help="출력 CSV 파일 경로 (기본값: 입력파일명_with_images.csv)")
    parser.add_argument("--headless", action="store_true", help="브라우저를 백그라운드로 실행")
    parser.add_argument("--delay-ms", type=int, default=800, help="요청 간 지연 시간 (ms)")
    parser.add_argument("--url-column", default="URL", help="URL 컬럼 이름 (기본값: URL)")
    parser.add_argument("--image-column", default="상품이미지", help="이미지 컬럼 이름 (기본값: 상품이미지)")
    return parser.parse_args()


def main():
    args = parse_args()
    
    # 기본 입력 파일명 설정
    if not args.input:
        # 현재 디렉토리에서 파일 찾기 (pcode 포함 파일 우선)
        import glob
        stroller_file = "danawa_유모차_output_with_pcode.csv"
        if Path(stroller_file).exists():
            args.input = stroller_file
        else:
            # 일반 유모차 파일 확인
            alt_file = "danawa_유모차_output.csv"
            if Path(alt_file).exists():
                args.input = alt_file
            else:
                csv_files = glob.glob("danawa_*output*.csv")
                if csv_files:
                    args.input = csv_files[0]
                else:
                    args.input = stroller_file
    
    # 한글 파일명 인코딩 문제 해결을 위해 Path 객체 사용
    input_path = Path(args.input)
    
    # output이 지정되지 않으면 입력 파일을 직접 업데이트
    if not args.output:
        args.output = str(input_path)  # 같은 파일에 덮어쓰기
    else:
        args.output = str(Path(args.output))
    
    add_images_to_csv(
        input_file=str(input_path),
        output_file=args.output,
        headless=args.headless,
        delay_ms=args.delay_ms,
        url_column=args.url_column,
        image_column=args.image_column,
    )


if __name__ == "__main__":
    main()

