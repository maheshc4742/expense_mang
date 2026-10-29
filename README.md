# Agentic AI Expense Manager

A student-friendly, local-first prototype demonstrating agent-style coordination for expense categorization, spending analysis, budget monitoring, anomaly review, and recommendations.

## Features
- Use demo transactions, upload a CSV, or enter transactions manually.
- Dashboard with total expenses, income, net cash flow, budget usage, and charts.
- Specialized agents coordinated by a Python orchestrator.
- Statistical heuristic flags unusually large expense amounts for review.
- Workflow trace makes agent actions visible for an AAT demonstration.
- Optional LM Studio narrative (not required for core features).
- CSV export and local processing; no bank connection or paid API required.

## Requirements
- Python 3.10 or newer (Python 3.11 recommended).
- Internet only for installing dependencies. The core app does not call paid cloud APIs.
- Optional: LM Studio with a downloaded and loaded model if you want an AI-generated narrative.

## Run on Windows
```powershell
cd agentic_ai_expense_manager
py -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
streamlit run app.py
```
Open the local URL shown by Streamlit (usually http://localhost:8501).

## CSV format
Required columns: `date`, `description`, `amount`. Optional columns: `type`, `category`.
- Dates should be parseable by pandas.
- `type` may be `expense` or `income`.
- Positive values are treated as expenses unless `type` says income; negative amounts are stored as positive magnitudes and treated as income when no type column is supplied.
- Categories may be supplied, or inferred from simple keywords.

Example:
```csv
date,description,amount,type,category
2026-10-02,Groceries,500,expense,Food
2026-10-03,Stipend,5000,income,Income
```

## Optional LM Studio narrative
1. Install LM Studio and download a compatible chat model.
2. Load the model in LM Studio and start its local server from the Developer tab. The default server URL is `http://localhost:1234/v1`.
3. Copy the model identifier shown by the server into the “LM Studio model identifier” field in the app, then enable “Use optional local LM Studio model for narrative insights”.
The narrative request is sent only to the local LM Studio server. Core expense calculations and recommendations remain deterministic.

## Tests
```powershell
python -m pytest
```

## Architecture
1. Categorization Agent: validates categories and fills missing ones.
2. Analysis Agent: calculates totals, cash flow, and budget usage.
3. Budget Monitor Agent: creates category summary and flags large transactions with a median/MAD heuristic.
4. Recommendation Agent: generates rules-based, explainable suggestions.
5. Orchestrator: coordinates agents and records a workflow trace.
6. Optional Local LLM: writes a narrative from computed results; it does not calculate the core metrics.

## Important limitations
- This is an educational prototype, not a financial advisor.
- Anomaly flags are heuristic review prompts, not fraud detection.
- Budget is treated as one overall budget; category summary is descriptive and does not implement individual category limits yet.
- Keyword categorization can be wrong and should be reviewed.
- Demo data is synthetic. Do not upload sensitive personal data to a shared or public deployment.
- The term “agentic” is demonstrated through coordinated specialist tasks, conditional workflow, tool calls to local analysis functions, and an execution trace. It is a lightweight orchestration prototype, not an unconstrained autonomous agent.
