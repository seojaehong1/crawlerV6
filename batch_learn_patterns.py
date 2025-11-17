import asyncio
import subprocess
import sys
from pathlib import Path

def load_txt_file(filename):
    """텍스트 파일을 리스트로 로드"""
    with open(filename, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def main():
    # 파일 로드
    urls = load_txt_file('카테고리별 url.txt')
    names = load_txt_file('카테고리이름.txt')
    product_counts = load_txt_file('상품수.txt')
    
    # patterns2 디렉토리 확인
    patterns_dir = Path('patterns2')
    patterns_dir.mkdir(exist_ok=True)
    
    # 이미 존재하는 파일 확인 (19번 유모차는 제외)
    existing_files = set()
    for json_file in patterns_dir.glob('*.json'):
        # 파일명에서 번호 추출 (예: 19_유모차.json -> 19)
        try:
            num = int(json_file.stem.split('_')[0])
            existing_files.add(num)
        except:
            pass
    
    print(f"총 {len(urls)}개 카테고리 중 {len(existing_files)}개 이미 완료됨")
    print(f"처리할 카테고리: {len(urls) - len(existing_files)}개\n")
    
    # 각 카테고리 처리
    for idx in range(len(urls)):
        category_num = idx + 1  # 1부터 시작
        
        # 이미 처리된 카테고리는 스킵
        if category_num in existing_files:
            print(f"[{category_num}/{len(urls)}] {names[idx]} - 이미 완료됨, 스킵")
            continue
        
        url = urls[idx]
        name = names[idx]
        product_count = product_counts[idx] if idx < len(product_counts) else "N/A"
        
        # 출력 파일 경로
        output_file = patterns_dir / f"{category_num}_{name}.json"
        
        print(f"\n[{category_num}/{len(urls)}] {name} 처리 시작...")
        print(f"  URL: {url}")
        print(f"  상품 수: {product_count}")
        print(f"  출력: {output_file}")
        
        # 상품 수에 따라 페이지 수 결정 (페이지당 약 40개 상품 가정)
        try:
            count = int(product_count)
            # 최대 10페이지, 최소 1페이지
            pages = min(max(1, count // 40), 10)
        except:
            pages = 10  # 기본값
        
        # pattern_learn_final.py 실행
        cmd = [
            sys.executable,
            'pattern_learn_final.py',
            '--category-url', url,
            '--pages', str(pages),
            '--max-total-items', '0',  # 제한 없음
            '--headless',  # 헤드리스 모드
            '--mapping-output', str(output_file)
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
            print(f"  ✓ 완료!")
            if result.stdout:
                # 마지막 몇 줄만 출력
                lines = result.stdout.strip().split('\n')
                for line in lines[-3:]:
                    if line.strip():
                        print(f"    {line}")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ 오류 발생!")
            print(f"    {e.stderr}")
            continue
    
    print(f"\n모든 카테고리 처리 완료!")

if __name__ == "__main__":
    main()

