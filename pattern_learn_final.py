import argparse
import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from playwright.async_api import async_playwright, BrowserContext, Page

# ==========================================
# 설정: 동시 실행 탭 개수 (로직이 가벼워져서 15개로 늘림)
# ==========================================
CONCURRENT_TABS = 15

async def process_product_page(context: BrowserContext, link: str, sem: asyncio.Semaphore) -> List[str]:
    """
    상품 페이지에서 오직 '체크마크(O)'가 있는 항목명(Key)만 추출합니다.
    이미지, 가격 등 다른 정보는 일절 보지 않습니다.
    """
    async with sem:
        page = await context.new_page()
        
        # 속도 향상을 위한 강력한 리소스 차단 (이미지, 폰트, 스타일시트 등)
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,ttf,woff,woff2,mp4,css}", lambda route: route.abort())
        
        found_keys = []
        
        try:
            # 타임아웃 15초 (오래 걸리는 페이지는 과감히 패스)
            await page.goto(link, wait_until="domcontentloaded", timeout=15000)
            
            # 상세 정보 탭 클릭 (필요한 경우)
            try:
                labels = ["상세정보", "상세 사양", "상세스펙", "상세 스펙", "스펙", "사양"]
                for label in labels:
                    btn = page.get_by_role("button", name=label)
                    if await btn.count() > 0:
                        await btn.first.click(timeout=2000)
                        await page.wait_for_load_state("domcontentloaded")
                        break
                    link_elem = page.get_by_role("link", name=label)
                    if await link_elem.count() > 0:
                        await link_elem.first.click(timeout=2000)
                        await page.wait_for_load_state("domcontentloaded")
                        break
            except:
                pass
            
            # 페이지 로딩 대기
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(0.5)  # 약간의 추가 대기
            
            # ---------------------------------------------------------
            # [핵심] Python 루프 대신 브라우저 내부 JS로 즉시 추출
            # ---------------------------------------------------------
            found_keys = await page.evaluate("""() => {
                const found = [];
                const checkMarks = new Set(["○", "O", "o", "●"]);
                const rows = document.querySelectorAll("tr");
                
                rows.forEach(row => {
                    const ths = row.querySelectorAll("th");
                    const tds = row.querySelectorAll("td");
                    
                    // Case A: <th>항목</th> <td>값1</td> <td>값2</td> ...
                    if (ths.length === 1 && tds.length > 1) {
                        const key = ths[0].innerText.trim();
                        tds.forEach(td => {
                            if (checkMarks.has(td.innerText.trim())) {
                                found.push(key);
                            }
                        });
                    }
                    
                    // Case B: <th>항목</th> <td>값</td> (1:1 매칭)
                    const loopCnt = Math.min(ths.length, tds.length);
                    for (let i = 0; i < loopCnt; i++) {
                        const val = tds[i].innerText.trim();
                        // 값 정제 (괄호 제거 등)
                        const cleanVal = val.split("인증번호")[0].split("바로가기")[0].replace(/\(.*\)/g, '').trim();
                        
                        if (checkMarks.has(cleanVal) || checkMarks.has(val)) {
                            const key = ths[i].innerText.trim();
                            if (key) found.push(key);
                        }
                    }
                });
                return found;
            }""")
            
        except Exception:
            # 로딩 실패나 에러는 무시 (전수 조사이므로 몇 개 빠져도 상관없음)
            pass
        finally:
            await page.close()
            
        return found_keys


async def collect_links_on_page(page: Page, max_per_page: Optional[int]) -> List[str]:
    """목록 페이지에서 상품 링크 수집"""
    # 다나와 리스트 구조에 맞는 선택자들
    selectors = [
        "li.prod_item div.prod_info a.prod_link",
        "li.prod_item .prod_name a",
        "div.prod_info a.prod_link",
    ]
    links = []
    seen = set()
    
    # JS로 링크 추출 (Python 반복문보다 빠름)
    for sel in selectors:
        if await page.locator(sel).count() > 0:
            found_links = await page.evaluate(f"""(sel) => {{
                const arr = [];
                document.querySelectorAll(sel).forEach(el => {{
                    const href = el.getAttribute('href');
                    if (href && !href.includes('javascript') && href.includes('danawa')) {{
                        arr.push(href);
                    }}
                }});
                return arr;
            }}""", sel)
            
            for href in found_links:
                if href not in seen:
                    seen.add(href)
                    links.append(href)
            
            if links: break
            
    if max_per_page:
        return links[:max_per_page]
    return links


async def paginate(page: Page, page_num: int) -> bool:
    """페이지 이동 로직"""
    try:
        # 1. movePage(N) 함수 직접 실행 (가장 빠름)
        is_fn = await page.evaluate("typeof movePage === 'function'")
        if is_fn:
            await page.evaluate(f"movePage({page_num})")
            await page.wait_for_load_state("domcontentloaded") 
            return True
            
        # 2. 버튼 클릭
        btn = page.locator(f"a.num[onclick*='movePage({page_num})']")
        if await btn.count() > 0:
            await btn.first.click()
            await page.wait_for_load_state("domcontentloaded")
            return True
        
        return False
    except:
        return False


async def run_async_scan(
    category_url: str,
    max_pages: int,
    headless: bool,
    max_total_items: Optional[int],
    mapping_output: str
):
    async with async_playwright() as p:
        print(f"=== [PASS 1] 패턴 학습 시작 (동시 {CONCURRENT_TABS}탭, 이미지X) ===")
        
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1366, "height": 800},
            # 불필요한 요청 차단을 위한 설정
            java_script_enabled=True,
            accept_downloads=False, 
        )
        
        list_page = await context.new_page()
        await list_page.goto(category_url, wait_until="domcontentloaded")
        
        all_checkmark_keys = set()
        total_scanned = 0
        sem = asyncio.Semaphore(CONCURRENT_TABS)
        
        for page_idx in range(1, max_pages + 1):
            print(f"\n[페이지 {page_idx}] 링크 수집 중...")
            links = await collect_links_on_page(list_page, None)
            
            if not links:
                print("  - 상품이 없습니다. 종료.")
                break
                
            print(f"  - {len(links)}개 상품 병렬 분석 시작...")
            
            tasks = []
            for link in links:
                if max_total_items and total_scanned >= max_total_items:
                    break
                tasks.append(process_product_page(context, link, sem))
                total_scanned += 1
            
            if not tasks:
                break
                
            # 병렬 실행
            results = await asyncio.gather(*tasks)
            
            # 결과 수집
            for keys_list in results:
                all_checkmark_keys.update(keys_list)
            
            print(f"  - 완료! 누적 {len(all_checkmark_keys)}개 체크마크 항목 발견")
            
            # 다음 페이지로 이동
            if max_total_items and total_scanned >= max_total_items:
                break
            if page_idx < max_pages:
                if not await paginate(list_page, page_idx + 1):
                    print("  - 다음 페이지로 이동 실패. 종료.")
                    break
        
        await browser.close()
        
        # 결과 정리 및 저장
        unique_items = sorted(all_checkmark_keys)
        mapping = {
            "count": len(unique_items),
            "items": unique_items,
        }
        
        from pathlib import Path
        output_path = Path(mapping_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(mapping_output, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2, sort_keys=True)
        
        print(f"\n[완료] {total_scanned}개 상품 스캔, {len(unique_items)}개 체크마크 항목 발견")
        print(f"[저장] 결과가 '{mapping_output}' 파일에 저장되었습니다.")


def parse_args():
    parser = argparse.ArgumentParser(description="Danawa category pattern learner (고속 비동기 버전)")
    parser.add_argument("--category-url", required=True, help="Danawa category URL (list view)")
    parser.add_argument("--pages", type=int, default=10, help="Max pages to scan")
    parser.add_argument("--max-total-items", type=int, default=0, help="Stop after N items (0=unlimited)")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--mapping-output", required=True, help="Output JSON filepath")
    return parser.parse_args()


def main():
    args = parse_args()
    asyncio.run(run_async_scan(
        category_url=args.category_url,
        max_pages=args.pages,
        headless=args.headless,
        max_total_items=(args.max_total_items or None),
        mapping_output=args.mapping_output,
    ))


if __name__ == "__main__":
    main()