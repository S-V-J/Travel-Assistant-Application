import sqlite3
import logging
from datetime import datetime, timedelta
from config import DB_PATH

logger = logging.getLogger(__name__)

def init_query_db():
    """Initialize the query history database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                model_type TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                date TEXT,
                query_count INTEGER DEFAULT 1
            )
        ''')
        conn.commit()
        logger.info("Query history database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()

def check_cache(query: str) -> str:
    """Check if a query is in the cache and return the response if not expired."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        one_hour_ago = datetime.now() - timedelta(hours=1)
        c.execute('''
            SELECT response FROM query_history 
            WHERE query = ? AND timestamp > ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (query, one_hour_ago))
        result = c.fetchone()
        if result:
            logger.info(f"Cache hit for query: {query}")
            return result[0]
        return ""
    except Exception as e:
        logger.error(f"Error checking cache: {e}")
        return ""
    finally:
        conn.close()

def store_query_response(query: str, response: str, model_type: str, date: str = None, query_count: int = 1):
    """Store query and response in the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO query_history (query, response, model_type, date, query_count) 
            VALUES (?, ?, ?, ?, ?)
        ''', (query, response, model_type, date or datetime.now().strftime('%Y-%m-%d'), query_count))
        conn.commit()
        logger.info(f"Stored query: {query}")
    except Exception as e:
        logger.error(f"Error storing query: {e}")
    finally:
        conn.close()

def cleanup_old_entries():
    """Remove entries older than 24 hours from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        one_day_ago = datetime.now() - timedelta(days=1)
        c.execute('''
            DELETE FROM query_history 
            WHERE timestamp < ?
        ''', (one_day_ago,))
        conn.commit()
        logger.info(f"Cleaned up {c.rowcount} old entries from database")
    except Exception as e:
        logger.error(f"Error cleaning up database: {e}")
    finally:
        conn.close()