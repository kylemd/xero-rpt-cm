import pandas as pd
import csv
import re


def main() -> None:
    # Read with *Code as string to avoid float coercion like 200.0
    coa = pd.read_csv("AugmentedChartOfAccounts.csv", dtype={"*Code": "string"})

    # SourceSummary.csv
    summary = (
        coa.groupby("Source")
        .agg(Count=("Source", "size"), ReviewCount=("NeedsReview", lambda s: (s == "Y").sum()))
        .reset_index()
    )
    summary.to_csv("SourceSummary.csv", index=False, quoting=csv.QUOTE_MINIMAL)

    # NeedsReviewSample.csv (up to 25 rows)
    needs = coa[coa["NeedsReview"] == "Y"].copy()
    needs = needs.rename(
        columns={
            "*Code": "AccountCode",
            "*Name": "Name",
            "Report Code": "ExistingReportCode",
        }
    )
    if "SuggestedParent" not in needs.columns:
        needs["SuggestedParent"] = ""
    # Ensure AccountCode is correctly formatted: numeric-only codes as integers (no decimals)
    if "AccountCode" in needs.columns:
        def _fmt_code(v):
            s = "" if pd.isna(v) else str(v).strip()
            if re.fullmatch(r"\d+", s):
                return int(s)
            m = re.fullmatch(r"(\d+)\.0+", s)
            if m:
                return int(m.group(1))
            return s
        needs["AccountCode"] = needs["AccountCode"].apply(_fmt_code)
    keep_cols = [
        c
        for c in [
            "AccountCode",
            "Name",
            "ExistingReportCode",
            "predictedReportCode",
            "predictedMappingName",
            "SuggestedParent",
            "Source",
        ]
        if c in needs.columns
    ]
    needs.head(25)[keep_cols].to_csv(
        "NeedsReviewSample.csv", index=False, quoting=csv.QUOTE_MINIMAL
    )

    print("OK")


if __name__ == "__main__":
    main()


