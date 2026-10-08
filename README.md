# 🚀 SPENDWISE — Student Financial Intelligence & AI Coach

> **Hackathon-Winning Personal Finance Platform for Indian College Students.**
> *Intelligent 5-stage cognitive engine (Record ➔ Understand ➔ Predict ➔ Recommend ➔ Achieve), conversational AI Financial Coach that compares expenses in real-time, digital piggy vault with UPI micro-roundups, campus bill splitter, student perks radar, and bank-grade PDF/CSV statements.*

---

## 🏆 Key Features

| Feature | Description |
| :--- | :--- |
| **🧠 Student Financial Intelligence (SFI)** | 5-stage closed-loop cognitive radar: NLP Quick-Logger, Weekend Burn Surge Index (+134%), Campus Peer Benchmarking, and Verified Savings Audit Ledger. |
| **🤖 AI Financial Coach & Comparator** | Interactive conversational copilot that compares expenses across categories (e.g. Food vs Transport), 15-day periods, and checks purchase affordability against safe daily spend. |
| **🛡️ 3-Metric Cockpit & Health Score** | Runway Remaining (Days), Daily Burn Rate (₹/day), and Safe Daily Spend (₹/day) with 360° Financial Health scoring (A+ to D). |
| **🐷 Digital Piggy Bank & Micro-Roundups** | Interactive SVG piggy vault with confetti animations and automated spare-change round-ups to the nearest ₹10 on every UPI spend. |
| **🤝 Campus Bill Splitter** | Split hostel Swiggy feasts, late-night cabs, or flat groceries with friends; automatically logs your personal share as an expense. |
| **🎓 Student Perks Radar** | Instant access to verified student discounts (Spotify ₹69/mo, Adobe ₹398.99/mo, Apple Education, GitHub Student Pack, Prime Youth) unlocking ₹1,50,000+/year in savings. |
| **📄 Bank-Grade PDF & CSV Statements** | One-click formal financial statements with official audit ID, KPI summary matrix, and DD-MM-YYYY transaction ledgers. |
| **⚡ Zero-Friction Reliability** | Built-in SQLite with realistic Indian student demo data + MySQL support. All dates strictly formatted as **DD-MM-YYYY**. |

---

## 🏗️ Project Structure

```
final hackathon/
├── app.py                     # Flask application, RESTful endpoints & SFI routing
├── db.py                      # Database layer (SQLite default + MySQL fallback)
├── finance_engine.py          # SFI 5-stage engine, expense comparator & AI Coach
├── pdf_generator.py           # Bank-grade A4 PDF statement generator (ReportLab)
├── templates/
│   ├── base.html              # Layout, theme toggle, AI Coach drawer, modals
│   ├── dashboard.html         # Main cockpit, piggy vault, bill splitter & charts
│   └── intelligence.html      # 5-Stage Student Financial Intelligence platform
├── tests/
│   └── test_finance.py        # 15 automated unit & integration tests (100% pass)
├── runway.db                  # Auto-initialized SQLite database with student demo data
├── requirements.txt           # Production dependencies
└── Hackathon Project Final.py # User original starter code reference
```

---

## ⚡ Quickstart (Run in 10 Seconds)

### 1. Open Terminal and Navigate to Folder:
```bash
cd "/Users/janakkudtharkar/Documents/final hackathon"
```

### 2. Install Dependencies (if needed):
```bash
pip install -r requirements.txt
```

### 3. Start SPENDWISE:
```bash
python3 app.py
```

Open **`http://127.0.0.1:5001`** in your browser!

---

## 🧪 Run Automated Tests

```bash
python3 -m unittest discover -s tests
```
*15/15 tests passing with 100% success.*
