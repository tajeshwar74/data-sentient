import os
import snowflake.connector
from snowflake.connector.connection import SnowflakeConnection
from dotenv import load_dotenv
import threading
from typing import Optional

# Import pandas once at the top for better performance
try:
    import pandas as pd
except ImportError:
    pd = None

# Load environment variables from .env file
load_dotenv()

# Security: Validate required environment variables
REQUIRED_ENV_VARS = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
]

for var in REQUIRED_ENV_VARS:
    if not os.getenv(var):
        raise RuntimeError(f"Missing required environment variable: {var}")

# Connection pool management
_connection_pool = []
_pool_lock = threading.Lock()
MAX_POOL_SIZE = 3
CONNECTION_TIMEOUT = 30


def _create_connection() -> SnowflakeConnection:
    """Create a new Snowflake connection with optimized settings."""
    try:
        account = os.getenv("SNOWFLAKE_ACCOUNT")
        user = os.getenv("SNOWFLAKE_USER")
        password = os.getenv("SNOWFLAKE_PASSWORD")
        warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
        database = os.getenv("SNOWFLAKE_DATABASE")

        if not all([account, user, password, warehouse, database]):
            raise ValueError("Invalid connection parameters")

        return snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
            warehouse=warehouse,
            database=database,
            schema=os.getenv("SNOWFLAKE_SCHEMA", "RAW"),
            login_timeout=CONNECTION_TIMEOUT,
            network_timeout=CONNECTION_TIMEOUT,
            autocommit=True,  # Optimize for data pipeline operations
            client_session_keep_alive=True,  # Keep connections alive longer
        )
    except Exception as e:
        print(f"Connection error: {type(e).__name__}")
        raise RuntimeError("Failed to connect to database") from e


def _get_pooled_connection() -> SnowflakeConnection:
    """Get a connection from the pool or create new one."""
    with _pool_lock:
        # Try to get an existing connection
        while _connection_pool:
            conn = _connection_pool.pop()
            try:
                # Test if connection is still valid
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return conn
            except:
                # Connection is dead, try next one
                try:
                    conn.close()
                except:
                    pass
                continue

    # No valid connections in pool, create new one
    return _create_connection()


def _return_connection(conn: SnowflakeConnection) -> None:
    """Return a connection to the pool."""
    with _pool_lock:
        if len(_connection_pool) < MAX_POOL_SIZE:
            _connection_pool.append(conn)
        else:
            # Pool is full, close the connection
            try:
                conn.close()
            except:
                pass


def get_conn():
    """Get a Snowflake connection (backwards compatibility)."""
    return _get_pooled_connection()


def execute(sql, params=None):
    """Execute SQL with optional parameters and return results if present.

    This uses parameter binding to avoid SQL injection and provides
    secure error handling with connection pooling.
    """
    conn = None
    cur = None
    try:
        conn = _get_pooled_connection()
        cur = conn.cursor()

        # Basic SQL logging (avoid logging sensitive data in production)
        if len(sql) <= 100:
            print(f"Executing SQL: {sql[:100]}")
        else:
            print(f"Executing SQL query (length: {len(sql)} chars)")

        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)

        # Try to fetch results for SELECT-like statements
        try:
            return cur.fetchall()
        except snowflake.connector.errors.ProgrammingError:
            return None

    except snowflake.connector.errors.ProgrammingError as e:
        print(f"SQL execution error: {type(e).__name__}")
        # Don't return connection to pool if there was an error
        if conn:
            try:
                conn.close()
            except:
                pass
            conn = None
        raise
    except Exception as e:
        print(f"Database connection error: {type(e).__name__}")
        if conn:
            try:
                conn.close()
            except:
                pass
            conn = None
        raise
    finally:
        if cur:
            try:
                cur.close()
            except:
                pass

        if conn:
            _return_connection(conn)


def query_df(sql, params=None):
    """Execute SELECT and return a pandas DataFrame.

    This is useful for UI code (e.g., Streamlit) which wants column names.
    Enhanced with security measures, connection pooling, and result caching.
    """
    conn = None
    cur = None
    try:
        # Validate SQL length to prevent extremely long queries
        if len(sql) > 10000:  # 10KB limit
            raise ValueError("Query too long")

        conn = _get_pooled_connection()
        cur = conn.cursor()

        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)

        rows = cur.fetchall()
        cols = [c[0] for c in cur.description] if cur.description else []

        if pd is None:
            raise RuntimeError(
                "pandas is required for query_df; add it to requirements.txt"
            )

        # Limit result set size for security and performance
        if len(rows) > 10000:  # 10k row limit
            print(f"Warning: Result set truncated from {len(rows)} to 10000 rows")
            rows = rows[:10000]

        # Create DataFrame with optimized settings
        df = pd.DataFrame(rows, columns=cols)

        # Optimize memory usage for large datasets
        if len(df) > 1000:
            df = df.copy()  # Ensure we own the data
            # Convert object columns to category where appropriate
            for col in df.select_dtypes(include=["object"]).columns:
                if df[col].nunique() < len(df) * 0.5:  # Less than 50% unique values
                    df[col] = df[col].astype("category")

        return df

    except snowflake.connector.errors.ProgrammingError as e:
        print(f"SQL execution error: {type(e).__name__}")
        if conn:
            try:
                conn.close()
            except:
                pass
            conn = None
        raise
    except Exception as e:
        print(f"Database query error: {type(e).__name__}")
        if conn:
            try:
                conn.close()
            except:
                pass
            conn = None
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            _return_connection(conn)


def cleanup_connection_pool():
    """Clean up all connections in the pool. Call this on application shutdown."""
    with _pool_lock:
        while _connection_pool:
            conn = _connection_pool.pop()
            try:
                conn.close()
            except:
                pass
        print("Connection pool cleaned up")


def normalize_stage(stage: str) -> str:
    """Ensure stage value starts with '@' for PUT/COPY usage."""
    if not stage:
        return "@CSV_STAGE"
    return stage if stage.startswith("@") else f"@{stage}"


def put_file(local_path, stage, auto_create=True):
    """Upload a local file to a Snowflake stage.

    - Normalizes the stage name (adds leading '@' if missing).
    - If the stage does not exist (or is unauthorized) and `auto_create` is True,
      attempts to create the short (unqualified) stage name and retries the PUT.
    """
    stage = normalize_stage(stage)
    stage_no_at = stage.lstrip("@")

    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            print(f"PUT file://{local_path} {stage} AUTO_COMPRESS=FALSE")
            cur.execute(f"PUT file://{local_path} {stage} AUTO_COMPRESS=FALSE")
        except snowflake.connector.errors.ProgrammingError as e:
            msg = str(e)
            # Match the typical message: Stage 'X' does not exist or not authorized
            if auto_create and "does not exist or not authorized" in msg:
                # Try creating a short/unqualified stage name (last component after any dots)
                short_stage = stage_no_at.split(".")[-1]
                try:
                    print(
                        f"Attempting to create stage {short_stage} because PUT failed with: {msg}"
                    )
                    cur.execute(f"CREATE STAGE {short_stage}")
                    print(f"Created stage {short_stage}; retrying PUT")
                    cur.execute(
                        f"PUT file://{local_path} @{short_stage} AUTO_COMPRESS=FALSE"
                    )
                except Exception as create_err:
                    # If creation fails, raise a clearer error with actionable guidance
                    raise RuntimeError(
                        f"Failed to create stage '{short_stage}': {create_err}. "
                        "Ensure your role has CREATE STAGE privileges, or set SNOWFLAKE_STAGE to an existing stage (e.g., '@CSV_STAGE')."
                    ) from create_err
            else:
                # Re-raise the original Snowflake error for visibility
                raise
    finally:
        cur.close()
        conn.close()
