import requests
import xmltodict
import json
import pandas as pd
import time
import os
from urllib.parse import unquote
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env 로드
load_dotenv()

# 1. 설정
# 환경변수 가져오기
RAW_SERVICE_KEY = os.getenv("RAW_SERVICE_KEY")
BASE_URL = "http://apis.data.go.kr/1192000/VsslEtrynd5/Info5"
SERVICE_KEY = unquote(RAW_SERVICE_KEY)

# 저장 폴더 설정
SAVE_DIR = "data/collect_backup"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

COL_MAP = {
    'prtAgCd': '항구청코드', 'prtAgNm': '항구청명', 'etryptYear': '입출항년도',
    'etryptCo': '입출항횟수', 'clsgn': '호출부호', 'vsslNm': '선박명',
    'vsslNltyCd': '국적코드', 'vsslNltyNm': '국적명', 'vsslKndCd': '선종코드',
    'vsslKndNm': '선종명', 'etryptPurpsCd': '목적코드', 'etryptPurpsNm': '입항목적',
    'frstDpmprtNatPrtCd': '최초출발항코드', 'frstDpmprtPrtNm': '최초출발항명',
    'prvsDpmprtNatPrtCd': '직전출발항코드', 'prvsDpmprtPrtNm': '직전출발항명',
    'nxlnptNatPrtCd': '다음입항코드', 'nxlnptPrtNm': '다음입항명',
    'dstnNatPrtCd': '목적지코드', 'dstnPrtNm': '목적지항명',
    'reqstSeNm': '신청구분', 'etryndNm': '입출항구분',
    'etryptDt': '입항일시', 'tkoffDt': '출항일시',
    'ibobprtNm': '내외항구분', 'laidupFcltyCd': '계류시설코드',
    'laidupFcltySubCd': '선석코드', 'laidupFcltyNm': '계류시설명',
    'tugYn': '예선사용', 'piltgYn': '도선사용',
    'ldadngFrghtClCd': '화물종류코드', 'ldadngTon': '적재톤수',
    'trnpdtTon': '환적톤수', 'landngFrghtTon': '양하톤수',
    'ldFrghtTon': '선적톤수', 'grtg': '총톤수', 'intrlGrtg': '국제총톤수',
    'satmntEntrpsNm': '대리점명', 'crewCo': '승무원수',
    'koranCrewCo': '한국인승무원', 'frgnrCrewCo': '외국인승무원',
    'mrNum': 'MR번호', 'tkoffPrrrnDt': '출항예정일시', 'dstnEtryptDt': '목적지입항예정'
}

PORT_CODES = {'020': '부산항'}
HMM_KEYWORDS = '현대|HMM|에이치엠엠|Hyundai'

def parse_items(xml_text):
    try:
        raw = xmltodict.parse(xml_text)
        items = raw.get('response', {}).get('body', {}).get('items', {})
        if not items or not items.get('item'): return []
        
        item_list = items['item']
        items_list = item_list if isinstance(item_list, list) else [item_list]
        
        rows = []
        for item in items_list:
            base = {k: v for k, v in item.items() if k != 'details'}
            details = item.get('details')
            if details and details.get('detail'):
                detail_list = details['detail']
                if isinstance(detail_list, dict): detail_list = [detail_list]
                for det in detail_list: rows.append({**base, **det})
            else:
                rows.append(base)
        return rows
    except Exception as e:
        print(f"  ⚠️ 파싱 오류: {e}")
        return []

def get_total_count(port_code, date_str):
    params = {'serviceKey': SERVICE_KEY, 'prtAgCd': port_code, 'sde': date_str, 'ede': date_str, 'deGb': 'I', 'pageNo': '1', 'numOfRows': '1'}
    try:
        res = requests.get(BASE_URL, params=params, timeout=15)
        raw = xmltodict.parse(res.text)
        return int(raw.get('response', {}).get('body', {}).get('totalCount', '0'))
    except: return 0

def fetch_one_day(port_code, date_str):
    total = get_total_count(port_code, date_str)
    if total == 0: return []

    page_size = 100
    all_rows = []
    for page in range(1, (total // page_size) + 2):
        params = {'serviceKey': SERVICE_KEY, 'prtAgCd': port_code, 'sde': date_str, 'ede': date_str, 'deGb': 'I', 'pageNo': str(page), 'numOfRows': str(page_size)}
        try:
            res = requests.get(BASE_URL, params=params, timeout=15)
            all_rows.extend(parse_items(res.text))
            time.sleep(0.2)
        except: continue

    if not all_rows: return []
    df = pd.DataFrame(all_rows)
    mask = df.apply(lambda r: r.astype(str).str.contains(HMM_KEYWORDS, na=False).any(), axis=1)
    return df[mask].to_dict('records')

def collect_hmm_all(start_date="20240101", end_date="20260406"):
    all_records = []
    start_dt = datetime.strptime(start_date, "%Y%m%d")
    end_dt = datetime.strptime(end_date, "%Y%m%d")
    total_days = (end_dt - start_dt).days + 1

    print(f"🚀 수집 시작: {start_date} ~ {end_date}")

    for i in range(total_days):
        current_date = (start_dt + timedelta(days=i)).strftime("%Y%m%d")
        day_found = 0

        for port_code, port_name in PORT_CODES.items():
            rows = fetch_one_day(port_code, current_date)
            if rows:
                for r in rows: r['_수집항구'] = port_name
                all_records.extend(rows)
                day_found += len(rows)
        
        if day_found > 0:
            print(f"  ✅ {current_date}: {day_found}건 발견 (누적: {len(all_records)})")
            # [중간 저장 1] 매일 최신화 (덮어쓰기)
            temp_df = pd.DataFrame(all_records).rename(columns=COL_MAP)
            temp_df.to_csv(f"{SAVE_DIR}/hmm_latest_checkpoint.csv", index=False, encoding='utf-8-sig')

        # [중간 저장 2] 30일마다 백업 파일 생성
        if (i + 1) % 30 == 0:
            backup_file = f"{SAVE_DIR}/backup_{current_date}.csv"
            pd.DataFrame(all_records).rename(columns=COL_MAP).to_csv(backup_file, index=False, encoding='utf-8-sig')
            print(f"💾 월간 백업 완료: {backup_file}")

    # 최종 저장
    if all_records:
        df_final = pd.DataFrame(all_records).rename(columns=COL_MAP)
        final_name = f"HMM_Final_{start_date}_{end_date}.csv"
        df_final.to_csv(final_name, index=False, encoding='utf-8-sig')
        print(f"\n🏆 수집 종료! 총 {len(df_final)}건 저장 완료.")
    else:
        print("😿 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    # 최근 1년 치 데이터로 우선 수집 (모델 성능 보고 필요하면 더 과거로 확장)
    collect_hmm_all(
        start_date="20250401", 
        end_date="20260406"
    )