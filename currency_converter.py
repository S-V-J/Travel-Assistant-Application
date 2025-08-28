# currency_converter.py
# This script fetches exchange rates from exchangeratesapi.io and stores them in a SQLite database.
# It supports local currency conversion and updates the database every 12 hours or on demand.
# Logs currency updates to query_history.db.

import sqlite3
import requests
from datetime import datetime
from typing import Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import time
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('currency_converter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CurrencyConverter:
    def __init__(self, access_key: str, db_path: str = "/home/stjl0/livekit-travel-voice-assistant/db/exchange_rates.db", query_db_path: str = "/home/stjl0/livekit-travel-voice-assistant/db/query_history.db", base_url: str = "http://api.exchangeratesapi.io/v1/"):
        self.access_key = access_key
        self.base_url = base_url
        self.db_path = db_path
        self.query_db_path = query_db_path
        self.scheduler = BackgroundScheduler()
        self.init_db()
        self.schedule_update()

    def init_db(self):
        """Initialize SQLite database with exchange_rates table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS exchange_rates (
                        currency TEXT,
                        rate REAL,
                        timestamp INTEGER,
                        date TEXT,
                        PRIMARY KEY (currency, timestamp)
                    )
                """)
                conn.commit()
            logger.info("Exchange rates database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def check_query_count_column(self) -> bool:
        """Check if query_count column exists in query_history table."""
        try:
            with sqlite3.connect(self.query_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(query_history);")
                columns = [info[1] for info in cursor.fetchall()]
                return "query_count" in columns
        except Exception as e:
            logger.error(f"Error checking query_count column: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """Make API request with retry logic and handle errors."""
        params['access_key'] = self.access_key
        url = f"{self.base_url}{endpoint}"
        logger.info(f"API request: {url} with params: {params}")
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"API request failed: {response.text}")
            raise ValueError(f"API request failed: {response.text}")
        data = response.json()
        if not data.get('success'):
            logger.error(f"API error: {data.get('error', {}).get('message', 'Unknown error')}")
            raise ValueError(f"API error: {data.get('error', {}).get('message', 'Unknown error')}")
        return data

    def update_rates(self, symbols: str = "USD,AUD,CAD,PLN,MXN,EUR,INR,NPR,PKR,BDT,CNY,JPY,RUB,TWD,ZAR,BRL,ARS,EGP,NZD,GBP"):
        """Fetch latest rates from API, store in database, and log to query_history.db."""
        try:
            data = self._make_request("latest", {'symbols': symbols})
            rates = data['rates']
            timestamp = data['timestamp']
            date = data['date']
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for currency, rate in rates.items():
                    cursor.execute(
                        "INSERT OR REPLACE INTO exchange_rates (currency, rate, timestamp, date) VALUES (?, ?, ?, ?)",
                        (currency, rate, timestamp, date)
                    )
                conn.commit()
            
            # Log to query_history.db
            try:
                with sqlite3.connect(self.query_db_path) as conn:
                    cursor = conn.cursor()
                    has_query_count = self.check_query_count_column()
                    if has_query_count:
                        cursor.execute("""
                            INSERT INTO query_history (query, response, tool_name, timestamp, date, query_count)
                            VALUES (?, ?, ?, ?, ?, 1)
                        """, ("update_currency_rates", f"Currency rates updated successfully for {date}.", "update_currency_rates", timestamp, date))
                    else:
                        cursor.execute("""
                            INSERT INTO query_history (query, response, tool_name, timestamp, date)
                            VALUES (?, ?, ?, ?, ?)
                        """, ("update_currency_rates", f"Currency rates updated successfully for {date}.", "update_currency_rates", timestamp, date))
                    conn.commit()
                logger.info(f"Logged currency update to query_history.db for date {date}")
            except Exception as e:
                logger.error(f"Error logging to query_history.db: {e}")
            
            logger.info(f"Updated rates in database: {rates}")
            return {"success": True, "rates": rates, "date": date}
        except Exception as e:
            logger.error(f"Error updating rates: {e}")
            return {"success": False, "error": str(e)}

    def schedule_update(self):
        """Schedule automatic database update every 12 hours."""
        try:
            self.scheduler.add_job(self.update_rates, 'interval', hours=12)
            self.scheduler.start()
            logger.info("Scheduler started for 12-hour updates")
            atexit.register(self._shutdown_scheduler)
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            raise

    def _shutdown_scheduler(self):
        """Gracefully shut down the scheduler."""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("Scheduler shut down successfully")
        except Exception as e:
            logger.warning(f"Error during scheduler shutdown: {e}")

    def get_latest_rates(self, symbols: Optional[str] = None) -> Dict:
        """Retrieve latest rates from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(timestamp) FROM exchange_rates")
                latest_timestamp = cursor.fetchone()[0]
                
                if not latest_timestamp:
                    logger.warning("No rates in database")
                    return {"success": False, "error": "No rates in database. Run update_rates() first."}
                
                query = "SELECT currency, rate, date FROM exchange_rates WHERE timestamp = ?"
                if symbols:
                    currencies = symbols.split(',')
                    query += f" AND currency IN ({','.join(['?'] * len(currencies))})"
                    cursor.execute(query, [latest_timestamp] + currencies)
                else:
                    cursor.execute(query, [latest_timestamp])
                
                rates = {row[0]: row[1] for row in cursor.fetchall()}
                date = cursor.execute("SELECT date FROM exchange_rates WHERE timestamp = ? LIMIT 1", [latest_timestamp]).fetchone()[0]
                
                logger.info(f"Retrieved rates from database for date {date}: {rates}")
                return {
                    "success": True,
                    "base": "EUR",
                    "date": date,
                    "rates": rates
                }
        except Exception as e:
            logger.error(f"Error retrieving rates: {e}")
            return {"success": False, "error": str(e)}

    def convert(self, amount: float, from_cur: str, to_cur: str) -> Dict:
        """Convert currency using rates from database."""
        try:
            rates_data = self.get_latest_rates(symbols=f"{from_cur},{to_cur}")
            if not rates_data['success']:
                logger.warning(f"Conversion failed: {rates_data['error']}")
                return rates_data
            
            rates = rates_data['rates']
            if from_cur not in rates or to_cur not in rates:
                logger.warning(f"Currency {from_cur} or {to_cur} not supported")
                return {"success": False, "error": f"Currency {from_cur} or {to_cur} not supported"}
            
            rate = rates[to_cur] / rates[from_cur] if from_cur != 'EUR' else rates[to_cur]
            result = round(amount * rate, 2)
            logger.info(f"Converted {amount} {from_cur} to {result} {to_cur}")
            return {
                "success": True,
                "from": from_cur,
                "to": to_cur,
                "amount": amount,
                "result": result,
                "date": rates_data['date']
            }
        except Exception as e:
            logger.error(f"Error converting currency: {e}")
            return {"success": False, "error": str(e)}

# Run as a background service
if __name__ == "__main__":
    api_key = "97326437d895b9a62b32a4ca74482f62"
    converter = CurrencyConverter(api_key, query_db_path="/home/stjl0/livekit-travel-voice-assistant/db/query_history.db")
    
    # Initial update
    logger.info("Starting initial rates update")
    result = converter.update_rates()
    logger.info(f"Initial rates update result: {result}")
    
    # Keep the script running for the scheduler
    try:
        while True:
            time.sleep(60)  # Sleep to keep the script running
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
        converter._shutdown_scheduler()