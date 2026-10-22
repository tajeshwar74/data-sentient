import pandas as pd
import os
import re
from snowflake_utils import execute, put_file
from audit import create_audit_table, insert_audit
from langchain_utils import get_csv_analysis_agent

_raw_stage = os.getenv("SNOWFLAKE_STAGE", "@CSV_STAGE")


def normalize_stage(stage_env_var):
    """Normalize stage name from environment variable."""
    if not stage_env_var:
        return "@CSV_STAGE"

    # If it already starts with @, use as-is
    if stage_env_var.startswith("@"):
        return stage_env_var

    # If it contains dots (database.schema.stage), use the simple stage name
    if "." in stage_env_var:
        # Extract just the stage name (last part after dots)
        stage_parts = stage_env_var.split(".")
        simple_stage = stage_parts[-1]  # Last part is the stage name
        return f"@{simple_stage}"

    # Otherwise, just add @ prefix
    return f"@{stage_env_var}"


STAGE = normalize_stage(_raw_stage)


def normalize_table_name(file_name: str) -> str:
    """
    Normalize file name to create a database-friendly table name.
    Handles hyphens, spaces, and other special characters.

    Args:
        file_name: Original file name (with or without .csv extension)

    Returns:
        Normalized table name suitable for database use
    """
    # Remove .csv extension if present
    table_name = file_name.replace(".csv", "").replace(".CSV", "")

    # Replace hyphens and spaces with underscores
    table_name = table_name.replace("-", "_").replace(" ", "_")

    # Handle other common special characters
    table_name = table_name.replace("(", "_").replace(")", "_")
    table_name = table_name.replace("[", "_").replace("]", "_")
    table_name = table_name.replace("{", "_").replace("}", "_")
    table_name = table_name.replace(".", "_")
    table_name = table_name.replace(",", "_")
    table_name = table_name.replace("'", "_")
    table_name = table_name.replace('"', "_")
    table_name = table_name.replace("\\", "_")
    table_name = table_name.replace("|", "_")
    table_name = table_name.replace("&", "_AND_")
    table_name = table_name.replace("%", "_PCT_")
    table_name = table_name.replace("#", "_NUM_")
    table_name = table_name.replace("@", "_AT_")
    table_name = table_name.replace("*", "_")
    table_name = table_name.replace("+", "_PLUS_")
    table_name = table_name.replace("=", "_EQ_")
    table_name = table_name.replace("?", "_")
    table_name = table_name.replace("!", "_")
    table_name = table_name.replace("<", "_LT_")
    table_name = table_name.replace(">", "_GT_")
    table_name = table_name.replace(":", "_")
    table_name = table_name.replace(";", "_")
    table_name = table_name.replace("~", "_")
    table_name = table_name.replace("^", "_")
    table_name = table_name.replace("$", "_USD")

    # Remove any duplicate underscores
    while "__" in table_name:
        table_name = table_name.replace("__", "_")

    # Remove leading/trailing underscores
    table_name = table_name.strip("_")

    # Convert to uppercase for consistency
    table_name = table_name.upper()

    # Ensure table name starts with a letter or underscore (SQL requirement)
    if table_name and not table_name[0].isalpha() and table_name[0] != "_":
        table_name = "TBL_" + table_name

    # Handle empty table names
    if not table_name:
        table_name = "UNNAMED_TABLE"

    # Limit length to reasonable database limits (most DBs support 128 chars)
    if len(table_name) > 100:
        table_name = table_name[:97] + "_TBL"

    return table_name


def infer_type(dtype):
    if "int" in str(dtype):
        return "NUMBER"
    if "float" in str(dtype):
        return "FLOAT"
    return "STRING"


def analyze_csv_format(file_path):
    """Analyze CSV file to determine the best format parameters."""
    try:
        # Read first few lines to analyze format
        with open(file_path, "r", encoding="utf-8") as f:
            first_lines = [
                f.readline().strip() for _ in range(min(5, sum(1 for _ in f) + 1))
            ]

        if not first_lines:
            return None

        # Detect delimiter
        first_line = first_lines[0] if first_lines else ""
        comma_count = first_line.count(",")
        semicolon_count = first_line.count(";")
        tab_count = first_line.count("\t")

        if comma_count > semicolon_count and comma_count > tab_count:
            delimiter = ","
        elif semicolon_count > tab_count:
            delimiter = ";"
        elif tab_count > 0:
            delimiter = "\t"
        else:
            delimiter = ","

        # Check for quotes
        has_quotes = '"' in first_line or "'" in first_line

        # Check encoding
        encoding = "utf-8"  # Default

        print(
            f"CSV Analysis: delimiter='{delimiter}', has_quotes={has_quotes}, encoding={encoding}"
        )

        return {
            "delimiter": delimiter,
            "has_quotes": has_quotes,
            "encoding": encoding,
            "sample_lines": first_lines[:3],
        }

    except Exception as e:
        print(f"CSV analysis failed: {e}")
        return None


def ingest_csv(local_path, use_agent=True):
    """
    Ingest CSV file into RAW layer with optional agentic analysis.

    Args:
        local_path: Path to the CSV file
        use_agent: Whether to use LangChain agent for analysis (default: True)

    Returns:
        Success/failure message with row count
    """
    create_audit_table()
    file_name = os.path.basename(local_path)

    # Normalize table name to handle hyphens and special characters
    table_name = normalize_table_name(file_name)

    # Print the table name mapping for user visibility
    original_name = file_name.replace(".csv", "").replace(".CSV", "")
    if original_name.upper() != table_name:
        print(f"Table name normalized: '{original_name}' -> '{table_name}'")

    # Optional: Get agentic analysis before ingestion
    agent_analysis = None
    if use_agent:
        try:
            print("⏳ Running agentic CSV analysis...")
            csv_agent = get_csv_analysis_agent()
            agent_analysis = csv_agent.analyze_and_prepare_csv(local_path)
            if agent_analysis.get("status") == "success":
                print(
                    f"✅ Agent Analysis Complete:\n{agent_analysis.get('agent_analysis', '')}"
                )
        except Exception as e:
            print(f"⚠️ Agent analysis skipped: {e}")
            # Continue with normal flow - agent analysis is optional

    try:
        # 0. Analyze CSV format before processing
        csv_format = analyze_csv_format(local_path)
        if csv_format:
            print(f"Detected CSV format: {csv_format}")

        # 1. Read CSV with improved handling for trailing commas and empty columns
        try:
            # Try with detected delimiter first
            if csv_format and csv_format["delimiter"] != ",":
                df = pd.read_csv(local_path, delimiter=csv_format["delimiter"])
            else:
                df = pd.read_csv(local_path)
        except Exception as read_err:
            print(f"Standard CSV read failed: {read_err}")
            # Try with different encodings and delimiters
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                for delimiter in [",", ";", "\t"]:
                    try:
                        print(f"Trying encoding={encoding}, delimiter='{delimiter}'")
                        df = pd.read_csv(
                            local_path, encoding=encoding, delimiter=delimiter
                        )
                        print(
                            f"Successfully read with encoding={encoding}, delimiter='{delimiter}'"
                        )
                        break
                    except:
                        continue
                if "df" in locals():
                    break
            else:
                raise Exception("Could not read CSV with any format combination")

        # Remove any unnamed columns that result from trailing commas
        unnamed_cols = [col for col in df.columns if col.lower().startswith("unnamed")]
        if unnamed_cols:
            print(
                f"Removing {len(unnamed_cols)} unnamed columns caused by trailing commas: {unnamed_cols}"
            )
            df = df.drop(columns=unnamed_cols)

        # Remove completely empty columns
        empty_cols = [col for col in df.columns if df[col].isna().all()]
        if empty_cols:
            print(f"Removing {len(empty_cols)} completely empty columns: {empty_cols}")
            df = df.drop(columns=empty_cols)

        # Strip whitespace from column names
        df.columns = df.columns.str.strip()

        # 2. Create RAW table dynamically with proper schema
        cols = [f'"{c.upper()}" {infer_type(t)}' for c, t in df.dtypes.items()]
        ddl = f"CREATE OR REPLACE TABLE RAW.{table_name} ({', '.join(cols)});"
        print(f"Creating table with DDL: {ddl}")
        execute(ddl)

        # 3. Upload file to stage (using simple stage name)
        print(f"Uploading {file_name} to stage {STAGE}")
        put_file(local_path, STAGE)

        # 4. Enhanced COPY INTO table with robust format detection
        copy_sql = f"""
        COPY INTO RAW.{table_name}
        FROM {STAGE}/{file_name}
        FILE_FORMAT=(
            TYPE=CSV
            SKIP_HEADER=1
            FIELD_OPTIONALLY_ENCLOSED_BY='"'
            EMPTY_FIELD_AS_NULL=TRUE
            ERROR_ON_COLUMN_COUNT_MISMATCH=FALSE
            REPLACE_INVALID_CHARACTERS=TRUE
        )
        ON_ERROR='CONTINUE';
        """
        print(f"Executing COPY command: {copy_sql}")
        copy_result = execute(copy_sql)
        print(f"COPY result: {copy_result}")

        # 5. Enhanced verification with detailed error checking
        verify_sql = f"SELECT COUNT(*) as row_count FROM RAW.{table_name}"
        count_result = execute(verify_sql)

        if count_result and len(count_result) > 0:
            actual_rows = count_result[0][0] if count_result[0] else 0
            print(f"Verification: {actual_rows} rows loaded into RAW.{table_name}")

            # If no rows loaded, check COPY history for detailed error info
            if actual_rows == 0:
                print("❌ No data loaded - checking COPY command history...")
                try:
                    history_sql = f"""
                    SELECT
                        FILE_NAME,
                        STATUS,
                        ERROR_COUNT,
                        ERROR_LIMIT,
                        ROWS_PARSED,
                        ROWS_LOADED,
                        ERROR_DETAILS
                    FROM TABLE(information_schema.copy_history(
                        table_name => 'RAW.{table_name}',
                        start_time => dateadd(minutes, -10, current_timestamp())
                    ))
                    ORDER BY LAST_LOAD_TIME DESC
                    LIMIT 1
                    """
                    history_result = execute(history_sql)
                    if history_result:
                        print(f"COPY History: {history_result}")
                        # Try alternative file format
                        print("Attempting with alternative CSV format...")
                        alt_sql = f"""
                        COPY INTO RAW.{table_name}
                        FROM {STAGE}/{file_name}
                        FILE_FORMAT=(
                            TYPE=CSV
                            SKIP_HEADER=1
                            FIELD_DELIMITER=','
                            RECORD_DELIMITER='\\n'
                            EMPTY_FIELD_AS_NULL=True
                            ERROR_ON_COLUMN_COUNT_MISMATCH=False
                        )
                        ON_ERROR='SKIP_FILE';
                        """
                        alt_result = execute(alt_sql)
                        print(f"Alternative COPY result: {alt_result}")

                        # Re-verify
                        recount_result = execute(verify_sql)
                        if recount_result:
                            actual_rows = (
                                recount_result[0][0] if recount_result[0] else 0
                            )
                            print(
                                f"After alternative format: {actual_rows} rows loaded"
                            )
                except Exception as history_err:
                    print(f"Could not check COPY history: {history_err}")
        else:
            actual_rows = 0
            print("❌ Could not verify row count")

        # 6. Insert audit record with actual row count
        if actual_rows > 0:
            insert_audit(file_name, f"RAW.{table_name}", actual_rows, "SUCCESS")
            success_msg = f"✅ Successfully loaded {actual_rows} rows into RAW.{table_name} (cleaned {len(unnamed_cols) + len(empty_cols)} problematic columns)"

            # Add agent insights if available
            if agent_analysis and agent_analysis.get("status") == "success":
                success_msg += f"\n\n🤖 Agent Insights:\n{agent_analysis.get('agent_analysis', '')}"

            return success_msg
        else:
            insert_audit(
                file_name,
                f"RAW.{table_name}",
                0,
                "FAILED",
                "No rows loaded - check file format or stage access",
            )
            return f"⚠️ Table RAW.{table_name} created but no data loaded. Check file format and stage permissions."

    except Exception as e:
        error_msg = str(e)
        print(f"Ingestion error: {error_msg}")
        insert_audit(file_name, f"RAW.{table_name}", 0, "FAILED", error_msg)
        return f"❌ Failed to load {file_name}: {error_msg}"
