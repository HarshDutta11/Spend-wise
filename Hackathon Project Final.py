import os
from datetime import date
from decimal import Decimal

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-only-secret-key")

CATEGORIES = ["Food", "Transport", "Education", "Entertainment", "Shopping", "Bills", "Health", "Other"]


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "student_finance"),
    )


def query(sql, values=(), fetchone=False, commit=False):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(sql, values)
    result = cursor.fetchone() if fetchone else cursor.fetchall()
    if commit:
        connection.commit()
    cursor.close()
    connection.close()
    return result


def financial_health_score(income, expenses, budget_overruns):
    if income <= 0:
        return 0, "Add your monthly income to calculate a useful score."

    savings_rate = max(0, (income - expenses) / income)
    spending_ratio = expenses / income
    score = 45 + min(savings_rate * 100, 35)
    score -= max(0, spending_ratio - 0.80) * 100
    score -= min(budget_overruns * 5, 20)
    score = round(max(0, min(100, score)))

    if score >= 80:
        message = "Excellent! You are spending responsibly and building savings."
    elif score >= 60:
        message = "Good progress. Try reducing spending in categories over budget."
    elif score >= 40:
        message = "Watch your spending closely and set realistic category budgets."
    else:
        message = "Your expenses are high for your income. Focus on essentials first."
    return score, message


@app.route("/")
def dashboard():
    user = query("SELECT * FROM users ORDER BY id LIMIT 1", fetchone=True)
    if not user:
        return "Run database.sql first to create a user.", 500

    totals = query(
        """SELECT
               COALESCE(SUM(CASE WHEN transaction_type = 'income' THEN amount END), 0) AS added_income,
               COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount END), 0) AS expenses
           FROM transactions WHERE user_id = %s""",
        (user["id"],), fetchone=True,
    )
    income = Decimal(user["monthly_income"]) + Decimal(totals["added_income"])
    expenses = Decimal(totals["expenses"])
    budgets = query(
        """SELECT b.category, b.monthly_limit, COALESCE(SUM(t.amount), 0) AS spent
           FROM budgets b LEFT JOIN transactions t
             ON b.user_id = t.user_id AND b.category = t.category AND t.transaction_type = 'expense'
           WHERE b.user_id = %s GROUP BY b.id, b.category, b.monthly_limit""",
        (user["id"],),
    )
    overruns = sum(Decimal(row["spent"]) > Decimal(row["monthly_limit"]) for row in budgets)
    score, message = financial_health_score(income, expenses, overruns)
    recent_transactions = query(
        "SELECT * FROM transactions WHERE user_id = %s ORDER BY transaction_date DESC, id DESC LIMIT 8",
        (user["id"],),
    )
    category_totals = query(
        """SELECT category, SUM(amount) AS amount FROM transactions
           WHERE user_id = %s AND transaction_type = 'expense'
           GROUP BY category ORDER BY amount DESC""",
        (user["id"],),
    )
    return render_template("dashboard.html", user=user, income=income, expenses=expenses,
                           balance=income - expenses, score=score, message=message,
                           budgets=budgets, transactions=recent_transactions,
                           category_totals=category_totals, categories=CATEGORIES,
                           today=date.today().isoformat())


@app.post("/transaction")
def add_transaction():
    try:
        description = request.form["description"].strip()
        category = request.form["category"]
        amount = Decimal(request.form["amount"])
        transaction_type = request.form["transaction_type"]
        transaction_date = request.form["transaction_date"]
        if not description or amount <= 0 or category not in CATEGORIES or transaction_type not in ("income", "expense"):
            raise ValueError
        user = query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        query("""INSERT INTO transactions (user_id, description, category, amount, transaction_type, transaction_date)
                 VALUES (%s, %s, %s, %s, %s, %s)""",
              (user["id"], description, category, amount, transaction_type, transaction_date), commit=True)
        flash("Transaction added.", "success")
    except (KeyError, ValueError):
        flash("Enter a valid description, amount, category, type, and date.", "error")
    return redirect(url_for("dashboard"))


@app.post("/budget")
def save_budget():
    try:
        category = request.form["category"]
        limit = Decimal(request.form["monthly_limit"])
        if category not in CATEGORIES or limit <= 0:
            raise ValueError
        user = query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        query("""INSERT INTO budgets (user_id, category, monthly_limit) VALUES (%s, %s, %s)
                 ON DUPLICATE KEY UPDATE monthly_limit = VALUES(monthly_limit)""",
              (user["id"], category, limit), commit=True)
        flash("Budget saved.", "success")
    except (KeyError, ValueError):
        flash("Enter a valid budget amount.", "error")
    return redirect(url_for("dashboard"))


@app.post("/profile")
def update_profile():
    try:
        name = request.form["name"].strip()
        monthly_income = Decimal(request.form["monthly_income"])
        if not name or monthly_income < 0:
            raise ValueError
        user = query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        query("UPDATE users SET name = %s, monthly_income = %s WHERE id = %s", (name, monthly_income, user["id"]), commit=True)
        flash("Profile updated.", "success")
    except (KeyError, ValueError):
        flash("Enter a valid name and income.", "error")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
