import pandas as pd
from agents import normalize_transactions, ExpenseOrchestrator

def test_normalize_and_category():
    raw = pd.DataFrame([{"date":"2026-10-01","description":"Groceries","amount":"250"}])
    tx = normalize_transactions(raw)
    assert list(tx.columns) == ["date", "description", "amount", "type", "category"]
    assert tx.iloc[0]["category"] == "Food"
    assert tx.iloc[0]["type"] == "expense"

def test_income_and_budget_summary():
    raw = pd.DataFrame([
        {"date":"2026-10-01","description":"Salary","amount":1000,"type":"income","category":"Income"},
        {"date":"2026-10-02","description":"Food","amount":200,"type":"expense","category":"Food"},
    ])
    tx = normalize_transactions(raw)
    result = ExpenseOrchestrator(monthly_budget=500).run(tx)
    assert result["summary"]["total_income"] == 1000
    assert result["summary"]["total_expenses"] == 200
    assert result["summary"]["budget_remaining"] == 300

def test_missing_columns_raise():
    raw = pd.DataFrame([{"merchant":"shop","amount":10}])
    try:
        normalize_transactions(raw)
    except ValueError as exc:
        assert "missing required" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError")
