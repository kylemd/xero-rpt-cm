"""
File Input Handler Module

Handles loading and sanitization of CSV and XLSX files for Chart of Accounts
and Trial Balance data, with intelligent detection of Xero trial balance format.
"""

import pandas as pd
import pathlib
import re
from typing import Tuple, Dict, Any, Optional


def load_chart_file(path: pathlib.Path) -> pd.DataFrame:
    """
    Load Chart of Accounts file (CSV or XLSX) and return as DataFrame.
    
    Args:
        path: Path to the chart file
        
    Returns:
        pandas DataFrame with chart data
        
    Raises:
        ValueError: If file format is not supported
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"Chart file not found: {path}")
    
    file_ext = path.suffix.lower()
    
    if file_ext == '.csv':
        return pd.read_csv(path, dtype={"*Code": "string"})
    elif file_ext == '.xlsx':
        return pd.read_excel(path, engine='openpyxl', dtype={"*Code": "string"})
    else:
        raise ValueError(f"Unsupported file format: {file_ext}. Only .csv and .xlsx are supported.")


def load_trial_balance_file(path: pathlib.Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load Trial Balance file (CSV or XLSX) with intelligent sanitization.
    
    Args:
        path: Path to the trial balance file
        
    Returns:
        Tuple of (DataFrame, metadata dict)
        
    Raises:
        ValueError: If file format is not supported
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"Trial balance file not found: {path}")
    
    file_ext = path.suffix.lower()
    
    if file_ext == '.csv':
        df = pd.read_csv(path)
        return df, {"format": "csv", "sanitized": False}
    elif file_ext == '.xlsx':
        df = pd.read_excel(path, engine='openpyxl', header=None)
        return sanitize_xlsx_trial_balance(df)
    else:
        raise ValueError(f"Unsupported file format: {file_ext}. Only .csv and .xlsx are supported.")


def sanitize_xlsx_trial_balance(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Intelligently detect and sanitize Xero trial balance XLSX format.
    Only sanitize if:
    - Cell A1 = "Trial Balance"
    - Cell A3 starts with "As at "
    
    Structure after sanitization:
    - Skip first 4 rows (title, blank, date header, blank)
    - Row 5 becomes column headers
    - Columns D and E (indices 3, 4) are Debit/Credit for the period at A3
    - Subsequent columns are in Dr/(Cr) format (negative = credit)
    
    Args:
        df: Raw DataFrame from XLSX file
        
    Returns:
        Tuple of (sanitized DataFrame, metadata dict)
    """
    # Check if this is a Xero trial balance format
    if (len(df) >= 4 and 
        str(df.iloc[0, 0]).strip() == "Trial Balance" and 
        str(df.iloc[2, 0]).strip().startswith("As at ")):
        
        period_date = str(df.iloc[2, 0]).strip().replace("As at ", "")
        company_name = str(df.iloc[1, 0]).strip() if len(df) > 1 and pd.notnull(df.iloc[1, 0]) else ""

        # Skip first 4 rows
        df = df.iloc[4:].reset_index(drop=True)

        # Promote first row to header
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

        # Parse amounts according to Xero format
        metadata = {"format": "xero_trial_balance", "period": period_date, "company_name": company_name, "sanitized": True}
        df = parse_trial_balance_amounts(df, metadata)

        return df, metadata
    
    # Non-Xero format: promote row 0 to headers so downstream code gets named columns
    df.columns = df.iloc[0]
    df = df.iloc[1:].reset_index(drop=True)
    return df, {"format": "unknown", "sanitized": False}


def parse_trial_balance_amounts(df: pd.DataFrame, metadata: Dict[str, Any]) -> pd.DataFrame:
    """
    Parse amounts accounting for different column formats:
    - Columns D & E (positions 3, 4): Debit and Credit as separate columns
    - Subsequent year columns: Dr/(Cr) format where negative = credit
    
    Args:
        df: DataFrame with raw amount columns
        metadata: Metadata about the file format
        
    Returns:
        DataFrame with parsed amounts
    """
    parsed_df = df.copy()
    
    # Identify debit/credit columns and year columns
    debit_col = df.columns[3] if len(df.columns) > 3 else None
    credit_col = df.columns[4] if len(df.columns) > 4 else None
    year_cols = [col for col in df.columns[5:] if is_year_column(col)]
    
    # For D & E: Parse as separate debit/credit
    if debit_col and credit_col:
        parsed_df['Debit - Year to date'] = df[debit_col].apply(parse_amount)
        parsed_df['Credit - Year to date'] = df[credit_col].apply(parse_amount)
    
    # For year columns: Parse Dr/(Cr) format
    for col in year_cols:
        parsed_df[col] = df[col].apply(parse_dr_cr_amount)
    
    return parsed_df


def parse_amount(value_str: Any) -> float:
    """
    Parse amount string handling currency formatting (commas, parentheses for negatives).
    
    Args:
        value_str: String or numeric value to parse
        
    Returns:
        Parsed float value
    """
    if pd.isna(value_str):
        return 0.0
    
    s = str(value_str).strip().replace(',', '')
    
    # Handle parentheses for negative values
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_dr_cr_amount(value: Any) -> float:
    """
    Parse Dr/(Cr) format: positive = debit, (parentheses) = credit (negative)
    
    Args:
        value: String or numeric value to parse
        
    Returns:
        Parsed float value (positive for debit, negative for credit)
    """
    if pd.isna(value):
        return 0.0
    
    s = str(value).strip().replace(',', '')
    
    # Handle parentheses for credit (negative) values
    if s.startswith('(') and s.endswith(')'):
        return -float(s[1:-1])
    
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def is_year_column(column_name: str) -> bool:
    """
    Check if a column name represents a year/period column.
    
    Args:
        column_name: Name of the column to check
        
    Returns:
        True if the column appears to be a year/period column
    """
    if not isinstance(column_name, str):
        return False
    
    # Common date patterns
    date_patterns = [
        r'\d{1,2}\s+\w+\s+\d{4}',  # "30 June 2024"
        r'\w+\s+\d{4}',            # "June 2024"
        r'\d{4}-\d{2}-\d{2}',      # "2024-06-30"
        r'\d{4}/\d{2}/\d{2}',      # "2024/06/30"
    ]
    
    for pattern in date_patterns:
        if re.search(pattern, column_name, re.IGNORECASE):
            return True
    
    return False


def detect_period_columns(df: pd.DataFrame) -> list:
    """
    Identify date-based columns in the DataFrame.
    
    Args:
        df: DataFrame to analyze
        
    Returns:
        List of column names that appear to be period columns
    """
    period_cols = []
    
    for col in df.columns:
        if is_year_column(col):
            period_cols.append(col)
    
    return period_cols


def get_account_code_column(df: pd.DataFrame) -> Optional[str]:
    """
    Detect the account code column from common column names.
    
    Args:
        df: DataFrame to analyze
        
    Returns:
        Name of the account code column, or None if not found
    """
    possible_names = ['AccountCode', 'Account Code', 'Code', '*Code']
    
    for name in possible_names:
        if name in df.columns:
            return name
    
    return None


def get_closing_balance_column(df: pd.DataFrame) -> Optional[str]:
    """
    Detect the closing balance column from common column names.
    
    Args:
        df: DataFrame to analyze
        
    Returns:
        Name of the closing balance column, or None if not found
    """
    possible_names = ['ClosingBalance', 'Closing Balance', '30 June 2024']
    
    for name in possible_names:
        if name in df.columns:
            return name
    
    # Look for most recent year column
    period_cols = detect_period_columns(df)
    if period_cols:
        # Sort by year and return the most recent
        sorted_cols = sorted(period_cols, reverse=True)
        return sorted_cols[0]
    
    return None
