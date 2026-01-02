import sqlite3
import json
from datetime import datetime
import hashlib

def get_listing_hash(listing):
    """Generate a SHA256 hash from the listing's title and description"""
    combined = listing['title'] + listing['description']
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file"""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(e)
    return conn

def create_table(conn):
    """Create the evaluations table if it doesn't exist"""
    sql = """ CREATE TABLE IF NOT EXISTS evaluations (
                id text PRIMARY KEY,
                data text NOT NULL,
                timestamp text
            ); """
    try:
        c = conn.cursor()
        c.execute(sql)
    except sqlite3.Error as e:
        print(e)

def insert_evaluation(conn, evaluation):
    """Insert an evaluation dict into the database, using hash as ID"""
    hash_id = get_listing_hash(evaluation['listing'])
    data = json.dumps(evaluation)
    timestamp = datetime.now().isoformat()
    sql = ''' INSERT OR REPLACE INTO evaluations(id, data, timestamp)
              VALUES(?, ?, ?) '''
    cur = conn.cursor()
    cur.execute(sql, (hash_id, data, timestamp))
    conn.commit()
    return hash_id

def evaluation_exists(conn, listing):
    """Check if an evaluation for the given listing already exists in the database"""
    hash_id = get_listing_hash(listing)
    cur = conn.cursor()
    cur.execute("SELECT id FROM evaluations WHERE id = ?", (hash_id,))
    return cur.fetchone() is not None

def get_all_evaluations(conn):
    """Retrieve all evaluations from the database"""
    cur = conn.cursor()
    cur.execute("SELECT id, data, timestamp FROM evaluations ORDER BY timestamp DESC")
    rows = cur.fetchall()
    evaluations = []
    for row in rows:
        data = json.loads(row[1])
        data['db_id'] = row[0]
        data['timestamp'] = row[2]
        evaluations.append(data)
    return evaluations

def get_evaluation_by_id(conn, evaluation_id):
    """Retrieve a specific evaluation by its database ID (hash)"""
    cur = conn.cursor()
    cur.execute("SELECT id, data, timestamp FROM evaluations WHERE id = ?", (evaluation_id,))
    row = cur.fetchone()
    if row:
        data = json.loads(row[1])
        data['db_id'] = row[0]
        data['timestamp'] = row[2]
        return data
    return None

def get_evaluations_by_score(conn, min_score=None, max_score=None):
    """Retrieve evaluations filtered by percentile score range"""
    cur = conn.cursor()
    if min_score is not None and max_score is not None:
        cur.execute("SELECT id, data, timestamp FROM evaluations WHERE json_extract(data, '$.percentile_score') BETWEEN ? AND ? ORDER BY timestamp DESC", (min_score, max_score))
    elif min_score is not None:
        cur.execute("SELECT id, data, timestamp FROM evaluations WHERE json_extract(data, '$.percentile_score') >= ? ORDER BY timestamp DESC", (min_score,))
    elif max_score is not None:
        cur.execute("SELECT id, data, timestamp FROM evaluations WHERE json_extract(data, '$.percentile_score') <= ? ORDER BY timestamp DESC", (max_score,))
    else:
        return get_all_evaluations(conn)
    
    rows = cur.fetchall()
    evaluations = []
    for row in rows:
        data = json.loads(row[1])
        data['db_id'] = row[0]
        data['timestamp'] = row[2]
        evaluations.append(data)
    return evaluations

def delete_all_evaluations(conn):
    """Delete all evaluations from the database"""
    sql = ''' DELETE FROM evaluations '''
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    return cur.rowcount