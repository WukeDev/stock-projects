import psycopg
import pandas as pd
import psycopg.sql
import requests
from io import StringIO

def insert_daily_dp_volume(conn: psycopg.Connection, date, table_name = 'daily', ticker_col = 'ticker', date_col = 'day', buy_vol = 'dp_buy_volume', sell_vol = 'dp_sell_volume', vol_rate = 'dp_volume_rate'):
    #Construct url for parsing
    try:
        date = pd.to_datetime(date)
    except:
        return False
    date = date.strftime('%Y%m%d')
    file_url = f'http://cdn.finra.org/equity/regsho/daily/CNMSshvol{date}.txt'
    # Headers to simulate a request from a web browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(file_url, headers=headers)
    
    #Make a data frame from url and drop the last line
    df = pd.read_csv(StringIO(response.text), delimiter='|')
    df = df.iloc[:-1]
    df.rename(columns={
        'ShortVolume': buy_vol,  # Buy volume -> dp_buy_volume
        'Date': date_col,
        'Symbol': ticker_col,
    }, inplace=True)
    
    try:
        df[sell_vol] = df['TotalVolume'] - df[buy_vol]
    except:
        return False
    df[date_col] = pd.to_datetime(df[date_col], format='%Y%m%d')
    df[date_col] = df[date_col].dt.strftime('%Y-%m-%d')
    #Calculate rate = buy_voluume / sell_volume and set to -1 if infinite
    df[vol_rate] = df.apply(lambda row: row[buy_vol] / row[sell_vol] if row[sell_vol] != 0 else -1, axis = 1)
    
    #Query database
    cur = conn.cursor()
    selected_columns = [date_col, ticker_col, buy_vol, sell_vol, vol_rate]
    rows = [tuple(row) for row in df[selected_columns].values]
    selected_columns = ",".join(selected_columns)
    insert_query = f"""INSERT INTO {table_name} ({selected_columns})
                        VALUES (%s, %s, %s, %s, %s)"""
    cur.executemany(insert_query, rows)
    conn.commit()
    return True 
