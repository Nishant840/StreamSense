import logging
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from datetime import datetime
from schemas import LogEvent, AnomalyResponse
import os
from contextlib import contextmanager

logger = logging.getLogger("anomaly-store")

DB_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/streamsense"
)

# Initialize a global thread-safe connection pool
db_pool = None

def init_db() -> None:
    global db_pool
    if not db_pool:
        db_pool = psycopg2.pool.ThreadedConnectionPool(1, 20, DB_URL)
        
    sql = """
        CREATE TABLE IF NOT EXISTS anomalies(
            id              SERIAL PRIMARY KEY,
            service         VARCHAR(100) NOT NULL,
            timestamp       VARCHAR(50)  NOT NULL,
            level           VARCHAR(20)  NOT NULL,
            message         TEXT         NOT NULL,
            template        TEXT,
            template_id     INTEGER,
            anomaly_score   FLOAT        NOT NULL,
            created_at      TIMESTAMP    DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_anomalies_service
            ON anomalies(service);

        CREATE INDEX IF NOT EXISTS idx_anomalies_created_at
            ON anomalies(created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_anomalies_score
            ON anomalies(anomaly_score DESC);
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    logger.info("Database intialized")

@contextmanager
def get_connection():
    global db_pool
    if not db_pool:
        db_pool = psycopg2.pool.ThreadedConnectionPool(1, 20, DB_URL)
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)

def save_anomaly(event: dict) -> int:
    sql = """
            INSERT INTO anomalies
                (service, timestamp, level, message, template, template_id, anomaly_score)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                event.get("service"),
                event.get("timestamp"),
                event.get("level"),
                event.get("message"),
                event.get("template"),
                event.get("template_id"),
                event.get("anomaly_score")
            ))
            anomaly_id = cur.fetchone()[0]
        conn.commit()
    return anomaly_id

def get_recent_anomalies(limit: int = 50) -> list[dict]:
    sql = """
        SELECT service, timestamp, level, message, template, anomaly_score
        FROM anomalies
        ORDER BY created_at DESC
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
            
    return [dict(row) for row in rows]

def get_anomalies(service: str | None = None, limit: int = 50) -> list[AnomalyResponse]:
    query = """
        SELECT id, service, timestamp, level, message, template, anomaly_score, created_at
        FROM anomalies
    """
    params = []
    
    if service:
        query += " WHERE service = %s"
        params.append(service)
        
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    anomalies = []
    for row in rows:
        anomalies.append(
            AnomalyResponse(
                id              = row["id"],
                service         = row["service"],
                timestamp       = row["timestamp"],
                level           = row["level"],
                message         = row["message"],
                anomaly_score   = row["anomaly_score"],
                template        = row["template"],
                created_at      = row["created_at"]
            )
        )
    return anomalies

def get_anomaly_count(service: str | None = None) -> int:
    query = "SELECT COUNT(*) FROM anomalies"
    params = []
    if service:
        query += " WHERE service = %s"
        params.append(service)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            count = cur.fetchone()[0]
            
    return count
