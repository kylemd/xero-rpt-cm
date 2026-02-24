## Broken Chart of Accounts — Fix Procedure (Playbook)

### Conceptual checklist (high level)
- Normalize inputs and establish the authoritative template (entity chart)
- Propose code and naming updates to align with the template
- Resolve code collisions while preserving uniqueness and auditability
- Archive blank/conflicting accounts using derivative codes (e.g., OLD suffix)
- Append missing template accounts to the client chart
- Validate integrity: uniqueness, coverage against template, and consistency

### Procedure steps (sequential)

1) Establish inputs and constraints
- What: Load the current client COA (e.g., ChartOfAccounts_Updated_v3.csv), the entity template (e.g., ChartOfAccounts/Company.csv), and blank-accounts list (e.g., BlankAccounts_v2.csv).
- Why: The template (entity) is the source of truth for codes/names/reporting codes; blank accounts with no activity can be safely archived if they collide with default codes.
- Observations:
  - Client files often use columns with asterisks (e.g., "*Code", "*Name"). The template uses a slightly different schema ("Code", "Reporting Code", etc.).
  - Treat all codes as strings; do not coerce to numeric to avoid losing suffixes like 479.1 or alphanumerics like 840H.

2) Normalization and schema alignment
- What: Normalize column names in memory to a common working schema: Code, ReportCode, Name, ReportingName, Type, TaxCode, Description, Dashboard, ExpenseClaims, EnablePayments, Balance.
- Why: Consistent field names make downstream steps predictable and less error-prone.
- Observations:
  - Always preserve original values when writing output; map the working schema back to the client’s header style and order.

3) Propose code and name updates to align with the template
- What: For each client row, try to align with the template by:
  - Exact match by ReportCode → assign template Code and Name.
  - Else exact match by normalized Name → assign template Code and Name.
- Why: The template’s Code is canonical; names and reporting codes are standardized for downstream reporting.
- Observations:
  - Many standard items fall neatly into this rule (e.g., ReportCode EXP.UTI → 489/490/491 Telephone/Internet/Mobile). If the client only has "Telephone", we align that; we add missing items later.
  - Example: Client “Service Income” should land on template Code 210.

4) Detect and resolve collisions
- What: After proposing target Codes, identify any duplicates (two rows mapped to the same Code or mapped Code already present on a third, unchanged row).
- Why: Each Code must be unique. The order of operations matters when freeing codes.
- Observations and rules:
  - If a blank account conflicts with a default template Code, rename the blank account to Code+"OLD" and mark for archive (e.g., 801 → 801OLD). This frees the default code safely.
  - Otherwise, assign the non-blank duplicate a near-by unique alternative (e.g., 210A, 210B). Prefer short, human-friendly alphanumerics over decimals.
  - Example: Collision at 210 between “Service Income” and another item → keep 210 for Service Income; give the nonstandard item 210A (or archive if blank).

5) Apply changes (code, name, and report code)
- What: Update in-memory DataFrame with:
  - proposed Code and Name from template matches
  - the corresponding template Reporting Code (ReportCode)
- Why: Changes must be consistent across code, name, and reporting mapping.
- Observations:
  - Log each change with line number, original vs. proposed values, reason, confidence, and whether archived.

6) Append missing template lines
- What: For each template Code not present in the client after changes, append a new row using template data mapped to the client schema; default operational flags (Dashboard/ExpenseClaims/EnablePayments) to “No”.
- Why: Ensures the client COA is complete and compatible with the standard reporting tree.
- Observations:
  - Example additions include: Consulting Income (220), Dividends Received (250), Purchases (351), Audit Fees (401), Depreciation (416), Postage (462), Internet (490), Mobile Phone (491), and various asset/liability placeholders.

7) Final validations and outputs
- What: Validate post-merge:
  - All Codes are unique
  - All previously missing template Codes are now present
  - All archived items carry the OLD suffix (or documented alternative) and have archive=true in the change log
- Why: Prevent regressions and ensure auditability.
- Observations:
  - Emit the transformed COA plus optional auxiliary CSVs: Changes, Collisions, and Unmappable (if any remained).

### Lessons learned (highlights)
- Use the template’s "Reporting Code" or "Name" to determine the canonical Code and Name; this is more robust than trying to infer from client codes alone.
- Handling collisions deterministically avoids manual trial-and-error (prioritize template-aligned items and archive blank conflicts).
- Keep Codes as strings end-to-end; alphanumeric suffixes are common (e.g., 840H, 479.1).
- Append missing template rows only after applying code updates and resolving collisions, so you do not duplicate or block canonical codes.
- Provide human-readable logs (Changes, Collisions, Unmappable) so reviewers can quickly approve or adjust.
