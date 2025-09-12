import sqlite3
import os

os.makedirs("db", exist_ok=True)

# Initialize query_history.db
conn = sqlite3.connect("db/query_history.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS queries
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              query_text TEXT,
              response_text TEXT,
              source TEXT,
              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
              query_count INTEGER)''')
conn.commit()
conn.close()

# Initialize exchange_rates.db
conn = sqlite3.connect("db/exchange_rates.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS rates
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              currency_from TEXT,
              currency_to TEXT,
              rate REAL,
              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()
conn.close()