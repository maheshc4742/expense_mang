import io
import json
from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st
from agents import ExpenseOrchestrator, load_transactions, normalize_transactions, demo_transactions

st.set_page_config(page_title="Agentic AI Expense Manager", page_icon="💸", layout="wide")
st.title("💸 Agentic AI Expense Manager")
st.caption("A local-first student project for expense tracking, budget monitoring, anomaly review, and explainable recommendations.")

with st.sidebar:
    st.header("Workspace")
    mode = st.radio("Data source", ["Use demo data", "Upload CSV", "Enter expenses"])
    st.divider()
    st.subheader("Monthly budget (₹)")
    default_budget = st.number_input("Total monthly budget", min_value=0, value=15000, step=500)
    st.caption("Demo uses synthetic data. No bank connection is required.")
    st.divider()
    st.subheader("Agent settings")
    anomaly_factor = st.slider("Unusual-spend sensitivity", 1.5, 4.0, 2.5, 0.1)
    use_local_llm = st.checkbox("Use optional local LM Studio model for narrative insights", value=False)
    model_name = st.text_input("LM Studio model identifier", value="local-model", disabled=not use_local_llm)

def parse_upload(upload):
    try:
        return pd.read_csv(upload)
    except Exception as exc:
        st.error(f"Could not read CSV: {exc}")
        return None

if mode == "Use demo data":
    raw = demo_transactions()
elif mode == "Upload CSV":
    uploaded = st.file_uploader("Upload a CSV with date, description, amount and optional category/type columns", type=["csv"])
    raw = parse_upload(uploaded) if uploaded else demo_transactions()
    if not uploaded:
        st.info("Showing demo data until you upload a CSV.")
else:
    st.markdown("Add a few transactions. Positive amounts are treated as expenses; use the Type column to mark income.")
    seed = pd.DataFrame([
        {"date": str(date.today()), "description": "Groceries", "amount": 850, "type": "expense", "category": "Food"},
        {"date": str(date.today()), "description": "Bus pass", "amount": 400, "type": "expense", "category": "Transport"},
    ])
    edited = st.data_editor(seed, num_rows="dynamic", use_container_width=True, key="manual_editor")
    raw = edited

if raw is None or len(raw) == 0:
    st.warning("No transactions available.")
    st.stop()

try:
    tx = normalize_transactions(raw)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

orchestrator = ExpenseOrchestrator(monthly_budget=float(default_budget), anomaly_factor=float(anomaly_factor))
with st.spinner("Orchestrator is coordinating expense agents..."):
    result = orchestrator.run(tx, use_local_llm=use_local_llm, model_name=model_name)

summary = result["summary"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total expenses", f"₹{summary['total_expenses']:,.0f}")
c2.metric("Total income", f"₹{summary['total_income']:,.0f}")
c3.metric("Net cash flow", f"₹{summary['net_cash_flow']:,.0f}")
c4.metric("Budget used", f"{summary['budget_used_pct']:.1f}%", delta=f"₹{summary['budget_remaining']:,.0f} remaining")

if summary["budget_used_pct"] >= 100:
    st.error("Monthly budget exceeded. Review the category breakdown and flagged transactions.")
elif summary["budget_used_pct"] >= 80:
    st.warning("You have used at least 80% of your monthly budget.")
else:
    st.success("Spending is currently within the configured monthly budget.")

tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Transactions", "Agent insights", "Workflow trace"])
with tab1:
    left, right = st.columns(2)
    with left:
        expense_only = tx[tx["type"] == "expense"]
        if not expense_only.empty:
            by_cat = expense_only.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
            fig = px.pie(by_cat, names="category", values="amount", hole=0.45, title="Expenses by category")
            st.plotly_chart(fig, use_container_width=True)
    with right:
        monthly = tx.copy()
        monthly["month"] = pd.to_datetime(monthly["date"]).dt.to_period("M").astype(str)
        monthly = monthly[monthly["type"] == "expense"].groupby("month", as_index=False)["amount"].sum()
        if not monthly.empty:
            fig2 = px.bar(monthly, x="month", y="amount", title="Monthly expense trend", labels={"amount": "Expense (₹)", "month": "Month"})
            st.plotly_chart(fig2, use_container_width=True)
    st.subheader("Category budget checks")
    st.dataframe(result["category_summary"], use_container_width=True, hide_index=True)
with tab2:
    st.dataframe(tx.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
    csv_bytes = tx.to_csv(index=False).encode("utf-8")
    st.download_button("Download normalized transactions CSV", csv_bytes, file_name="normalized_expenses.csv", mime="text/csv")
with tab3:
    st.subheader("Recommendations")
    for item in result["recommendations"]:
        st.markdown(f"- {item}")
    st.subheader("Transactions flagged for review")
    if result["anomalies"].empty:
        st.info("No transactions were flagged by the current heuristic. This does not guarantee every transaction is normal.")
    else:
        st.dataframe(result["anomalies"], use_container_width=True, hide_index=True)
    st.caption("Flags are review prompts, not fraud determinations or financial advice.")
    st.subheader("Optional local model narrative")
    if use_local_llm:
        st.write(result.get("llm_narrative", "Local model narrative was not available. See recommendations above."))
with tab4:
    st.write("The orchestrator selected and executed the following steps:")
    for i, step in enumerate(result["trace"], 1):
        st.markdown(f"{i}. **{step['agent']}** — {step['action']}")
    st.json({"workflow_status": "completed", "agents_run": len(result["trace"]), "transactions_processed": len(tx)})

st.divider()
st.caption("Educational prototype only. Verify transaction data and recommendations. No bank credentials or live account integrations are used.")
