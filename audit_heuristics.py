"""
Heuristic Audit Script

Systematically reviews all keyword rules in mapping_logic_v15.py for:
- Rules that return codes incompatible with common input types
- Rules that could cause multi-report appearances
- Ambiguous patterns
- Missing type guards
"""

import ast
import json
import pathlib
import re
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict


class HeuristicAuditor:
    """Audits keyword rules for integrity and consistency issues."""
    
    def __init__(self, project_root: pathlib.Path):
        """
        Initialize the auditor.
        
        Args:
            project_root: Path to the project root directory
        """
        self.project_root = project_root
        self.keyword_rules = []
        self.integrity_rules = {}
        self.report_appearances = {}
        self._load_integrity_rules()
        self._parse_keyword_rules()
    
    def _load_integrity_rules(self):
        """Load integrity rules from configuration files."""
        # Load Account_Types_per_Financial-Reports.json
        reports_file = self.project_root / 'SystemFiles' / 'Account_Types_per_Financial-Reports.json'
        if reports_file.exists():
            with open(reports_file, 'r', encoding='utf-8') as f:
                self.integrity_rules = json.load(f)
        
        # Load report appearances from financial report JSON files
        financial_reports_dir = self.project_root / 'financial-reports'
        for report_file in financial_reports_dir.glob('*.json'):
            report_name = report_file.name
            with open(report_file, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            
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
    
    def _parse_keyword_rules(self):
        """Parse keyword rules from mapping_logic_v15.py."""
        mapping_file = self.project_root / 'mapping_logic_v15.py'
        if not mapping_file.exists():
            return
        
        with open(mapping_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the keyword_match function
        start_match = re.search(r'def keyword_match\(', content)
        if not start_match:
            return
        
        # Extract the function content
        lines = content.split('\n')
        start_line = content[:start_match.start()].count('\n')
        
        # Find the end of the function (next function definition or end of file)
        end_line = len(lines)
        for i in range(start_line + 1, len(lines)):
            line = lines[i].strip()
            if line.startswith('def ') and not line.startswith('def keyword_match'):
                end_line = i
                break
        
        # Parse the function content
        function_lines = lines[start_line:end_line]
        self._extract_rules_from_function(function_lines, start_line + 1)
    
    def _extract_rules_from_function(self, lines: List[str], start_line_num: int):
        """Extract individual rules from the keyword_match function."""
        current_rule = None
        
        for i, line in enumerate(lines):
            line_num = start_line_num + i
            line = line.strip()
            
            # Look for return statements with reporting codes
            if line.startswith('return ') and ('\'' in line or '"' in line):
                # Extract the reporting code and source
                match = re.search(r'return\s+[\'"]([^\'"]+)[\'"],\s*[\'"]([^\'"]+)[\'"]', line)
                if match:
                    reporting_code = match.group(1)
                    source = match.group(2)
                    
                    # Find the context (what conditions led to this return)
                    context_lines = []
                    for j in range(max(0, i-10), i):
                        context_line = lines[j].strip()
                        if context_line and not context_line.startswith('#'):
                            context_lines.append(context_line)
                    
                    rule = {
                        'line_number': line_num,
                        'reporting_code': reporting_code,
                        'source': source,
                        'context': ' '.join(context_lines[-3:]),  # Last 3 context lines
                        'full_context': context_lines
                    }
                    
                    # Try to extract the keyword pattern
                    keyword_pattern = self._extract_keyword_pattern(context_lines)
                    if keyword_pattern:
                        rule['keyword_pattern'] = keyword_pattern
                    
                    # Try to extract type assumptions
                    type_assumptions = self._extract_type_assumptions(context_lines)
                    if type_assumptions:
                        rule['assumes_type'] = type_assumptions
                    
                    self.keyword_rules.append(rule)
    
    def _extract_keyword_pattern(self, context_lines: List[str]) -> Optional[str]:
        """Extract the keyword pattern from context lines."""
        for line in context_lines:
            # Look for 'in txt' patterns
            match = re.search(r'[\'"]([^\'"]+)[\'"]\s+in\s+txt', line)
            if match:
                return match.group(1)
            
            # Look for 'any(' patterns
            match = re.search(r'any\([^)]*[\'"]([^\'"]+)[\'"]', line)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_type_assumptions(self, context_lines: List[str]) -> Optional[str]:
        """Extract type assumptions from context lines."""
        for line in context_lines:
            # Look for type checks
            if 'row_type' in line or 'row[\'*Type\']' in line:
                # Extract the type being checked
                match = re.search(r'[\'"]([^\'"]+)[\'"]', line)
                if match:
                    return match.group(1)
        
        return None
    
    def audit_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Perform comprehensive audit of all keyword rules.
        
        Returns:
            Dictionary with audit findings
        """
        findings = {
            'incompatible_mappings': [],
            'multi_report_risks': [],
            'ambiguous_patterns': [],
            'missing_type_guards': []
        }
        
        for rule in self.keyword_rules:
            # Check for incompatible mappings
            incompatible = self._check_incompatible_mapping(rule)
            if incompatible:
                findings['incompatible_mappings'].append(incompatible)
            
            # Check for multi-report risks
            multi_report = self._check_multi_report_risk(rule)
            if multi_report:
                findings['multi_report_risks'].append(multi_report)
            
            # Check for ambiguous patterns
            ambiguous = self._check_ambiguous_pattern(rule)
            if ambiguous:
                findings['ambiguous_patterns'].append(ambiguous)
            
            # Check for missing type guards
            missing_guard = self._check_missing_type_guard(rule)
            if missing_guard:
                findings['missing_type_guards'].append(missing_guard)
        
        return findings
    
    def _check_incompatible_mapping(self, rule: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if a rule returns codes incompatible with common input types."""
        reporting_code = rule['reporting_code']
        assumes_type = rule.get('assumes_type')
        
        if not assumes_type:
            return None
        
        # Check if the reporting code is compatible with the assumed type
        for account_type, rules in self.integrity_rules.items():
            if assumes_type.lower() in account_type.lower():
                allowed_codes = rules.get('allowed_codes', [])
                allowed_prefixes = rules.get('allowed_prefixes', [])
                
                if reporting_code not in allowed_codes:
                    # Check prefix match
                    code_prefix = reporting_code.split('.')[0] if '.' in reporting_code else reporting_code
                    if code_prefix not in allowed_prefixes:
                        return {
                            'rule': rule,
                            'issue': f"Rule assumes type '{assumes_type}' but returns code '{reporting_code}' not allowed for that type",
                            'recommendation': f"Add type guard or change output code to one of: {allowed_codes[:5]}"
                        }
        
        return None
    
    def _check_multi_report_risk(self, rule: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if a rule could cause multi-report appearances."""
        reporting_code = rule['reporting_code']
        
        if reporting_code in self.report_appearances:
            appearances = self.report_appearances[reporting_code]
            if len(appearances) > 1:
                return {
                    'rule': rule,
                    'issue': f"Reporting code '{reporting_code}' appears in multiple reports: {appearances}",
                    'recommendation': "Consider using a more specific code that appears in only one report"
                }
        
        return None
    
    def _check_ambiguous_pattern(self, rule: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for ambiguous keyword patterns."""
        keyword_pattern = rule.get('keyword_pattern')
        if not keyword_pattern:
            return None
        
        # Check if this pattern could match multiple types of accounts
        ambiguous_patterns = {
            'super': ['superannuation expense', 'super fund asset'],
            'loan': ['loan liability', 'loan asset'],
            'depreciation': ['depreciation expense', 'accumulated depreciation asset'],
            'interest': ['interest income', 'interest expense'],
            'rent': ['rental income', 'rental expense']
        }
        
        for pattern, contexts in ambiguous_patterns.items():
            if pattern in keyword_pattern.lower():
                return {
                    'rule': rule,
                    'issue': f"Keyword pattern '{keyword_pattern}' is ambiguous - could match: {contexts}",
                    'recommendation': f"Add type guard to distinguish between {contexts[0]} and {contexts[1]}"
                }
        
        return None
    
    def _check_missing_type_guard(self, rule: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if a rule is missing type guards."""
        context = rule.get('context', '')
        assumes_type = rule.get('assumes_type')
        
        # Rules that should have type guards but don't
        if assumes_type and 'row_type' not in context and 'row[\'*Type\']' not in context:
            return {
                'rule': rule,
                'issue': f"Rule assumes type '{assumes_type}' but has no type guard",
                'recommendation': f"Add type guard: if row_type not in {{'{assumes_type}'}}: return None"
            }
        
        return None
    
    def generate_report(self, findings: Dict[str, List[Dict[str, Any]]]) -> str:
        """Generate a human-readable audit report."""
        report = []
        report.append("# Heuristic Audit Report")
        report.append("")
        
        total_issues = sum(len(issues) for issues in findings.values())
        report.append(f"**Total Issues Found: {total_issues}**")
        report.append("")
        
        for category, issues in findings.items():
            if not issues:
                continue
            
            report.append(f"## {category.replace('_', ' ').title()}")
            report.append("")
            
            for i, issue in enumerate(issues, 1):
                rule = issue['rule']
                report.append(f"### Issue {i}")
                report.append(f"**Line {rule['line_number']}**: {rule['context']}")
                report.append(f"**Pattern**: {rule.get('keyword_pattern', 'N/A')}")
                report.append(f"**Output**: {rule['reporting_code']}")
                report.append(f"**Issue**: {issue['issue']}")
                report.append(f"**Recommendation**: {issue['recommendation']}")
                report.append("")
        
        return '\n'.join(report)


def main():
    """Main function to run the heuristic audit."""
    project_root = pathlib.Path(__file__).parent
    auditor = HeuristicAuditor(project_root)
    
    print("Running heuristic audit...")
    findings = auditor.audit_rules()
    
    # Write findings to JSON file
    output_file = project_root / 'heuristic_audit_findings.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(findings, f, indent=2)
    
    print(f"Audit findings written to: {output_file}")
    
    # Generate and display report
    report = auditor.generate_report(findings)
    print("\n" + "="*50)
    print(report)
    
    # Write report to file
    report_file = project_root / 'heuristic_audit_report.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nDetailed report written to: {report_file}")


if __name__ == '__main__':
    main()
