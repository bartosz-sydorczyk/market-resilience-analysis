import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine, text

# --- 1. EXTRACT ---
end_date = datetime.today()
start_date = datetime(end_date.year - 5, 1, 1)

tickers = ["SPY", "TLT"]
print(f"Fetching historical data for {tickers} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")

raw_data = yf.download(tickers, start=start_date, end=end_date)['Close']

# --- 2. TRANSFORM ---
clean_data = raw_data.reset_index().melt(
    id_vars=['Date'],
    var_name='Ticker',
    value_name='Close_Price'
)
clean_data['Close_Price'] = clean_data['Close_Price'].round(2)
clean_data = clean_data.dropna()

assets_dictionary = {
    'Ticker': ['SPY', 'TLT'],
    'Asset_Name': ['SPDR S&P 500 ETF Trust', 'iShares 20+ Year Treasury Bond ETF'],
    'Asset_Class': ['Equity', 'Fixed Income'],
    'Risk_Level': ['High', 'Low']
}
dim_assets = pd.DataFrame(assets_dictionary)

# --- 3. LOAD (Professional Database Creation) ---
print("\nConnecting to MS SQL Server...")

# Safely load environment variables
if not os.path.exists('.env'):
    print("WARNING: '.env' file not found!")
    print("Please create a '.env' file in the root directory and define 'DB_PASSWORD=your_password'.")
    sys.exit(1)

load_dotenv()

# Download password from environment
db_password = os.getenv("DB_PASSWORD")
if not db_password:
    print("WARNING: 'DB_PASSWORD' variable is missing in the .env file.")
    sys.exit(1)

db_name = "MarketResilience"

try:
    # Step 3A: Connect to 'master' with AUTOCOMMIT to create the new database
    engine_master = create_engine(
        f"mssql+pymssql://sa:{db_password}@localhost:1433/master",
        isolation_level="AUTOCOMMIT"
    )

    print(f"Checking if database '{db_name}' exists...")
    with engine_master.connect() as conn:
        create_db_query = f"""
        IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{db_name}')
        BEGIN
            CREATE DATABASE {db_name}
        END
        """
        conn.execute(text(create_db_query))

    # Step 3B: Connect directly to our new database
    print(f"Connecting to the new database: {db_name}...")
    engine_target = create_engine(f"mssql+pymssql://sa:{db_password}@localhost:1433/{db_name}")

    print("Loading data into 'fact_prices' table...")
    clean_data.to_sql('fact_prices', con=engine_target, if_exists='replace', index=False)

    print("Loading data into 'dim_assets' table...")
    dim_assets.to_sql('dim_assets', con=engine_target, if_exists='replace', index=False)

    print(f"ETL process completed successfully! Data is live in the '{db_name}' database.")

except Exception as e:
    print(f"An error occurred during database operations: {e}")
