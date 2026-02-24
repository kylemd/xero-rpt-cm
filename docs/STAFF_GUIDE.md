# Xero Report Code Mapping - Staff User Guide

## Overview

This guide provides step-by-step instructions for using the Xero Report Code Mapping tool to validate and process Chart of Accounts files. The tool helps ensure accurate financial reporting by detecting integrity issues and balance anomalies.

## Getting Started

### 1. Accessing the Tool

**Option 1: Web Interface (Recommended)**
1. Open your web browser
2. Navigate to: `http://server:5000` (replace `server` with your server name)
3. Or double-click the desktop shortcut: "Xero Report Mapping"

**Option 2: Command Line**
1. Open PowerShell
2. Navigate to the project directory
3. Run: `python mapping_logic_v15.py --help`

### 2. Required Files

Before starting, ensure you have:
- **Chart of Accounts file** (CSV or XLSX format)
- **Trial Balance file** (CSV or XLSX format)
- **Template selection** (Company, Trust, Sole Trader, Partnership, or Xero Handi)

## Web Interface Usage

### Step 1: Upload Files

1. **Upload Chart of Accounts**
   - Drag and drop your Chart of Accounts file onto the "Chart of Accounts" upload zone
   - Or click "Choose File" and select your file
   - Supported formats: CSV, XLSX

2. **Upload Trial Balance**
   - Drag and drop your Trial Balance file onto the "Trial Balance" upload zone
   - Or click "Choose File" and select your file
   - Supported formats: CSV, XLSX

3. **Select Template**
   - Choose the appropriate template from the dropdown:
     - **Company**: For company structures
     - **Trust**: For trust structures
     - **Sole Trader**: For sole trader businesses
     - **Partnership**: For partnership structures
     - **Xero Handi**: For Xero Handi users

4. **Enter Industry (Optional)**
   - Type the industry context if relevant (e.g., "Building & Construction")
   - This helps with more accurate mapping

5. **Click "Validate Files"**
   - The system will analyze your files for issues

### Step 2: Review Validation Results

The validation results will show:

**Summary Cards:**
- **Total Issues Found**: Overall count of problems detected
- **Integrity Violations**: Type/Code mismatches that could cause reporting errors
- **Balance Anomalies**: Accounts with unusual balance patterns

**Actions Available:**
- **"Proceed with Mapping"**: If no issues found, continue directly to processing
- **"Resolve Issues"**: If issues found, review and fix them first

### Step 3: Resolve Issues (If Required)

#### Integrity Issues Tab

For each integrity violation:

1. **Review the Issue**
   - Account code and type
   - Current reporting code
   - Description of the problem

2. **Select Suggested Code**
   - Choose from the dropdown of valid codes
   - The system suggests codes based on integrity rules

3. **Take Action**
   - **Accept**: Apply the suggested code
   - **Skip**: Leave as-is (not recommended)

4. **Bulk Actions**
   - **"Accept All Suggestions"**: Apply all suggested fixes at once
   - **"Export Decisions"**: Save your decisions for future reference

#### Balance Anomalies Tab

For each balance anomaly:

1. **Review the Anomaly**
   - Account showing unusual balance pattern
   - Recommendation for reclassification
   - Number of periods checked

2. **View Balance History**
   - Table showing balance across multiple periods
   - Highlights periods with contrary balances

3. **Reclassify Account**
   - Select new account type from dropdown
   - Click "Reclassify" to apply change
   - Or "Skip" to leave as-is

4. **Bulk Actions**
   - **"Bulk Reclassify"**: Apply reclassifications to multiple accounts

### Step 4: Process Files

1. **Click "Proceed with Mapping"**
   - The system will process your files
   - Progress bar shows processing status

2. **Review Results**
   - Output file location
   - Number of accounts processed
   - Summary of changes made

3. **Download Results**
   - The processed Chart of Accounts file
   - Any additional reports generated

## Understanding File Formats

### Chart of Accounts Files

**Required Columns:**
- `*Code`: Unique account identifier
- `*Name`: Account name
- `*Type`: Account type (Revenue, Expense, Asset, Liability, Equity)
- `Description`: Additional account details (optional)

**Example:**
```csv
*Code,*Name,*Type,Description
100,Cash at Bank,Current Asset,Bank account
200,Sales Revenue,Revenue,Main revenue stream
300,Office Rent,Expense,Monthly office rent
```

### Trial Balance Files

**Xero Format (Auto-detected):**
- Cell A1: "Trial Balance"
- Cell A3: "As at [date]"
- First 4 rows automatically skipped

**Required Columns:**
- Account code column (AccountCode, Account Code, or Code)
- Account Type column
- Balance columns for each period

**Example:**
```csv
AccountCode,Account,Account Type,30 June 2024,30 June 2023
100,Cash at Bank,Current Asset,50000,45000
200,Sales Revenue,Revenue,100000,95000
```

## Understanding Validation Results

### Integrity Violations

**What they mean:**
- Account type and reporting code don't match
- Could cause accounts to appear in wrong report sections
- May lead to double-counting or misclassification

**Common examples:**
- Revenue account with expense reporting code
- Asset account with liability reporting code
- Account appearing in multiple reports

**How to fix:**
- Review the suggested reporting code
- Ensure it matches the account type
- Consider if the account type itself needs changing

### Balance Anomalies

**What they mean:**
- Account has balance pattern opposite to expected
- Asset account with persistent credit balance
- Liability account with persistent debit balance

**Common examples:**
- "Current Asset" account with credit balances across multiple periods
- "Revenue" account with debit balances
- "Expense" account with credit balances

**How to fix:**
- Review the balance history
- Consider reclassifying to appropriate account type
- Verify the account is correctly set up in Xero

## Best Practices

### 1. File Preparation

**Before uploading:**
- Ensure files are saved in CSV or XLSX format
- Check that required columns are present
- Verify account codes are unique
- Remove any password protection

**For Xero Trial Balance:**
- Export directly from Xero
- Don't modify the format
- Include all required periods

### 2. Issue Resolution

**For Integrity Issues:**
- Always review suggested codes
- Consider the business context
- When in doubt, consult with accounting team
- Document any manual overrides

**For Balance Anomalies:**
- Review multiple periods of data
- Consider seasonal variations
- Verify account setup in source system
- Test reclassification impact

### 3. Quality Assurance

**After processing:**
- Review the output file
- Spot-check critical accounts
- Verify totals match expectations
- Test import into target system

## Troubleshooting

### Common Issues

**File Upload Problems:**
- **Error**: "Invalid file format"
  - **Solution**: Ensure file is CSV or XLSX format
- **Error**: "File too large"
  - **Solution**: File must be under 16MB

**Validation Errors:**
- **Error**: "Missing required columns"
  - **Solution**: Check column names match requirements
- **Error**: "Template not found"
  - **Solution**: Select valid template from dropdown

**Processing Issues:**
- **Error**: "Processing failed"
  - **Solution**: Check file format and try again
- **Error**: "Server timeout"
  - **Solution**: Try with smaller files or contact IT support

### Getting Help

**For Technical Issues:**
- Contact IT Support
- Include error messages and file details
- Provide screenshots if possible

**For Business Logic Questions:**
- Consult with Accounting Team
- Review integrity rules documentation
- Check template chart examples

**For System Problems:**
- Contact System Administrator
- Report server access issues
- Request account permissions

## Advanced Features

### 1. Batch Processing

For processing multiple files:
1. Use the batch analysis interface
2. Upload multiple Chart of Accounts files
3. Review pattern analysis results
4. Apply bulk corrections

### 2. Decision Export

To save your resolution decisions:
1. Click "Export Decisions" after resolving issues
2. JSON file contains all your choices
3. Use for training improved models
4. Reference for similar future cases

### 3. ML Model Integration

The system learns from your decisions:
- Your corrections improve future suggestions
- Pattern recognition identifies common issues
- Accuracy improves over time
- Reduces manual review requirements

## Security and Privacy

### Data Handling

- Files are processed temporarily
- No permanent storage of client data
- Resolution decisions are anonymized
- Regular cleanup of temporary files

### Access Control

- Network-based access control
- User authentication for sensitive operations
- Audit trail of all processing activities
- Secure handling of financial data

## Performance Tips

### For Large Files

- Process during off-peak hours
- Consider splitting very large files
- Use batch processing for multiple files
- Monitor system performance

### For Multiple Users

- Coordinate processing schedules
- Use different server instances if available
- Clear browser cache regularly
- Report performance issues

## Conclusion

This guide covers the essential usage of the Xero Report Code Mapping tool. The system is designed to be user-friendly while providing powerful validation and correction capabilities. For additional support or advanced features, consult with the technical team or refer to the deployment documentation.

Remember: The goal is to ensure accurate financial reporting by catching and correcting issues before they impact your final reports. Take time to review and understand the validation results, and don't hesitate to ask for help when needed.
