"""Tests for cross-account context pass."""
import pytest
from context_rules import CONTEXT_ANCHORS, detect_anchors, infer_from_context, infer_section


class TestAnchorDetection:
    def test_goodwill_detected_when_active(self):
        """Goodwill with non-zero balance should be detected as anchor."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
        ]
        bal = {"718": 50000.0}
        anchors = detect_anchors(accounts, bal)
        assert len(anchors) >= 1
        assert any(a["anchor_name"] == "goodwill_intangibles" for a in anchors)

    def test_goodwill_ignored_when_zero_balance(self):
        """Goodwill with zero balance should not be detected."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
        ]
        bal = {"718": 0.0}
        anchors = detect_anchors(accounts, bal)
        assert not any(a["anchor_name"] == "goodwill_intangibles" for a in anchors)

    def test_goodwill_ignored_when_no_balance(self):
        """Goodwill not in trial balance should not be detected."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
        ]
        bal = {}
        anchors = detect_anchors(accounts, bal)
        assert not any(a["anchor_name"] == "goodwill_intangibles" for a in anchors)


class TestContextInference:
    def test_capital_legal_near_goodwill(self):
        """Capital Legal Expenses near active Goodwill should infer ASS.NCA.INT."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
            {"code": "720", "name": "capital legal expenses", "type": "Non-current Asset",
             "predicted": "ASS", "source": "FallbackParent"},
        ]
        bal = {"718": 50000.0, "720": 12000.0}
        overridden = set()
        result = infer_from_context(accounts, bal, overridden)
        match = [r for r in result if r["code"] == "720"]
        assert len(match) == 1
        assert match[0]["inferred_code"] == "ASS.NCA.INT"

    def test_no_inference_when_already_specific(self):
        """Accounts with specific codes should not be overridden."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
            {"code": "720", "name": "capital legal expenses", "type": "Non-current Asset",
             "predicted": "ASS.NCA.FIX.PLA", "source": "ppe_asset"},
        ]
        bal = {"718": 50000.0, "720": 12000.0}
        overridden = set()
        result = infer_from_context(accounts, bal, overridden)
        match = [r for r in result if r["code"] == "720"]
        assert len(match) == 0

    def test_no_inference_when_overridden(self):
        """Audited overrides should be skipped."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
            {"code": "720", "name": "capital legal expenses", "type": "Non-current Asset",
             "predicted": "ASS", "source": "FallbackParent"},
        ]
        bal = {"718": 50000.0, "720": 12000.0}
        overridden = {1}  # index of code 720
        result = infer_from_context(accounts, bal, overridden)
        match = [r for r in result if r["code"] == "720"]
        assert len(match) == 0

    def test_no_inference_when_goodwill_inactive(self):
        """When goodwill has zero balance, no context inference should occur."""
        accounts = [
            {"code": "718", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
            {"code": "720", "name": "capital legal expenses", "type": "Non-current Asset",
             "predicted": "ASS", "source": "FallbackParent"},
        ]
        bal = {"718": 0.0, "720": 12000.0}
        overridden = set()
        result = infer_from_context(accounts, bal, overridden)
        assert len(result) == 0

    def test_no_inference_beyond_proximity(self):
        """Accounts beyond proximity range should not be inferred."""
        accounts = [
            {"code": "100", "name": "goodwill", "type": "Non-current Asset",
             "predicted": "ASS.NCA.INT.GOO", "source": "some_rule"},
            {"code": "200", "name": "capital legal expenses", "type": "Non-current Asset",
             "predicted": "ASS", "source": "FallbackParent"},
        ]
        bal = {"100": 50000.0, "200": 12000.0}
        overridden = set()
        result = infer_from_context(accounts, bal, overridden)
        # 200 - 100 = 100 > proximity of 50
        assert len(result) == 0


class TestSectionInference:
    def test_lone_head_among_nca_inferred(self):
        """A head-only ASS among NCA neighbours should infer ASS.NCA."""
        accounts = [
            {"code": "700", "name": "land", "type": "Non-current Asset",
             "predicted": "ASS.NCA.FIX.PLA", "source": "ppe_asset"},
            {"code": "710", "name": "equipment", "type": "Non-current Asset",
             "predicted": "ASS.NCA.FIX.PLA", "source": "ppe_asset"},
            {"code": "715", "name": "deposit bond", "type": "Non-current Asset",
             "predicted": "ASS", "source": "FallbackParent"},
            {"code": "720", "name": "other nca", "type": "Non-current Asset",
             "predicted": "ASS.NCA", "source": "some_rule"},
        ]
        bal = {"700": 100000, "710": 50000, "715": 5000, "720": 8000}
        result = infer_section(accounts, bal, set())
        match = [r for r in result if r["code"] == "715"]
        assert len(match) == 1
        assert match[0]["inferred_code"] == "ASS.NCA"

    def test_opening_balance_promoted(self):
        """Opening Balance Equity CAN be promoted by section inference.

        Previously excluded because no rule handled it; now the rule engine
        assigns EQU.RET via opening_balance_equity rule, so section inference
        would only reach it if the rule engine didn't fire first.
        """
        accounts = [
            {"code": "880", "name": "Retained Earnings", "type": "Equity",
             "predicted": "EQU.RET", "source": "some_rule"},
            {"code": "882", "name": "Opening Balance Equity", "type": "Equity",
             "predicted": "EQU", "source": "FallbackParent"},
            {"code": "885", "name": "Current Year Earnings", "type": "Equity",
             "predicted": "EQU.RET", "source": "some_rule"},
        ]
        bal = {"880": 50000, "882": 0, "885": 10000}
        result = infer_section(accounts, bal, set())
        match = [r for r in result if r["code"] == "882"]
        # Section inference now agrees with the rule engine: EQU.RET
        assert len(match) == 1
        assert match[0]["inferred_code"] == "EQU.RET"

    def test_no_inference_when_no_consensus(self):
        """Mixed neighbours should not trigger section inference."""
        accounts = [
            {"code": "700", "name": "asset a", "type": "Current Asset",
             "predicted": "ASS.CUR.REC", "source": "rule_a"},
            {"code": "710", "name": "asset b", "type": "Non-current Asset",
             "predicted": "ASS.NCA", "source": "rule_b"},
            {"code": "715", "name": "deposit", "type": "Current Asset",
             "predicted": "ASS", "source": "FallbackParent"},
        ]
        bal = {"700": 100000, "710": 50000, "715": 5000}
        result = infer_section(accounts, bal, set())
        match = [r for r in result if r["code"] == "715"]
        assert len(match) == 0
