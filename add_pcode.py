import csv
import re
from pathlib import Path

def extract_pcode_from_url(url: str) -> str:
    """URL에서 pcode 추출"""
    if not url:
        return ""
    match = re.search(r'pcode=(\d+)', url)
    if match:
        return match.group(1)
    return ""

def add_pcode_column(input_file: str, output_file: str):
    """CSV 파일에 pcode 컬럼을 맨 앞에 추가"""
    rows = []
    
    # CSV 파일 읽기
    with open(input_file, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        if not fieldnames:
            print("CSV 파일에 헤더가 없습니다.")
            return
        
        # URL 컬럼 찾기
        url_col = None
        for col in fieldnames:
            if 'URL' in col or 'url' in col.lower():
                url_col = col
                break
        
        if not url_col:
            print("URL 컬럼을 찾을 수 없습니다.")
            return
        
        # 각 행 처리
        for row in reader:
            url = row.get(url_col, "")
            pcode = extract_pcode_from_url(url)
            row['pcode'] = pcode
            rows.append(row)
    
    # 새로운 필드명 (pcode를 맨 앞에)
    new_fieldnames = ['pcode'] + [f for f in fieldnames if f != 'pcode']
    
    # CSV 파일 쓰기
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in new_fieldnames})
    
    print(f"완료! {len(rows)}개 행 처리. 결과 파일: {output_file}")

if __name__ == "__main__":
    input_file = "danawa_유모차_output.csv"
    output_file = "danawa_유모차_output_with_pcode.csv"
    
    add_pcode_column(input_file, output_file)

