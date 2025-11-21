# database.py
import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple

# GLOBAL DATABASE NAME
DB_NAME = "chat_history.db"

def create_database(db_name: str = DB_NAME):
    """Create the database and table if they don't exist."""
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                output TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"Database '{db_name}' created/verified successfully.")
    
    except sqlite3.Error as e:
        print(f"Error creating database: {e}")

def append_data(role: str, output: str, db_name: str = DB_NAME) -> bool:
    """Append a new record to the database."""
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chat_records (role, output)
            VALUES (?, ?)
        ''', (role, output))
        
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        
        print(f"Record added successfully with ID: {record_id}")
        return True
    
    except sqlite3.Error as e:
        print(f"Error appending data: {e}")
        return False

def delete_all_records(db_name: str = DB_NAME) -> bool:
    """Delete all records from the database table."""
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM chat_records')
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"All records deleted successfully. Total deleted: {deleted_count}")
        return True
    
    except sqlite3.Error as e:
        print(f"Error deleting records: {e}")
        return False

def get_all_records(db_name: str = DB_NAME) -> List[Tuple]:
    """Retrieve all records from the database."""
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM chat_records ORDER BY id')
        records = cursor.fetchall()
        
        conn.close()
        return records
    
    except sqlite3.Error as e:
        print(f"Error retrieving records: {e}")
        return []

def get_last_n_records(n: int, db_name: str = DB_NAME) -> List[Tuple]:
    """Retrieve the last N records from the database."""
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM chat_records
            ORDER BY id DESC
            LIMIT ?
        ''', (n,))

        records = cursor.fetchall()
        conn.close()

        # To get them in chronological order (oldest first), reverse the list:
        return list(reversed(records))

    except sqlite3.Error as e:
        print(f"Error retrieving last {n} records: {e}")
        return []

# Initialize database on module import
create_database()
