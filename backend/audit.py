from snowflake_utils import execute


def create_audit_table():
    execute("""
    CREATE TABLE IF NOT EXISTS LOAD_AUDIT (
        FILE_NAME STRING,
        TARGET_TABLE STRING,
        LOAD_TIME TIMESTAMP_NTZ,
        ROWS_LOADED NUMBER,
        STATUS STRING,
        ERROR_MESSAGE STRING
    )
    """)


def insert_audit(file_name, target_table, rows_loaded, status, error=None):
    sql = """
    INSERT INTO LOAD_AUDIT (FILE_NAME, TARGET_TABLE, LOAD_TIME, ROWS_LOADED, STATUS, ERROR_MESSAGE)
    VALUES (%s, %s, CURRENT_TIMESTAMP(), %s, %s, %s)
    """
    execute(sql, (file_name, target_table, rows_loaded, status, error))
