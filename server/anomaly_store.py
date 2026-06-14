import logging
import psycopg2
import psycopg2.extras
from datetime import datetime
from schemas import LogEvent, AnomalyResponse

logger = logging.getLogger("anomaly-store")

DB_CONFIG = {
    "dbname":   "streamsense",
    "user":     "streamsense",
    "password": "streamsense123",
    "host":     "localhost",
    "port":     5432
}

def get_connection() -> psycopg2.extensions.connection:
    return psycopg2.connect(**DB_CONFIG)

def init_db() -> None:
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

def save_anomaly(event: LogEvent) -> int:
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
                event.service,
                event.timestamp,
                event.level,
                event.message,
                event.template,
                event.template_id,
                event.anomaly_score,
            ))
            row_id = cur.fetchone()[0]
        conn.commit()

    logger.info(f"Saved anomaly | id={row_id} service={event.service}")
    return row_id

def get_anomalies(
        service:    str | None = None,
        limit:      int        = 50,
) -> list[AnomalyResponse]:
    if service:
        sql     = """
            SELECT id, service, timestamp, level, message,
                    template, template_id, anomaly_score, created_at
            FROM anomalies
            WHERE service = %s
            ORDER BY created_at DESC
            LIMIT %s;
        """
        params = (service, limit)
    else:
        sql     = """
            SELECT id, service, timestamp, level, message,
                    template, template_id, anomaly_score, created_at
            FROM anomalies
            ORDER BY created_at DESC
            LIMIT %s;
        """
        params = (limit,)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [AnomalyResponse(**row) for row in rows]

def get_anomaly_count(service: str | None = None) -> int:
    if service:
        sql     = "SELECT COUNT(*) FROM anomalies WHERE service = %s;"
        params  = (service,)
    else:
        sql     = "SELECT COUNT(*) FROM anomalies"
        params  = ()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]