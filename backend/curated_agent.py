from snowflake_utils import execute, query_df, cleanup_connection_pool
from audit import insert_audit
import pandas as pd
import pandas  # Also import as 'pandas' for snowflake connector compatibility
from datetime import datetime
import json
from functools import lru_cache
import numpy as np
from langchain_utils import get_curation_agent


def normalize_column_names(df):
    """
    Normalize column names by replacing spaces, hyphens, and special characters with underscores.
    This ensures column names are database-friendly and SQL-compliant.

    Args:
        df: DataFrame with potentially problematic column names

    Returns:
        DataFrame with normalized column names and column mapping
    """
    import re

    # Create a mapping of old names to new names
    column_mapping = {}

    for col in df.columns:
        # Start with the original column name
        normalized_col = str(col)

        # Replace spaces and hyphens with underscores
        normalized_col = normalized_col.replace(" ", "_").replace("-", "_")

        # Handle parentheses - replace with underscores or remove them
        # Example: RETAIL_PRICE_(USD) -> RETAIL_PRICE_USD
        normalized_col = normalized_col.replace("(", "_").replace(")", "_")

        # Handle other common special characters
        # Handle other common special characters
        normalized_col = normalized_col.replace("{", "_").replace("}", "_")
        normalized_col = normalized_col.replace("[", "_").replace("]", "_")
        normalized_col = normalized_col.replace(",", "_")
        normalized_col = normalized_col.replace(".", "_")
        normalized_col = normalized_col.replace(":", "_")
        normalized_col = normalized_col.replace(";", "_")
        normalized_col = normalized_col.replace("/", "_")
        normalized_col = normalized_col.replace("\\", "_")
        normalized_col = normalized_col.replace("|", "_")
        normalized_col = normalized_col.replace("&", "_AND_")
        normalized_col = normalized_col.replace("%", "_PCT_")
        normalized_col = normalized_col.replace("#", "_NUM_")
        normalized_col = normalized_col.replace("@", "_AT_")
        normalized_col = normalized_col.replace("*", "_")
        normalized_col = normalized_col.replace("+", "_PLUS_")
        normalized_col = normalized_col.replace("=", "_EQ_")
        normalized_col = normalized_col.replace("?", "_")
        normalized_col = normalized_col.replace("<", "_LT_")
        normalized_col = normalized_col.replace(">", "_GT_")
        normalized_col = normalized_col.replace('"', "_")
        normalized_col = normalized_col.replace("'", "_")
        normalized_col = normalized_col.replace("!", "_")
        normalized_col = normalized_col.replace("^", "_")
        normalized_col = normalized_col.replace("~", "_")
        normalized_col = normalized_col.replace("$", "_USD")

        # Remove any duplicate underscores
        while "__" in normalized_col:
            normalized_col = normalized_col.replace("__", "_")

        # Remove leading/trailing underscores
        normalized_col = normalized_col.strip("_")

        # Convert to uppercase for consistency
        normalized_col = normalized_col.upper()

        # Ensure column name starts with a letter or underscore (SQL requirement)
        if (
            not normalized_col
            or not normalized_col[0].isalpha()
            and normalized_col[0] != "_"
        ):
            normalized_col = "COL_" + normalized_col

        # Handle empty column names
        if not normalized_col:
            normalized_col = f"UNNAMED_COL_{df.columns.get_loc(col) + 1}"

        # Handle potential duplicates by adding suffix if needed
        original_normalized = normalized_col
        counter = 1
        while normalized_col in column_mapping.values():
            normalized_col = f"{original_normalized}_{counter}"
            counter += 1

        column_mapping[col] = normalized_col

    # Rename columns and return the DataFrame
    df_normalized = df.rename(columns=column_mapping)

    # Print the column mapping for user visibility
    if any(old != new for old, new in column_mapping.items()):
        print("Column name normalization applied:")
        for old, new in column_mapping.items():
            if old != new:
                print(f"  '{old}' -> '{new}'")

    return df_normalized, column_mapping


@lru_cache(maxsize=128)
def _get_cached_patterns():
    """Get compiled regex patterns for date detection (cached)."""
    import re

    return [
        re.compile(r"^\d{4}-\d{2}-\d{2}$"),  # YYYY-MM-DD
        re.compile(r"^\d{2}/\d{2}/\d{4}$"),  # MM/DD/YYYY or DD/MM/YYYY
        re.compile(r"^\d{2}/\d{2}/\d{2}$"),  # MM/DD-YY or DD/MM-YY (2-digit year)
        re.compile(r"^\d{2}-\d{2}/\d{4}$"),  # MM-DD-YYYY or DD-MM-YYYY
        re.compile(r"^\d{2}/\d{2}-\d{2}$"),  # MM-DD-YY or DD-MM-YY (2-digit year)
        re.compile(r"^\d{4}/\d{2}/\d{2}$"),  # YYYY/MM/DD
        re.compile(
            r"^\d{1,2}\s+\w+\s+\d{4}$"
        ),  # DD Month YYYY (e.g., "25 December 2024")
        re.compile(r"^\d{4}\d{2}\d{2}$"),  # YYYYMMDD
    ]


def detect_column_type(df, col):
    """
    Detect column type by analyzing distribution of values.
    Returns the dominant type based on percentage thresholds.
    Also detects if numbers are floats (decimals) vs integers.
    Supports multiple date formats: YYYY-MM-DD, MM/DD/YYYY, MM/DD/YY, DD-MM-YYYY, etc.
    Supports formatted numbers with commas, currency symbols, and other formatting.
    Optimized with caching and vectorized operations.
    """
    series = df[col].dropna().astype(str)

    if series.empty:
        return "VARCHAR"

    total_non_null = len(series)

    # Use cached compiled patterns for better performance
    date_patterns = _get_cached_patterns()

    # Vectorized pattern matching for better performance
    date_count = 0
    for pattern in date_patterns:
        date_count += series.str.match(pattern, na=False).sum()

    # Enhanced numeric detection: supports formatted numbers with commas, currency symbols, etc.
    # Examples: "1234", "1,234.56", "$1,234.56", "₹2,42,492.99", "-1,234.56", "%$"
    import re

    def is_numeric_formatted(val):
        """Check if value can be parsed as number after removing formatting."""
        # Remove currency symbols, commas, spaces, and other formatting chars
        cleaned = re.sub(r"[\$€£¥s,@%&()\[\]\{\}\|\/~!?]", "", str(val))
        # Check if remaining is a valid number (must have at least one digit)
        if not cleaned or cleaned == "-" or cleaned == ".":
            return False
        try:
            float(cleaned)
            return True
        except (ValueError, TypeError):
            return False

    # Apply numeric check with formatting support
    numeric_mask = series.apply(is_numeric_formatted)
    numeric_count = numeric_mask.sum()

    if numeric_count > 0:
        # Check for decimal points in the cleaned values
        def has_decimal(val):
            cleaned = re.sub(r"[\$€£¥s,@%&()\[\]\{\}\|\/~!?]", "", str(val))
            return "." in cleaned

        float_mask = series[numeric_mask].apply(has_decimal)
        float_count = float_mask.sum()
    else:
        float_count = 0

    date_ratio = date_count / total_non_null if total_non_null > 0 else 0
    numeric_ratio = numeric_count / total_non_null if total_non_null > 0 else 0
    float_ratio = float_count / numeric_count if numeric_count > 0 else 0

    # Decision logic: 70% threshold for pure types, otherwise VARCHAR
    if numeric_ratio > 0.7:
        # Check if mostly floats to use DECIMAL instead of NUMBER
        if float_ratio > 0.3:
            return "DECIMAL"
        return "NUMBER"
    elif date_ratio > 0.7:
        return "DATE"
    else:
        return "VARCHAR"


def validate_numeric(value):
    """
    Validate numeric values.
    Rule: If numeric column has special chars, convert to 0. NULL values convert to 0 as well.
    Supports formatted numbers with commas, currency symbols, and other formatting.
    """
    if pd.isna(value) or value == "":
        return 0, "NULL_CONVERTED_TO_ZERO"

    value_str = str(value).strip()

    # Remove currency symbols, commas, spaces, and other formatting characters
    import re

    # Remove common currency symbols: $, ₹, €, £, ¥
    # Remove commas (thousand separators)
    # Remove spaces
    # Keep minus sign, decimal point, and digits
    cleaned = re.sub(r"[\$€£¥s,@%&()\[\]\{\}\|\/~!?]", "", value_str)

    # If after cleaning we have nothing valid, convert to 0
    if not cleaned or cleaned == "-" or cleaned == ".":
        return 0, "INVALID_FORMAT_CONVERTED_TO_ZERO"

    try:
        num = float(cleaned)
        # Check for reasonable ranges (customize based on domain)
        if num < -1e10 or num > 1e10:
            return 0, "OUT_OF_RANGE_CONVERTED_TO_ZERO"
        return num, "VALID"
    except (ValueError, TypeError):
        # Special characters or invalid format in numeric column -> convert to 0
        return 0, "INVALID_FORMAT_CONVERTED_TO_ZERO"


def validate_date(value):
    """
    Validate and convert date values to proper datetime.
    Rule: Parse dates into datetime objects for Snowflake DATE type.
    Handles multiple date formats including 2-digit years (YY) and numeric timestamps.
    Only NULL values stay NULL; invalid dates are rejected.
    """
    if pd.isna(value) or value == "":
        return None, "NULL_VALUE"

    value_str = str(value).strip()

    if value_str == "":
        return None, "NULL_VALUE"

    try:
        # First check if it's a numeric timestamp (from Snowflake DATE type returning as number)
        # Snowflake might return dates as nanosecond timestamps
        if isinstance(value, (int, float)) or (
            isinstance(value, str) and value.isdigit()
        ):
            numeric_val = float(value)

            # Detect timestamp scale and convert to seconds
            if numeric_val > 1e18:  # Nanoseconds (19+ digits)
                seconds = numeric_val / 1e9
            elif numeric_val > 1e15:  # Microseconds (16+ digits)
                seconds = numeric_val / 1e6
            elif numeric_val > 1e12:  # Milliseconds (13+ digits)
                seconds = numeric_val / 1e3
            else:  # Assume seconds (10 digits for dates around 2001-2286)
                seconds = numeric_val

            # Convert Unix timestamp to datetime
            parsed = pd.Timestamp.fromtimestamp(seconds, tz="UTC").tz_localize(None)
        else:
            # Try parsing string with different formats
            parsed = pd.to_datetime(value_str, format=None, infer_datetime_format=True)

        # Check for reasonable date range (1900 - today)
        if parsed.year < 1900 or parsed > pd.Timestamp.now():
            return None, "INVALID_DATE_RANGE"

        return parsed, "VALID"
    except (ValueError, TypeError, OSError):
        return None, "INVALID_FORMAT"


def validate_string(value):
    """
    Validate and sanitize string values.
    Rule: Handle missing/null values, remove/replace problematic control characters while preserving text.
    """
    if pd.isna(value) or value == "":
        return None, "NULL_VALUE"

    value_str = str(value).strip()

    if value_str == "":
        return None, "EMPTY_AFTER_TRIM"

    # Remove special characters but preserve spaces and common punctuation
    sanitized = value_str.replace("\n", " ").replace("\r", " ")

    return sanitized, "VALID"


def generate_create_table_ddl(
    table_name, schema, col_types, tracking_cols=True, is_rejected_table=False
):
    """
    Generate CREATE TABLE DDL based on detected column types.

    Args:
        table_name: Name of the table to create
        schema: Schema name (e.g., 'CURATED')
        col_types: Dictionary of column names and their detected types
        tracking_cols: Whether to include tracking columns
        is_rejected_table: Whether this is a rejected table (adds rejection columns)

    Returns:
        SQL CREATE TABLE statement
    """
    columns = []

    # Tracking columns
    if tracking_cols:
        columns.append("_ROW_ID NUMBER")
        columns.append("_SOURCE_TABLE VARCHAR(255)")
        columns.append("_LOAD_TIMESTAMP VARCHAR(50)")

    # Data columns based on detected types
    for col_name, col_type in col_types.items():
        col_name_upper = col_name.upper()
        if col_type == "DECIMAL":
            columns.append(f"{col_name_upper} DECIMAL(38, 2)")
        elif col_type == "NUMBER":
            columns.append(f"{col_name_upper} NUMBER(38, 2)")
        elif col_type == "DATE":
            columns.append(f"{col_name_upper} DATE")
        else:
            columns.append(f"{col_name_upper} VARCHAR(255)")

    # Add rejection columns for rejected tables
    if is_rejected_table:
        columns.append("_REJECTION_REASON VARCHAR(500)")
        columns.append("_REJECTED_AT VARCHAR(50)")

    columns_sql = ",\n    ".join(columns)
    ddl = f"""
    CREATE OR REPLACE TABLE {schema}.{table_name} (
        {columns_sql}
    )
    """
    return ddl


def load_raw_to_curated(raw_table, use_agent=True):
    """
    Transform raw data to curated layer with comprehensive validation.
    Creates CURATED table and REJECTED table for failed records.
    Applies cleansing rules:
    - Convert floats to DECIMAL(38, 2)
    - Replace NULLs in numeric fields with 0
    - Fix varchar columns with proper type detection
    Optimized for performance with batch processing and memory management.

    Args:
        raw_table: Name of the raw table to transform
        use_agent: Whether to use LangChain agent for analysis (default: True)

    Returns:
        Tuple of (curated_table, rejected_table, summary_df, summary_stats)
    """

    curated_table = f"{raw_table}_CURATED"
    rejected_table = f"{raw_table}_REJECTED"

    # Optional: Get agentic recommendations before processing
    agent_recommendations = None
    if use_agent:
        try:
            print("Running agentic data curation analysis...")
            curation_agent = get_curation_agent()
            # Get a data sample for agent analysis
            sample_df = query_df(f"SELECT * FROM RAW.{raw_table} LIMIT 10")
            sample_dict = sample_df.to_dict("records") if not sample_df.empty else []

            agent_recommendations = curation_agent.analyze_and_curate(
                raw_table, sample_dict
            )
            if agent_recommendations.get("status") == "success":
                print(
                    f"✅ Agent Analysis Complete:\n{agent_recommendations.get('agent_recommendations', '')}"
                )
        except Exception as e:
            print(f"⚠️ Agent analysis skipped: {e}")
            # Continue with normal flow - agent analysis is optional

    # Load raw data with memory optimization
    print(f"Loading raw data from RAW.{raw_table}...")
    raw_df = query_df(f"SELECT * FROM RAW.{raw_table}")

    # Store original CSV structure info
    csv_shape = raw_df.shape
    csv_columns = raw_df.columns.tolist()
    csv_dtypes = {col: str(dtype) for col, dtype in raw_df.dtypes.items()}

    # Optimize memory usage for large datasets
    if len(raw_df) > 5000:
        print(
            f"Large dataset detected ({len(raw_df)} rows), optimizing memory usage..."
        )
    # Convert object columns to category where beneficial
    for col in raw_df.select_dtypes(include=["object"]).columns:
        if raw_df[col].nunique() < len(raw_df) * 0.1:  # Less than 10% unique values
            raw_df[col] = raw_df[col].astype("category")

    # Normalize column names (replace spaces and hyphens with underscores)
    raw_df, column_mapping = normalize_column_names(raw_df)
    print(f"Raw data loaded with {len(raw_df)} rows and {len(raw_df.columns)} columns")

    # Add tracking columns
    raw_df["_ROW_ID"] = range(1, len(raw_df) + 1)
    raw_df["_SOURCE_TABLE"] = raw_table
    raw_df["_LOAD_TIMESTAMP"] = datetime.now().isoformat()

    # Batch column type detection for performance
    print("Analyzing column types...")
    data_columns = [
        col
        for col in raw_df.columns
        if col not in ["_ROW_ID", "_SOURCE_TABLE", "_LOAD_TIMESTAMP"]
    ]
    col_types = {}

    for i, col in enumerate(data_columns):
        if i % 10 == 0 and i > 0:
            print(f"Analyzed {i}/{len(data_columns)} columns...")
        col_types[col] = detect_column_type(raw_df, col)

    print(f"Column type analysis complete. Found {len(col_types)} data columns.")

    # Pre-allocate lists with estimated sizes for better performance
    estimated_accepted = int(len(raw_df) * 0.95)  # Assume 95% acceptance rate
    estimated_rejected = len(raw_df) - estimated_accepted

    curated_data = []
    rejected_data = []
    summary_rows = []
    duplicate_check = set()

    # Track column-level statistics for summary
    column_stats = {
        col: {"raw_nulls": 0, "curated_nulls": 0, "conversions": 0}
        for col in col_types.keys()
    }

    # Process data in batches for memory efficiency
    batch_size = min(1000, len(raw_df))  # Process in chunks of 1000 or less
    total_batches = (len(raw_df) + batch_size - 1) // batch_size

    print(f"Processing data in {total_batches} batches of {batch_size} rows each...")

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(raw_df))
        batch_df = raw_df.iloc[start_idx:end_idx]

        if batch_idx % 10 == 0:
            print(f"Processing batch {batch_idx + 1}/{total_batches}...")

        for idx, row in batch_df.iterrows():
            curated_row = {
                "_ROW_ID": row["_ROW_ID"],
                "_SOURCE_TABLE": raw_table,
                "_LOAD_TIMESTAMP": row["_LOAD_TIMESTAMP"],
            }
            rejected_row = {
                "_ROW_ID": row["_ROW_ID"],
                "_SOURCE_TABLE": raw_table,
                "_LOAD_TIMESTAMP": row["_LOAD_TIMESTAMP"],
            }
            row_rejected = False
            rejection_reasons = []

            for col, dtype in col_types.items():
                raw_val = row[col]
                curated_val = None
                validation_status = "VALID"

                if dtype == "NUMBER" or dtype == "DECIMAL":
                    curated_val, validation_status = validate_numeric(raw_val)
                elif dtype == "DATE":
                    curated_val, validation_status = validate_date(raw_val)
                else:  # STRING
                    curated_val, validation_status = validate_string(raw_val)

                # Track column statistics
                if pd.isna(raw_val) or raw_val == "":
                    column_stats[col]["raw_nulls"] += 1
                if curated_val is None or curated_val == "":
                    column_stats[col]["curated_nulls"] += 1

                # Track transformations (only non-valid transformations)
                if validation_status != "VALID":
                    column_stats[col]["conversions"] += 1
                    summary_rows.append(
                        {
                            "ROW_NUMBER": idx + 1,
                            "COLUMN_NAME": col.upper(),
                            "RAW_VALUE": raw_val,
                            "CURATED_VALUE": curated_val,
                            "VALIDATION_STATUS": validation_status,
                        }
                    )

                # Mark row as rejected only for DATE validation failures (not numeric)
                # Numeric columns with special chars are converted to 0 (not rejected)
                if dtype == "DATE" and validation_status not in [
                    "VALID",
                    "NULL_VALUE",
                    "NULL_CONVERTED_TO_ZERO",
                ]:
                    row_rejected = True
                    rejection_reasons.append(f"{col}: {validation_status}")

                curated_row[col] = curated_val
                rejected_row[col] = raw_val

            if row_rejected:
                rejected_row["_REJECTION_REASON"] = " | ".join(rejection_reasons)
                rejected_row["_REJECTED_AT"] = datetime.now().isoformat()
                rejected_data.append(rejected_row)

            else:
                # Check for duplicates (on non-null values) - optimized
                dup_key = tuple(
                    str(curated_row.get(col, ""))
                    for col in col_types.keys()
                    if col not in ["_ROW_ID"]
                )
                if dup_key in duplicate_check and dup_key[0] != "":
                    rejected_row["_REJECTION_REASON"] = "DUPLICATE_RECORD"
                    rejected_row["_REJECTED_AT"] = datetime.now().isoformat()
                    rejected_data.append(rejected_row)
                else:
                    duplicate_check.add(dup_key)
                    curated_data.append(curated_row)

    print(
        f"Data processing complete. Accepted: {len(curated_data)}, Rejected: {len(rejected_data)}"
    )

    # Create curated table with proper schema
    if curated_data:
        # Generate and execute CREATE TABLE DDL
        create_dll = generate_create_table_ddl(
            curated_table.upper(), "CURATED", col_types
        )
        print("Creating CURATED table with DDL:")
        print(create_dll)
        execute(create_dll)

        # Now insert the data
        curated_df = pd.DataFrame(curated_data)

        # Ensure proper data types for Snowflake insertion
        for col, dtype in col_types.items():
            if dtype == "DATE":
                # Convert to datetime first, then to string in YYYY-MM-DD format
                # This prevents write_pandas from converting to numeric timestamps
                curated_df[col] = pd.to_datetime(curated_df[col], errors="coerce")
                curated_df[col] = curated_df[col].dt.strftime("%Y-%m-%d")
                # Set NULL values back to None for proper NULL handling in Snowflake
                curated_df[col] = curated_df[col].replace("NaT", None)
            elif dtype == "DECIMAL" or dtype == "NUMBER":
                curated_df[col] = pd.to_numeric(curated_df[col], errors="coerce")
            # VARCHAR columns are already strings

        from snowflake.connector.pandas_tools import write_pandas
        from snowflake_utils import get_conn

        conn = get_conn()
        write_pandas(
            conn,
            curated_df,
            curated_table.upper(),
            schema="CURATED",
            auto_create_table=False,
            overwrite=False,
        )
        print(f"✅ Data inserted into CURATED.{curated_table.upper()}")
    else:
        # Create empty curated table
        create_ddl = generate_create_table_ddl(
            curated_table.upper(), "CURATED", col_types
        )
        execute(create_ddl)
        print(f"✅ Empty CURATED table created: CURATED.{curated_table.upper()}")

    # Create rejected table (if any rejections)
    if rejected_data:
        # Create rejected table with same schema + rejection columns
        rejected_ddl = generate_create_table_ddl(
            rejected_table.upper(),
            "CURATED",
            col_types,
            tracking_cols=True,
            is_rejected_table=True,
        )

        print("Creating REJECTED table with DDL:")
        print(rejected_ddl)
        execute(rejected_ddl)

        # Insert rejected data
        rejected_df = pd.DataFrame(rejected_data)
        from snowflake.connector.pandas_tools import write_pandas
        from snowflake_utils import get_conn

        conn = get_conn()
        write_pandas(
            conn,
            rejected_df,
            rejected_table.upper(),
            schema="CURATED",
            auto_create_table=False,
            overwrite=False,
        )
        print(f"✅ Rejected records inserted into CURATED.{rejected_table.upper()}")

    # Insert audit record
    total_rows = len(raw_df)
    accepted_rows = len(curated_data)
    rejected_rows = len(rejected_data)
    quality_score = (accepted_rows / total_rows * 100) if total_rows > 0 else 0

    audit_metadata = {
        "accepted_rows": accepted_rows,
        "rejected_rows": rejected_rows,
        "quality_score": quality_score,
        "rejected_table": rejected_table,
    }

    insert_audit(
        raw_table,
        f"CURATED.{curated_table}",
        total_rows,
        "SUCCESS",
        json.dumps(audit_metadata),
    )

    summary_df = pd.DataFrame(summary_rows) if summary_rows else pd.DataFrame()

    # Create comprehensive summary with stats
    summary_stats = {
        "csv_shape": csv_shape,
        "raw_shape": (len(raw_df), len(col_types)),
        "curated_shape": (len(curated_data), len(col_types)),
        "rejected_count": len(rejected_data),
        "column_stats": column_stats,
        "csv_columns": csv_columns,
        "csv_dtypes": csv_dtypes,
        "curated_col_types": col_types,
        "column_mapping": column_mapping,
        "agent_recommendations": agent_recommendations.get("agent_recommendations", "")
        if agent_recommendations
        else None,
    }

    # Clean up memory for large datasets
    if len(raw_df) > 5000:
        del raw_df  # Free up memory
        import gc

        gc.collect()
        print("Memory cleanup completed for large dataset")

    return curated_table, rejected_table, summary_df, summary_stats
