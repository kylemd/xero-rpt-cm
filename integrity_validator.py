"""
Integrity Validation Module

Validates Chart of Accounts data against integrity rules defined in
Account_Types_Head.csv and Account_Types_per_Financial-Reports.json.
"""

import pandas as pd
import json
import pathlib
from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict


class IntegrityValidator:
    """Validates account type and reporting code combinations against integrity rules."""
    
    def __init__(self, project_root: pathlib.Path):
        """
        Initialize the validator with integrity rules.
        
        Args:
            project_root: Path to the project root directory
        """
        self.project_root = project_root
        self.type_head_mapping = {}
        self.type_allowed_codes = {}
        self.report_appearances = {}
        self._load_integrity_rules()
    
    def _load_integrity_rules(self):
        """Load integrity rules from configuration files."""
        # Load Account_Types_Head.csv
        head_file = self.project_root / 'SystemFiles' / 'Account_Types_Head.csv'
        if head_file.exists():
            head_df = pd.read_csv(head_file)
            for _, row in head_df.iterrows():
                account_type = row['Account Type'].strip()
                expected_head = row['Expected Head Reporting Code'].strip()
                self.type_head_mapping[account_type.lower()] = expected_head
        
        # Load Account_Types_per_Financial-Reports.json
        reports_file = self.project_root / 'SystemFiles' / 'Account_Types_per_Financial-Reports.json'
        if reports_file.exists():
            with open(reports_file, 'r', encoding='utf-8') as f:
                reports_data = json.load(f)
            
            for account_type, rules in reports_data.items():
                self.type_allowed_codes[account_type.lower()] = {
                    'allowed_codes': set(rules.get('allowed_codes', [])),
                    'allowed_prefixes': set(rules.get('allowed_prefixes', []))
                }
        
        # Load report appearances from financial report JSON files
        self._load_report_appearances()
    
    def _load_report_appearances(self):
        """Load which reporting codes appear in which financial reports."""
        financial_reports_dir = self.project_root / 'financial-reports'
        
        for report_file in financial_reports_dir.glob('*.json'):
            report_name = report_file.name
            with open(report_file, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            
            # Extract all ReportCode:: values from the report
            codes = self._extract_report_codes(report_data)
            for code in codes:
                if code not in self.report_appearances:
                    self.report_appearances[code] = []
                self.report_appearances[code].append(report_name)
    
    def _extract_report_codes(self, data: Any) -> Set[str]:
        """Recursively extract ReportCode:: values from nested JSON structure."""
        codes = set()
        
        if isinstance(data, dict):
            for key, value in data.items():
                if key == 'Value' and isinstance(value, str) and value.startswith('ReportCode::'):
                    code = value.replace('ReportCode::', '')
                    codes.add(code)
                else:
                    codes.update(self._extract_report_codes(value))
        elif isinstance(data, list):
            for item in data:
                codes.update(self._extract_report_codes(item))
        
        return codes
    
    def validate_account_entry(self, account_type: str, reporting_code: str, 
                             account_name: str = "") -> Dict[str, Any]:
        """
        Check if an account's Type and Reporting Code combination is valid.
        
        Args:
            account_type: The account type (e.g., "Revenue", "Expense")
            reporting_code: The reporting code (e.g., "REV.TRA.SER")
            account_name: The account name (for context in error messages)
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        if not account_type or not reporting_code:
            result['valid'] = False
            result['errors'].append("Account type and reporting code are required")
            return result
        
        account_type_lower = account_type.strip().lower()
        reporting_code = reporting_code.strip()
        
        # Check if account type is known
        if account_type_lower not in self.type_head_mapping:
            result['warnings'].append(f"Unknown account type: {account_type}")
        
        # Check expected head mapping
        if account_type_lower in self.type_head_mapping:
            expected_head = self.type_head_mapping[account_type_lower]
            actual_head = reporting_code.split('.')[0] if '.' in reporting_code else reporting_code
            
            if actual_head != expected_head:
                result['valid'] = False
                result['errors'].append(
                    f"Type '{account_type}' expects reporting head '{expected_head}', "
                    f"found '{actual_head}'"
                )
        
        # Check allowed codes for this type
        if account_type_lower in self.type_allowed_codes:
            allowed_info = self.type_allowed_codes[account_type_lower]
            
            # Check exact code match
            if reporting_code not in allowed_info['allowed_codes']:
                # Check prefix match
                code_prefix = reporting_code.split('.')[0] if '.' in reporting_code else reporting_code
                if code_prefix not in allowed_info['allowed_prefixes']:
                    result['valid'] = False
                    result['errors'].append(
                        f"Reporting code '{reporting_code}' not allowed for type '{account_type}'. "
                        f"Allowed codes: {sorted(allowed_info['allowed_codes'])}"
                    )
        
        # Check for multi-report appearances
        if reporting_code in self.report_appearances:
            appearances = self.report_appearances[reporting_code]
            if len(appearances) > 1:
                result['valid'] = False
                result['errors'].append(
                    f"Reporting code '{reporting_code}' appears in multiple reports: {appearances}"
                )
        
        return result
    
    def validate_chart_dataframe(self, df: pd.DataFrame, source_name: str) -> List[Dict[str, Any]]:
        """
        Validate entire chart DataFrame and return structured findings.
        
        Args:
            df: DataFrame with chart data
            source_name: Name of the source file for error reporting
            
        Returns:
            List of validation findings
        """
        findings = []
        
        # Determine column names
        type_col = None
        code_col = None
        name_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if 'type' in col_lower and '*' not in col_lower:
                type_col = col
            elif 'report' in col_lower and 'code' in col_lower:
                code_col = col
            elif 'name' in col_lower and '*' not in col_lower:
                name_col = col
        
        if not type_col or not code_col:
            findings.append({
                'source_file': source_name,
                'line_number': 0,
                'account_code': 'N/A',
                'type': 'N/A',
                'reporting_code': 'N/A',
                'reason': f"Missing required columns. Found: {list(df.columns)}"
            })
            return findings
        
        # Validate each row
        for idx, row in df.iterrows():
            account_type = str(row.get(type_col, '')).strip()
            reporting_code = str(row.get(code_col, '')).strip()
            account_name = str(row.get(name_col, '')).strip() if name_col else ""
            account_code = str(row.get('*Code', '')).strip() if '*Code' in df.columns else str(idx + 1)
            
            if not account_type or not reporting_code or account_type == 'nan' or reporting_code == 'nan':
                continue
            
            validation = self.validate_account_entry(account_type, reporting_code, account_name)
            
            if not validation['valid']:
                for error in validation['errors']:
                    findings.append({
                        'source_file': source_name,
                        'line_number': idx + 1,
                        'account_code': account_code,
                        'type': account_type,
                        'reporting_code': reporting_code,
                        'reason': error
                    })
        
        return findings
    
    def get_allowed_codes_for_type(self, account_type: str) -> Set[str]:
        """
        Return valid reporting codes for a given account type.
        
        Args:
            account_type: The account type to query
            
        Returns:
            Set of allowed reporting codes
        """
        account_type_lower = account_type.strip().lower()
        if account_type_lower in self.type_allowed_codes:
            return self.type_allowed_codes[account_type_lower]['allowed_codes']
        return set()
    
    def get_report_appearances(self, reporting_code: str) -> List[str]:
        """
        Return all reports where a reporting code appears.
        
        Args:
            reporting_code: The reporting code to query
            
        Returns:
            List of report filenames where the code appears
        """
        return self.report_appearances.get(reporting_code, [])
    
    def detect_balance_anomalies(self, account_code: str, account_type: str, 
                               period_balances: Dict[str, float]) -> Dict[str, Any]:
        """
        Flag accounts with persistent contrary balances.
        
        Args:
            account_code: The account code
            account_type: The account type
            period_balances: Dictionary of period -> balance values
            
        Returns:
            Dictionary with anomaly analysis
        """
        result = {
            'is_anomaly': False,
            'expected_sign': None,
            'actual_pattern': None,
            'periods_checked': 0,
            'recommendation': None,
            'severity': None
        }
        
        if len(period_balances) < 2:
            return result
        
        # Define expected balance signs
        expected_debit_types = {
            'asset', 'current asset', 'fixed asset', 'non-current asset', 
            'expense', 'direct costs', 'depreciation', 'bank'
        }
        expected_credit_types = {
            'liability', 'current liability', 'non-current liability',
            'revenue', 'other income', 'equity', 'retained earnings'
        }
        
        account_type_lower = account_type.strip().lower()
        
        if account_type_lower in expected_debit_types:
            result['expected_sign'] = 'debit'
        elif account_type_lower in expected_credit_types:
            result['expected_sign'] = 'credit'
        else:
            return result  # Unknown type, can't determine anomaly
        
        # Analyze balance signs across periods
        non_zero_balances = {period: balance for period, balance in period_balances.items() 
                           if abs(balance) > 1e-9}
        
        if len(non_zero_balances) < 2:
            return result
        
        result['periods_checked'] = len(non_zero_balances)
        
        # Count periods with contrary balance
        contrary_count = 0
        for balance in non_zero_balances.values():
            if result['expected_sign'] == 'debit' and balance < 0:
                contrary_count += 1
            elif result['expected_sign'] == 'credit' and balance > 0:
                contrary_count += 1
        
        contrary_percentage = contrary_count / len(non_zero_balances)
        
        # Determine if anomaly exists (≥75% threshold)
        if contrary_percentage >= 0.75:
            result['is_anomaly'] = True
            
            if contrary_percentage == 1.0:
                result['severity'] = 'Critical'
                result['actual_pattern'] = f"consistently_{'credit' if result['expected_sign'] == 'debit' else 'debit'}"
            elif contrary_percentage >= 0.75:
                result['severity'] = 'High'
                result['actual_pattern'] = f"mostly_{'credit' if result['expected_sign'] == 'debit' else 'debit'}"
            
            # Generate recommendation
            opposite_type = 'Liability' if result['expected_sign'] == 'debit' else 'Asset'
            result['recommendation'] = (
                f"Account has {result['actual_pattern']} balance across {result['periods_checked']} periods. "
                f"Consider reviewing if this should be classified as {opposite_type} instead of {account_type}."
            )
        
        return result
    
    def get_validation_summary(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a summary of validation findings.
        
        Args:
            findings: List of validation findings
            
        Returns:
            Summary dictionary with counts and statistics
        """
        if not findings:
            return {
                'total_violations': 0,
                'critical_violations': 0,
                'high_violations': 0,
                'medium_violations': 0,
                'violation_types': {},
                'files_affected': set()
            }
        
        summary = {
            'total_violations': len(findings),
            'critical_violations': 0,
            'high_violations': 0,
            'medium_violations': 0,
            'violation_types': defaultdict(int),
            'files_affected': set()
        }
        
        for finding in findings:
            summary['files_affected'].add(finding['source_file'])
            
            # Categorize by violation type
            reason = finding['reason']
            if 'multiple reports' in reason:
                summary['critical_violations'] += 1
                summary['violation_types']['multi_report'] += 1
            elif 'expects reporting head' in reason:
                summary['high_violations'] += 1
                summary['violation_types']['head_mismatch'] += 1
            elif 'not allowed for type' in reason:
                summary['medium_violations'] += 1
                summary['violation_types']['code_not_allowed'] += 1
            else:
                summary['medium_violations'] += 1
                summary['violation_types']['other'] += 1
        
        summary['files_affected'] = list(summary['files_affected'])
        summary['violation_types'] = dict(summary['violation_types'])
        
        return summary
