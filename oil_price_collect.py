import yfinance as yf
import pandas as pd
from datetime import datetime

"""
    [데이터 컬럼 의미 상세 설명]
    1. date: 기준 날짜 (YYYY-MM-DD)
    2. oil_price_wti: 서부 텍사스산 원유(WTI) 1배럴당 가격 ($)
       - 해운사 연료비(Bunker Fuel)의 핵심 변수. 상승 시 약 1~2주 뒤 운임(SCFI) 상승 요인.
    3. usd_krw: 원/달러 환율 (KRW)
       - 해운 운임은 달러($) 기준이므로, 환율 하락 시 원화 환산 수익성에 영향.
    4. hmm_stock: HMM(011200) 종가 (KRW)
       - 시장의 선행 지표. 운임 상승 기대감이 반영되는 지수.
"""

def generate_market_csv(start_date="2025-01-01", end_date="2026-04-06"):
    print(f"🚀 마켓 데이터 수집 시작 ({start_date} ~ {end_date})...")
    
    # 1. 티커 설정 (WTI유 선물, 원/달러 환율, HMM 주가)
    tickers = {
        "CL=F": "oil_price_wti",
        "KRW=X": "usd_krw",
        "011200.KS": "hmm_stock"
    }
    
    # 2. 데이터 다운로드 및 통합
    market_df = pd.DataFrame()
    
    for ticker, col_name in tickers.items():
        print(f"📡 {ticker} 수집 중...")
        # Close(종가) 데이터만 추출
        data = yf.download(ticker, start=start_date, end=end_date)['Close']
        market_df[col_name] = data
        
    # 3. 데이터 전처리 (중요!)
    # 날짜 인덱스를 컬럼으로 빼고, 주말/공휴일 결측치를 직전 영업일 가격으로 채움
    market_df = market_df.sort_index().ffill().bfill().reset_index()
    
    # 컬럼명 정리 (Date, oil_price_wti, usd_krw, hmm_stock)
    market_df.columns = ['date'] + list(tickers.values())
    
    # 날짜 포맷팅 (YYYY-MM-DD) - Databricks에서 인식하기 가장 좋음
    market_df['date'] = market_df['date'].dt.strftime('%Y-%m-%d')
    
    # 4. CSV 저장
    file_name = f"market_data_{start_date.replace('-', '')}_{end_date.replace('-', '')}.csv"
    market_df.to_csv(file_name, index=False, encoding='utf-8-sig')
    
    print("-" * 50)
    print(f"✅ 수집 완료: {len(market_df)}행")
    print(f"💾 파일명: {file_name}")
    print(market_df.tail(5)) # 하위 5행 출력해서 확인

if __name__ == "__main__":
    # 입항 데이터가 25년 4월부터이므로, 모델 학습용 시차(Lag)를 고려해 1월부터 수집
    generate_market_csv(start_date="2025-01-01", end_date="2026-04-06")