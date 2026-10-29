"""Agentic workflow for the Expense Manager.

This prototype uses a deterministic orchestrator and specialized Python agents.
An optional local model served by LM Studio may produce a narrative, but all calculations
and budget checks are performed in Python for transparency.
"""
from __future__ import annotations
from datetime import date
import re
from openai import OpenAI
import pandas as pd

REQUIRED_COLUMNS = {"date", "description", "amount"}

CATEGORY_KEYWORDS = {
    "Food": ["grocery", "grocer", "food", "restaurant", "cafe", "coffee", "lunch", "dinner", "snack", "swiggy", "zomato"],
    "Transport": ["bus", "metro", "train", "fuel", "petrol", "uber", "ola", "taxi", "auto", "transport", "parking"],
    "Housing": ["rent", "maintenance", "electricity", "water bill", "gas bill", "internet", "wifi"],
    "Education": ["book", "course", "college", "tuition", "stationery", "exam", "education"],
    "Shopping": ["amazon", "clothes", "shopping", "shoes", "mall", "electronics"],
    "Health": ["pharmacy", "medicine", "doctor", "hospital", "clinic", "health"],
    "Entertainment": ["movie", "cinema", "game", "music", "subscription", "netflix", "event"],
    "Income": ["salary", "stipend", "scholarship", "refund", "income"],
}

def _category_for(description: str, supplied: str = "") -> str:
    if supplied and str(supplied).strip() and str(supplied).strip().lower() not in {"nan", "none"}:
        return str(supplied).strip().title()
    text = str(description).lower()
    for category, words in CATEGORY_KEYWORDS.items():
        if any(word in text for word in words):
            return category
    return "Other"

def normalize_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize accepted columns; required: date, description, amount."""
    if frame is None or frame.empty:
        raise ValueError("The uploaded or entered dataset is empty.")
    data = frame.copy()
    data.columns = [str(c).strip().lower().replace(" ", "_") for c in data.columns]
    aliases = {"transaction_date":"date", "details":"description", "merchant":"description", "value":"amount", "transaction_amount":"amount", "transaction_type":"type"}
    data = data.rename(columns={c: aliases.get(c, c) for c in data.columns})
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError("CSV is missing required column(s): " + ", ".join(sorted(missing)) + ". Required: date, description, amount.")
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["description"] = data["description"].fillna("Unspecified transaction").astype(str).str.strip()
    data["amount"] = pd.to_numeric(data["amount"].astype(str).str.replace(",", "", regex=False).str.replace("₹", "", regex=False).str.strip(), errors="coerce")
    data = data.dropna(subset=["date", "amount"]).copy()
    if data.empty:
        raise ValueError("No rows have a valid date and numeric amount.")
    if "type" not in data.columns:
        data["type"] = data["amount"].apply(lambda x: "income" if x < 0 else "expense")
    else:
        data["type"] = data["type"].fillna("").astype(str).str.lower().str.strip()
        data["type"] = data.apply(lambda r: "income" if r["type"] in {"income", "credit", "salary"} or r["amount"] < 0 else "expense", axis=1)
    # Store amounts as positive magnitudes; type distinguishes inflow/outflow.
    data["amount"] = data["amount"].abs().round(2)
    if "category" not in data.columns:
        data["category"] = ""
    data["category"] = data.apply(lambda r: _category_for(r["description"], r.get("category", "")), axis=1)
    data["date"] = data["date"].dt.strftime("%Y-%m-%d")
    data = data[["date", "description", "amount", "type", "category"]].sort_values("date").reset_index(drop=True)
    return data

def demo_transactions() -> pd.DataFrame:
    today = pd.Timestamp.today().normalize()
    rows = [
        (today - pd.Timedelta(days=27), "Monthly stipend", 8000, "income", "Income"),
        (today - pd.Timedelta(days=25), "Room rent", 4500, "expense", "Housing"),
        (today - pd.Timedelta(days=22), "Groceries", 980, "expense", "Food"),
        (today - pd.Timedelta(days=20), "Metro card", 450, "expense", "Transport"),
        (today - pd.Timedelta(days=18), "Textbooks", 750, "expense", "Education"),
        (today - pd.Timedelta(days=15), "Cafe lunch", 320, "expense", "Food"),
        (today - pd.Timedelta(days=12), "Movie tickets", 600, "expense", "Entertainment"),
        (today - pd.Timedelta(days=9), "Online shopping", 2400, "expense", "Shopping"),
        (today - pd.Timedelta(days=6), "Fuel", 700, "expense", "Transport"),
        (today - pd.Timedelta(days=3), "Restaurant dinner", 1850, "expense", "Food"),
        (today - pd.Timedelta(days=1), "Electronics purchase", 3900, "expense", "Shopping"),
    ]
    return pd.DataFrame(rows, columns=["date", "description", "amount", "type", "category"])

class CategorizationAgent:
    name = "Categorization Agent"
    def run(self, tx: pd.DataFrame) -> pd.DataFrame:
        out = tx.copy()
        out["category"] = out.apply(lambda r: _category_for(r["description"], r["category"]), axis=1)
        return out

class AnalysisAgent:
    name = "Analysis Agent"
    def run(self, tx: pd.DataFrame, budget: float) -> dict:
        expenses = tx.loc[tx.type == "expense", "amount"]
        income = tx.loc[tx.type == "income", "amount"]
        total_expenses = float(expenses.sum())
        total_income = float(income.sum())
        used = total_expenses / budget * 100 if budget > 0 else 0.0
        return {
            "total_expenses": round(total_expenses, 2),
            "total_income": round(total_income, 2),
            "net_cash_flow": round(total_income - total_expenses, 2),
            "budget_used_pct": round(used, 1),
            "budget_remaining": round(budget - total_expenses, 2),
            "monthly_budget": round(budget, 2),
            "transaction_count": int(len(tx)),
        }

class BudgetMonitorAgent:
    name = "Budget Monitor Agent"
    def run(self, tx: pd.DataFrame, budget: float, anomaly_factor: float) -> tuple[pd.DataFrame, pd.DataFrame]:
        exp = tx[tx.type == "expense"].copy()
        if exp.empty:
            return pd.DataFrame(columns=["category", "spent", "share_pct"]), exp
        by_cat = exp.groupby("category", as_index=False)["amount"].sum().rename(columns={"amount": "spent"})
        total = float(by_cat["spent"].sum())
        by_cat["share_pct"] = (by_cat["spent"] / total * 100).round(1) if total else 0
        by_cat["share_pct"] = by_cat["share_pct"].astype(float)
        # Heuristic: flag amounts above median + factor * MAD; if MAD=0, use median * factor.
        values = exp["amount"].astype(float)
        median = float(values.median())
        mad = float((values - median).abs().median())
        threshold = median + anomaly_factor * mad if mad > 0 else median * anomaly_factor
        exp["review_reason"] = exp["amount"].apply(lambda x: f"Amount exceeds heuristic threshold ₹{threshold:,.0f}" if x > threshold else "")
        anomalies = exp[exp["review_reason"] != ""].copy()
        by_cat["monthly_budget"] = budget
        by_cat["status"] = by_cat["spent"].apply(lambda x: "Review: high share" if total > 0 and x / total >= 0.4 else "Within overall budget")
        return by_cat.sort_values("spent", ascending=False), anomalies

class RecommendationAgent:
    name = "Recommendation Agent"
    def run(self, tx: pd.DataFrame, summary: dict, category_summary: pd.DataFrame, anomalies: pd.DataFrame) -> list[str]:
        tips = []
        if summary["budget_remaining"] < 0:
            tips.append(f"Spending is ₹{abs(summary['budget_remaining']):,.0f} above the configured monthly budget. Review non-essential purchases before making new discretionary commitments.")
        elif summary["budget_used_pct"] >= 80:
            tips.append(f"You have used {summary['budget_used_pct']:.1f}% of the monthly budget. Track remaining purchases carefully for the rest of the month.")
        else:
            tips.append(f"You have used {summary['budget_used_pct']:.1f}% of the configured monthly budget. Continue tracking expenses to stay within the limit.")
        if not category_summary.empty:
            top = category_summary.iloc[0]
            tips.append(f"Your largest expense category is {top['category']} at ₹{top['spent']:,.0f} ({top['share_pct']:.1f}% of expenses). Review this category for possible savings.")
        if not anomalies.empty:
            tips.append(f"{len(anomalies)} transaction(s) were flagged for manual review by a simple statistical heuristic. Check whether they are expected; a flag is not proof of fraud.")
        else:
            tips.append("No transactions were flagged by the current heuristic. This does not guarantee every transaction is normal.")
        tips.append("Set realistic category-level limits and compare actual spending with those limits weekly.")
        return tips

def local_ollama_narrative(
    summary,
    category_summary,
    recommendations,
    model_name
):
    client = OpenAI(
        base_url="http://localhost:1234/v1",
        api_key="lm-studio"
    )

    prompt = f"""
    Explain these expense results clearly and cautiously.
    Do not invent numbers.

    Summary: {summary}
    Categories: {category_summary.to_dict(orient="records")}
    Recommendations: {recommendations}

    This is educational information, not financial advice.
    """

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "You are a careful expense analysis assistant."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content

class ExpenseOrchestrator:
    """Coordinates agents and records a trace for demonstration."""
    def __init__(self, monthly_budget: float = 15000, anomaly_factor: float = 2.5):
        self.monthly_budget = float(monthly_budget)
        self.anomaly_factor = float(anomaly_factor)
        self.categorizer = CategorizationAgent()
        self.analysis = AnalysisAgent()
        self.monitor = BudgetMonitorAgent()
        self.recommender = RecommendationAgent()

    def run(self, transactions: pd.DataFrame, use_local_llm: bool = False, model_name: str = "local-model") -> dict:
        trace = []
        tx = self.categorizer.run(transactions)
        trace.append({"agent": self.categorizer.name, "action": "Checked and normalized transaction categories."})
        summary = self.analysis.run(tx, self.monthly_budget)
        trace.append({"agent": self.analysis.name, "action": "Calculated expense totals, income, net cash flow, and budget utilization."})
        category_summary, anomalies = self.monitor.run(tx, self.monthly_budget, self.anomaly_factor)
        trace.append({"agent": self.monitor.name, "action": f"Reviewed category spending and flagged {len(anomalies)} transaction(s) using a configurable heuristic."})
        recommendations = self.recommender.run(tx, summary, category_summary, anomalies)
        trace.append({"agent": self.recommender.name, "action": "Generated recommendations based on calculated results and review flags."})
        narrative = None
        if use_local_llm:
            narrative = local_ollama_narrative(summary, category_summary, recommendations, model_name)
            trace.append({"agent": "Optional Local LLM", "action": "Attempted to turn computed results into a readable narrative; calculations remain deterministic."})
        return {"transactions": tx, "summary": summary, "category_summary": category_summary, "anomalies": anomalies, "recommendations": recommendations, "trace": trace, "llm_narrative": narrative}

# Public alias used by the app and tests.
def load_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    return normalize_transactions(frame)
