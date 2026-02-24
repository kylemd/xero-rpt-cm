"""Tests for the rule engine."""
from rule_engine import Rule, evaluate_rules, MatchContext


class TestRuleCreation:
    def test_rule_creation(self):
        rule = Rule(
            name="test_rule",
            code="EXP.VEH",
            priority=70,
            keywords=["motor vehicle"],
        )
        assert rule.name == "test_rule"
        assert rule.code == "EXP.VEH"
        assert rule.priority == 70
        assert rule.keywords == ["motor vehicle"]

    def test_rule_defaults(self):
        rule = Rule(name="minimal", code="EXP", priority=50)
        assert rule.keywords == []
        assert rule.keywords_all == []
        assert rule.keywords_exclude == []
        assert rule.raw_types == set()
        assert rule.canon_types == set()
        assert rule.type_exclude == set()
        assert rule.template is None
        assert rule.owner_context is False
        assert rule.name_only is False
        assert rule.notes == ""


class TestRuleMatching:
    def test_simple_keyword_match(self):
        rules = [
            Rule(name="vehicle_expense", code="EXP.VEH", priority=70,
                 keywords=["motor vehicle"]),
        ]
        ctx = MatchContext(
            normalised_text="motor vehicle fuel",
            raw_type="Expense",
            canon_type="expense",
            template_name="company",
        )
        code, rule_name = evaluate_rules(rules, ctx)
        assert code == "EXP.VEH"
        assert rule_name == "vehicle_expense"

    def test_no_match_returns_none(self):
        rules = [
            Rule(name="vehicle_expense", code="EXP.VEH", priority=70,
                 keywords=["motor vehicle"]),
        ]
        ctx = MatchContext(
            normalised_text="office supplies",
            raw_type="Expense",
            canon_type="expense",
            template_name="company",
        )
        code, rule_name = evaluate_rules(rules, ctx)
        assert code is None
        assert rule_name is None

    def test_highest_priority_wins(self):
        rules = [
            Rule(name="generic_expense", code="EXP", priority=50,
                 keywords=["insurance"]),
            Rule(name="vehicle_insurance", code="EXP.VEH", priority=70,
                 keywords_all=["motor vehicle", "insurance"]),
        ]
        ctx = MatchContext(
            normalised_text="motor vehicle insurance",
            raw_type="Expense",
            canon_type="expense",
            template_name="company",
        )
        code, rule_name = evaluate_rules(rules, ctx)
        assert code == "EXP.VEH"
        assert rule_name == "vehicle_insurance"

    def test_type_constraint_filters(self):
        rules = [
            Rule(name="wages_direct", code="EXP.COS.WAG", priority=95,
                 keywords=["wages"],
                 raw_types={"direct costs", "cost of sales"}),
        ]
        ctx = MatchContext(
            normalised_text="construction wages",
            raw_type="Expense",
            canon_type="expense",
            template_name="company",
        )
        code, rule_name = evaluate_rules(rules, ctx)
        assert code is None

    def test_keywords_exclude(self):
        rules = [
            Rule(name="depreciation_expense", code="EXP.DEP", priority=70,
                 keywords=["depreciation"],
                 keywords_exclude=["accumulated"]),
        ]
        ctx = MatchContext(
            normalised_text="accumulated depreciation on vehicles",
            raw_type="Fixed Asset",
            canon_type="fixed asset",
            template_name="company",
        )
        code, rule_name = evaluate_rules(rules, ctx)
        assert code is None

    def test_template_constraint(self):
        rules = [
            Rule(name="company_funds", code="LIA.NCL.ADV", priority=90,
                 keywords=["funds introduced"],
                 template="company"),
        ]
        ctx = MatchContext(
            normalised_text="owner a funds introduced",
            raw_type="Equity",
            canon_type="equity",
            template_name="trust",
        )
        code, rule_name = evaluate_rules(rules, ctx)
        assert code is None

    def test_owner_context(self):
        rules = [
            Rule(name="drawings", code="EQU.DRA", priority=90,
                 keywords=["drawings"],
                 owner_context=True),
        ]
        owner_keywords = ["owner a", "proprietor", "drawings"]
        ctx = MatchContext(
            normalised_text="office supplies drawings account",
            raw_type="Equity",
            canon_type="equity",
            template_name="company",
            owner_keywords=owner_keywords,
        )
        code, rule_name = evaluate_rules(rules, ctx)
        assert code == "EQU.DRA"

    def test_canon_type_constraint(self):
        rules = [
            Rule(name="insurance_general", code="EXP.INS", priority=70,
                 keywords=["insurance"],
                 canon_types={"expense"}),
        ]
        ctx = MatchContext(
            normalised_text="insurance premium asset",
            raw_type="Current Asset",
            canon_type="current asset",
            template_name="company",
        )
        code, rule_name = evaluate_rules(rules, ctx)
        assert code is None

    def test_raw_type_case_insensitive(self):
        rules = [
            Rule(name="bank_default", code="ASS.CUR.CAS.BAN", priority=100,
                 raw_types={"bank"}),
        ]
        ctx = MatchContext(
            normalised_text="westpac cheque",
            raw_type="Bank",
            canon_type="bank",
            template_name="company",
        )
        code, _ = evaluate_rules(rules, ctx)
        assert code == "ASS.CUR.CAS.BAN"

    def test_type_exclude(self):
        rules = [
            Rule(name="gst_liability", code="LIA.CUR.TAX.GST", priority=80,
                 keywords=["gst"],
                 type_exclude={"expense"}),
        ]
        ctx = MatchContext(
            normalised_text="gst on expenses",
            raw_type="Expense",
            canon_type="expense",
            template_name="company",
        )
        code, _ = evaluate_rules(rules, ctx)
        assert code is None
