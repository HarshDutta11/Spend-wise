import io
import os
import csv
import json
import math
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    Response,
    url_for,
)
import db
import finance_engine
import gemini_service

app = Flask(__name__)
app.config["SECRET_KEY"] = "spendwise-hackathon-winning-secret-2026"

CATEGORIES = [
    {"name": "Food", "icon": "🍛", "color": "#f59e0b"},
    {"name": "Bills", "icon": "⚡", "color": "#ef4444"},
    {"name": "Transport", "icon": "🛵", "color": "#3b82f6"},
    {"name": "Education", "icon": "📚", "color": "#8b5cf6"},
    {"name": "Entertainment", "icon": "🎬", "color": "#ec4899"},
    {"name": "Shopping", "icon": "🛍️", "color": "#14b8a6"},
    {"name": "Health", "icon": "💊", "color": "#10b981"},
    {"name": "Other", "icon": "✨", "color": "#6b7280"},
]
CATEGORY_NAMES = [c["name"] for c in CATEGORIES]
CATEGORY_MAP = {c["name"]: c for c in CATEGORIES}


@app.before_request
def ensure_initialized():
    if not hasattr(app, "_db_initialized"):
        db.init_db()
        app._db_initialized = True


def get_current_user():
    user = db.query("SELECT * FROM users ORDER BY id LIMIT 1", fetchone=True)
    if not user:
        db.init_db()
        user = db.query("SELECT * FROM users ORDER BY id LIMIT 1", fetchone=True)
    return user


def get_piggy_balance(user_id):
    row = db.query(
        """SELECT
             COALESCE(SUM(CASE WHEN action_type IN ('deposit', 'roundup') THEN amount ELSE -amount END), 0) AS balance,
             COALESCE(SUM(CASE WHEN action_type = 'roundup' THEN amount ELSE 0 END), 0) AS total_roundups
           FROM piggy_bank WHERE user_id = %s""",
        (user_id,), fetchone=True,
    )
    balance = Decimal(str(row["balance"] if row and row["balance"] is not None else 0))
    roundups = Decimal(str(row["total_roundups"] if row and row["total_roundups"] is not None else 0))
    return max(Decimal("0.00"), balance), roundups


@app.route("/")
def dashboard():
    user = get_current_user()
    uid = user["id"]

    # 1. Cash flow totals
    totals = db.query(
        """SELECT
             COALESCE(SUM(CASE WHEN transaction_type = 'income' THEN amount END), 0) AS added_income,
             COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount END), 0) AS expenses
           FROM transactions WHERE user_id = %s""",
        (uid,), fetchone=True,
    )
    base_income = Decimal(str(user["monthly_income"]))
    added_income = Decimal(str(totals["added_income"] or 0))
    total_income = base_income + added_income
    expenses = Decimal(str(totals["expenses"] or 0))
    net_balance = total_income - expenses

    # 2. Piggy Bank Vault
    piggy_balance, total_roundups = get_piggy_balance(uid)
    piggy_history = db.query(
        "SELECT * FROM piggy_bank WHERE user_id = %s ORDER BY id DESC LIMIT 5",
        (uid,),
    )
    for p in piggy_history:
        p["formatted_date"] = finance_engine.format_dmy(p.get("action_date"))

    # 3. Category Budgets
    budgets = db.query(
        """SELECT b.id, b.category, b.monthly_limit, COALESCE(SUM(t.amount), 0) AS spent
           FROM budgets b LEFT JOIN transactions t
             ON b.user_id = t.user_id AND b.category = t.category AND t.transaction_type = 'expense'
           WHERE b.user_id = %s GROUP BY b.id, b.category, b.monthly_limit""",
        (uid,),
    )
    for b in budgets:
        limit = Decimal(str(b["monthly_limit"]))
        spent = Decimal(str(b["spent"]))
        b["limit_dec"] = limit
        b["spent_dec"] = spent
        b["percent"] = min(100, round(float((spent / limit) * 100))) if limit > 0 else 0
        b["overrun"] = spent > limit
        b["remaining"] = max(Decimal("0"), limit - spent)
        b["meta"] = CATEGORY_MAP.get(b["category"], {"icon": "🏷️", "color": "#6b7280"})

    # 4. Savings Goals
    goals_raw = db.query(
        "SELECT * FROM savings_goals WHERE user_id = %s ORDER BY id ASC",
        (uid,),
    )
    total_saved_in_goals = Decimal("0")
    goals = []
    monthly_savings_pace = max(Decimal("1000.00"), (total_income - expenses))
    for g in goals_raw:
        target = Decimal(str(g["target_amount"]))
        current = Decimal(str(g["current_amount"]))
        total_saved_in_goals += current
        proj = finance_engine.calculate_goal_projection(
            target_amount=target,
            current_amount=current,
            target_date_str=g["target_date"],
            monthly_savings_rate=monthly_savings_pace,
        )
        g_dict = dict(g)
        g_dict.update(proj)
        g_dict["target_date_dmy"] = finance_engine.format_dmy(g.get("target_date"))
        goals.append(g_dict)

    total_liquid_savings = piggy_balance + total_saved_in_goals

    # 5. Category Breakdown
    category_totals = db.query(
        """SELECT category, SUM(amount) AS amount FROM transactions
           WHERE user_id = %s AND transaction_type = 'expense'
           GROUP BY category ORDER BY amount DESC""",
        (uid,),
    )
    for c in category_totals:
        c["amount_dec"] = Decimal(str(c["amount"]))
        c["meta"] = CATEGORY_MAP.get(c["category"], {"icon": "🏷️", "color": "#6b7280"})
        if expenses > 0:
            c["share_pct"] = round(float((c["amount_dec"] / expenses) * 100), 1)
        else:
            c["share_pct"] = 0

    # 6. Financial Health Score (360-degree engine)
    health = finance_engine.calculate_financial_health_score(
        income=total_income,
        expenses=expenses,
        budgets_data=budgets,
        liquid_savings=total_liquid_savings,
        category_breakdown=category_totals,
    )

    # 7. Cockpit Metrics (Matches user attached screenshot hero banner!)
    cockpit = finance_engine.calculate_daily_cockpit(
        income=total_income,
        expenses=expenses,
        liquid_savings=total_liquid_savings,
        score=health["score"]
    )

    # 8. AI Advisor Insights
    insights = finance_engine.generate_ai_insights(
        income=total_income,
        expenses=expenses,
        budgets_data=budgets,
        category_breakdown=category_totals,
        goals_data=goals,
        piggy_balance=piggy_balance,
    )

    # 9. Recent transactions strictly formatted in DD-MM-YYYY
    recent_transactions = db.query(
        "SELECT * FROM transactions WHERE user_id = %s ORDER BY id DESC LIMIT 10",
        (uid,),
    )
    for tx in recent_transactions:
        tx["meta"] = CATEGORY_MAP.get(tx["category"], {"icon": "🏷️", "color": "#6b7280"})
        tx["formatted_date"] = finance_engine.format_dmy(tx.get("transaction_date"))

    # 10. Bill Splits
    bill_splits = db.query(
        "SELECT * FROM bill_splits WHERE user_id = %s ORDER BY id DESC",
        (uid,),
    )
    total_owed_to_me = Decimal("0.00")
    total_i_owe = Decimal("0.00")
    for s in bill_splits:
        s["formatted_date"] = finance_engine.format_dmy(s.get("created_date"))
        tot = Decimal(str(s["total_amount"]))
        mshare = Decimal(str(s["my_share"]))
        if s["settled"] == 0:
            if s["paid_by"].lower() == "you":
                total_owed_to_me += (tot - mshare)
            else:
                total_i_owe += mshare

    # 11. Badges
    badges = db.query("SELECT * FROM badges WHERE user_id = %s ORDER BY id ASC", (uid,))
    for b in badges:
        b["formatted_date"] = finance_engine.format_dmy(b.get("unlocked_at"))

    # 12. Recurring Payments & Transit Passes (Metro, Bus, Mess, Recharges)
    recurring_raw = db.query(
        "SELECT * FROM recurring_payments WHERE user_id = %s ORDER BY id ASC",
        (uid,),
    )
    recurring_payments = []
    for r in recurring_raw:
        r_dict = dict(r)
        r_dict["amount_dec"] = Decimal(str(r_dict.get("amount", 0)))
        r_dict["formatted_due_date"] = finance_engine.format_dmy(r_dict.get("next_due_date"))
        r_dict["due_status"] = finance_engine.calculate_due_status(r_dict["formatted_due_date"])
        r_dict["meta"] = CATEGORY_MAP.get(r_dict.get("category"), {"icon": "🏷️", "color": "#6b7280"})
        recurring_payments.append(r_dict)

    recurring_metrics = finance_engine.calculate_recurring_metrics(recurring_payments)

    today_dmy = date.today().strftime("%d-%m-%Y")

    return render_template(
        "dashboard.html",
        user=user,
        income=total_income,
        base_income=base_income,
        added_income=added_income,
        expenses=expenses,
        balance=net_balance,
        piggy_balance=piggy_balance,
        total_roundups=total_roundups,
        piggy_history=piggy_history,
        total_liquid_savings=total_liquid_savings,
        budgets=budgets,
        goals=goals,
        health=health,
        cockpit=cockpit,
        insights=insights,
        transactions=recent_transactions,
        category_totals=category_totals,
        categories=CATEGORIES,
        student_offers=finance_engine.STUDENT_OFFERS,
        bill_splits=bill_splits,
        total_owed_to_me=total_owed_to_me,
        total_i_owe=total_i_owe,
        badges=badges,
        recurring_payments=recurring_payments,
        recurring_metrics=recurring_metrics,
        today_dmy=today_dmy,
    )


@app.post("/transaction")
def add_transaction():
    user = get_current_user()
    uid = user["id"]
    try:
        description = request.form["description"].strip()
        category = request.form["category"]
        amount = Decimal(request.form["amount"])
        transaction_type = request.form["transaction_type"]
        raw_date = request.form.get("transaction_date", "").strip()
        # Strictly format to DD-MM-YYYY
        transaction_date = finance_engine.format_dmy(raw_date)
        notes = request.form.get("notes", "").strip()
        roundup_opt = request.form.get("auto_roundup") == "1"

        if not description or amount <= 0 or category not in CATEGORY_NAMES or transaction_type not in ("income", "expense"):
            raise ValueError("Invalid transaction inputs")

        # Check if transaction crosses provided category budget limit
        budget_warning = False
        if transaction_type == "expense":
            b_info = db.query(
                """SELECT b.monthly_limit, COALESCE(SUM(t.amount), 0) AS current_spent
                   FROM budgets b LEFT JOIN transactions t
                     ON b.user_id = t.user_id AND b.category = t.category AND t.transaction_type = 'expense'
                   WHERE b.user_id = %s AND b.category = %s
                   GROUP BY b.monthly_limit""",
                (uid, category),
                fetchone=True,
            )
            if b_info:
                b_limit = Decimal(str(b_info["monthly_limit"]))
                b_spent = Decimal(str(b_info["current_spent"]))
                if (b_spent + amount) > b_limit:
                    budget_warning = True

        # Do NOT decline the transaction - insert and save normally
        db.query(
            """INSERT INTO transactions (user_id, description, category, amount, transaction_type, transaction_date, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (uid, description, category, amount, transaction_type, transaction_date, notes),
            commit=True,
        )

        if roundup_opt and transaction_type == "expense":
            roundup_amt = finance_engine.calculate_roundup(amount, round_to=10)
            if roundup_amt > 0:
                ceil_ten = math.ceil(float(amount) / 10) * 10
                db.query(
                    """INSERT INTO piggy_bank (user_id, action_type, amount, description, action_date)
                       VALUES (%s, 'roundup', %s, %s, %s)""",
                    (uid, roundup_amt, f"Round-up: {description} (₹{float(amount):.2f} -> ₹{ceil_ten:.2f})", transaction_date),
                    commit=True,
                )
                if budget_warning:
                    flash(f"⚠️ you are about to cross your monthly limit for this catagory! Logged ₹{float(amount):.2f} in {category} & stashed ₹{float(roundup_amt):.2f} into Piggy Vault! 🐷🪙", "warning")
                else:
                    flash(f"Transaction logged on {transaction_date} & ₹{float(roundup_amt):.2f} stashed into Piggy Vault! 🐷🪙", "success")
                return redirect(url_for("dashboard"))

        if budget_warning:
            flash(f"⚠️ you are about to cross your monthly limit for this catagory! Logged {transaction_type.capitalize()} of ₹{float(amount):.2f} on {transaction_date} for '{description}'.", "warning")
        else:
            flash(f"Logged {transaction_type.capitalize()} of ₹{float(amount):.2f} on {transaction_date} for '{description}'.", "success")
    except Exception as e:
        flash(f"Failed to add transaction: {e}", "error")

    return redirect(url_for("dashboard"))


@app.post("/bill-split")
def add_bill_split():
    user = get_current_user()
    uid = user["id"]
    try:
        title = request.form["title"].strip()
        total_amount = Decimal(request.form["total_amount"])
        split_count = int(request.form.get("split_count", 2))
        paid_by = request.form.get("paid_by", "You").strip()
        friends = request.form.get("friends", "").strip()
        auto_record = request.form.get("auto_record") == "1"
        category = request.form.get("category", "Food")
        
        today_dmy = date.today().strftime("%d-%m-%Y")

        if not title or total_amount <= 0 or split_count < 1:
            raise ValueError("Invalid bill split inputs.")

        my_share = (total_amount / Decimal(split_count)).quantize(Decimal("0.01"), rounding=finance_engine.ROUND_HALF_UP)

        if not friends:
            friends = f"{split_count} friends split (₹{float(my_share):,.2f} each)"

        db.query(
            """INSERT INTO bill_splits (user_id, title, total_amount, paid_by, my_share, split_count, friends, settled, created_date)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s)""",
            (uid, title, total_amount, paid_by, my_share, split_count, friends, today_dmy),
            commit=True,
        )

        if auto_record:
            desc = f"Bill Split: {title} (My Share)"
            db.query(
                """INSERT INTO transactions (user_id, description, category, amount, transaction_type, transaction_date, notes)
                   VALUES (%s, %s, %s, %s, 'expense', %s, %s)""",
                (uid, desc, category, my_share, today_dmy, f"Split with: {friends}"),
                commit=True,
            )

        flash(f"Bill '{title}' split successfully! Your share: ₹{float(my_share):,.2f} (Logged on {today_dmy}).", "success")
    except Exception as e:
        flash(f"Failed to split bill: {e}", "error")

    return redirect(url_for("dashboard"))


@app.post("/bill-split/<int:split_id>/settle")
def settle_bill_split(split_id):
    user = get_current_user()
    uid = user["id"]
    db.query("UPDATE bill_splits SET settled = 1 WHERE id = %s AND user_id = %s", (split_id, uid), commit=True)
    flash("🎉 Bill settled up successfully!", "success")
    return redirect(url_for("dashboard"))


@app.post("/bill-split/<int:split_id>/delete")
def delete_bill_split(split_id):
    user = get_current_user()
    uid = user["id"]
    db.query("DELETE FROM bill_splits WHERE id = %s AND user_id = %s", (split_id, uid), commit=True)
    flash("Bill split record removed.", "info")
    return redirect(url_for("dashboard"))


# ================= RECURRING PAYMENTS & TRANSIT PASSES =================

@app.post("/recurring-payments")
def add_recurring_payment():
    user = get_current_user()
    uid = user["id"]
    try:
        title = request.form["title"].strip()
        category = request.form.get("category", "Transport").strip()
        amount = Decimal(request.form["amount"])
        frequency = request.form.get("frequency", "Monthly").strip()
        payment_method = request.form.get("payment_method", "UPI / SmartCard").strip()
        raw_due_date = request.form.get("next_due_date", "").strip()
        next_due_date = finance_engine.format_dmy(raw_due_date) if raw_due_date else (date.today() + timedelta(days=30)).strftime("%d-%m-%Y")
        auto_roundup = 1 if request.form.get("auto_roundup") == "1" else 0
        notes = request.form.get("notes", "").strip()

        if not title or amount <= 0:
            raise ValueError("Invalid recurring payment details")

        db.query(
            """INSERT INTO recurring_payments (user_id, title, category, amount, frequency, payment_method, next_due_date, status, auto_roundup, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (uid, title, category, amount, frequency, payment_method, next_due_date, "Active", auto_roundup, notes),
            commit=True,
        )
        flash(f"✅ Recurring commitment '{title}' (₹{amount:,.2f} {frequency}) activated!", "success")
    except Exception as e:
        flash(f"Error adding recurring payment: {str(e)}", "danger")

    return redirect(url_for("dashboard") + "#recurring-section")


@app.post("/recurring-payments/<int:item_id>/pay")
def pay_recurring_payment(item_id):
    user = get_current_user()
    uid = user["id"]
    item = db.query("SELECT * FROM recurring_payments WHERE id = %s AND user_id = %s", (item_id, uid), fetchone=True)
    if not item:
        flash("Recurring payment not found", "danger")
        return redirect(url_for("dashboard") + "#recurring-section")

    try:
        amount = Decimal(str(item["amount"]))
        today_dmy = date.today().strftime("%d-%m-%Y")

        # 1. Log transaction in ledger
        db.query(
            """INSERT INTO transactions (user_id, description, category, amount, transaction_type, transaction_date, notes)
               VALUES (%s, %s, %s, %s, 'expense', %s, %s)""",
            (uid, f"Recurring: {item['title']}", item["category"], amount, today_dmy, f"Auto-renewed via {item['payment_method']}"),
            commit=True,
        )

        # 2. Spare change auto-roundup into Piggy Bank Vault
        if item.get("auto_roundup") == 1:
            raw_amt = float(amount)
            ru = math.ceil(raw_amt / 10.0) * 10 - raw_amt
            if ru == 0:
                ru = 10.0
            roundup_dec = Decimal(str(round(ru, 2)))
            db.query(
                """INSERT INTO piggy_bank (user_id, action_type, amount, description, action_date)
                   VALUES (%s, 'roundup', %s, %s, %s)""",
                (uid, roundup_dec, f"Auto Round-up: {item['title']}", today_dmy),
                commit=True,
            )

        # 3. Advance next due date according to frequency
        new_due_date = finance_engine.advance_due_date(item["next_due_date"], item.get("frequency", "Monthly"))
        db.query(
            "UPDATE recurring_payments SET next_due_date = %s WHERE id = %s AND user_id = %s",
            (new_due_date, item_id, uid),
            commit=True,
        )

        flash(f"⚡ Paid & logged ₹{amount:,.2f} for '{item['title']}'! Next renewal due on {new_due_date}.", "success")
    except Exception as e:
        flash(f"Error processing payment renewal: {str(e)}", "danger")

    return redirect(url_for("dashboard") + "#recurring-section")


@app.post("/recurring-payments/<int:item_id>/toggle")
def toggle_recurring_payment(item_id):
    user = get_current_user()
    uid = user["id"]
    item = db.query("SELECT * FROM recurring_payments WHERE id = %s AND user_id = %s", (item_id, uid), fetchone=True)
    if item:
        new_status = "Paused" if item.get("status") == "Active" else "Active"
        db.query(
            "UPDATE recurring_payments SET status = %s WHERE id = %s AND user_id = %s",
            (new_status, item_id, uid),
            commit=True,
        )
        flash(f"Recurring payment '{item['title']}' is now {new_status}.", "info")
    return redirect(url_for("dashboard") + "#recurring-section")


@app.post("/recurring-payments/<int:item_id>/delete")
def delete_recurring_payment(item_id):
    user = get_current_user()
    uid = user["id"]
    db.query("DELETE FROM recurring_payments WHERE id = %s AND user_id = %s", (item_id, uid), commit=True)
    flash("Recurring payment record removed.", "info")
    return redirect(url_for("dashboard") + "#recurring-section")


@app.post("/recurring-payments/quick-add")
def quick_add_recurring_payment():
    user = get_current_user()
    uid = user["id"]
    preset = request.form.get("preset", "").lower().strip()
    today = date.today()

    presets_map = {
        "metro": ("Namma Metro Smartcard Auto-Recharge", "Transport", Decimal("800.00"), "Monthly", "UPI / SmartCard", 5, "Purple & Green Line Daily Commute"),
        "bus": ("Campus & City Bus Pass", "Transport", Decimal("450.00"), "Monthly", "Cash / Counter", 10, "Route 42A Student Pass"),
        "5g": ("Jio Student 5G Unlimited Pack", "Bills", Decimal("299.00"), "Monthly", "UPI / Auto-Debit", 15, "2GB/Day + Unlimited 5G Data"),
        "mess": ("Hostel Mess Dining Dues", "Food", Decimal("3200.00"), "Monthly", "NetBanking / UPI", 3, "Hostel Block-B Mess Subscription"),
        "spotify": ("Spotify Premium Student", "Entertainment", Decimal("69.00"), "Monthly", "UPI / Auto-Debit", 20, "Verified Student Discount Plan"),
    }

    if preset in presets_map:
        title, cat, amt, freq, pmethod, days_ahead, notes = presets_map[preset]
        due_dmy = (today + timedelta(days=days_ahead)).strftime("%d-%m-%Y")
        db.query(
            """INSERT INTO recurring_payments (user_id, title, category, amount, frequency, payment_method, next_due_date, status, auto_roundup, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active', 1, %s)""",
            (uid, title, cat, amt, freq, pmethod, due_dmy, notes),
            commit=True,
        )
        flash(f"🚀 Quick-added '{title}' (₹{amt:,.2f}/mo) to recurring commitments!", "success")
    else:
        flash("Unknown preset selected.", "warning")

    return redirect(url_for("dashboard") + "#recurring-section")


# =====================================================================
# PAYMENT GATEWAY & LIVE CATEGORY SELECTION ENGINE (₹ INR)
# =====================================================================

@app.route("/pay")
@app.route("/payment-gateway")
def payment_gateway():
    user = get_current_user()
    uid = user["id"]
    today_dmy = date.today().strftime("%d-%m-%Y")

    # Fetch categories and budget info
    budgets = db.query("SELECT * FROM budgets WHERE user_id = %s", (uid,))
    budget_map = {b["category"]: float(b["monthly_limit"]) for b in budgets}

    # Fetch current spending by category
    spent_rows = db.query(
        """SELECT category, COALESCE(SUM(amount), 0) AS total_spent
           FROM transactions
           WHERE user_id = %s AND transaction_type = 'expense'
           GROUP BY category""",
        (uid,)
    )
    spent_map = {r["category"]: float(r["total_spent"]) for r in spent_rows}

    categories_data = []
    for c in CATEGORIES:
        cat_name = c["name"]
        limit = budget_map.get(cat_name, 0.0)
        spent = spent_map.get(cat_name, 0.0)
        remaining = max(0.0, limit - spent) if limit > 0 else 0.0
        pct = min(100.0, round((spent / limit) * 100, 1)) if limit > 0 else 0.0
        categories_data.append({
            "name": cat_name,
            "icon": c["icon"],
            "color": c["color"],
            "monthly_limit": limit,
            "current_spent": spent,
            "remaining": remaining,
            "spent_pct": pct,
        })

    # Recent transactions
    recent_txs = db.query(
        "SELECT * FROM transactions WHERE user_id = %s ORDER BY id DESC LIMIT 5",
        (uid,)
    )

    # Telemetry snapshot for runway impact
    incomes = db.query("SELECT * FROM transactions WHERE user_id = %s AND transaction_type = 'income'", (uid,))
    expenses = db.query("SELECT * FROM transactions WHERE user_id = %s AND transaction_type = 'expense'", (uid,))
    base_income = float(finance_engine.to_decimal(user.get("monthly_income", 0)))
    total_income = base_income + sum(float(finance_engine.to_decimal(t["amount"])) for t in incomes)
    total_expenses = sum(float(finance_engine.to_decimal(t["amount"])) for t in expenses)
    piggy_balance, _ = get_piggy_balance(uid)
    cockpit = finance_engine.calculate_daily_cockpit(total_income, total_expenses, float(piggy_balance))

    return render_template(
        "payment_gateway.html",
        user=user,
        today_dmy=today_dmy,
        categories=categories_data,
        category_map=CATEGORY_MAP,
        recent_txs=recent_txs,
        cockpit=cockpit,
    )


@app.get("/api/pay/check-budget")
def api_check_budget():
    user = get_current_user()
    uid = user["id"]
    category = request.args.get("category", "").strip()
    try:
        amount = float(request.args.get("amount", 0.0))
    except (ValueError, TypeError):
        amount = 0.0

    b_info = db.query(
        """SELECT b.monthly_limit, COALESCE(SUM(t.amount), 0) AS current_spent
           FROM budgets b LEFT JOIN transactions t
             ON b.user_id = t.user_id AND b.category = t.category AND t.transaction_type = 'expense'
           WHERE b.user_id = %s AND b.category = %s
           GROUP BY b.monthly_limit""",
        (uid, category),
        fetchone=True,
    )

    if not b_info:
        return jsonify({
            "has_budget": False,
            "category": category,
            "limit": 0.0,
            "spent": 0.0,
            "remaining": 0.0,
            "new_total": amount,
            "warning": False,
            "warning_message": "",
        })

    limit = float(b_info["monthly_limit"])
    spent = float(b_info["current_spent"])
    new_total = spent + amount
    will_cross = (new_total > limit) if limit > 0 else False

    return jsonify({
        "has_budget": True,
        "category": category,
        "limit": limit,
        "spent": spent,
        "remaining": max(0.0, limit - spent),
        "new_total": new_total,
        "warning": will_cross,
        "warning_message": "you are about to cross your monthly limit for this catagory!" if will_cross else "",
        "overage": max(0.0, new_total - limit) if will_cross else 0.0,
    })


@app.post("/api/pay/process")
def api_pay_process():
    user = get_current_user()
    uid = user["id"]
    data = request.get_json() or {}

    merchant = (data.get("merchant") or data.get("description") or "Campus Expense").strip()
    category = (data.get("category") or "Other").strip()
    payment_method = (data.get("payment_method") or "UPI").strip()
    auto_roundup = bool(data.get("auto_roundup", True))
    raw_date = (data.get("transaction_date") or "").strip()
    today_dmy = finance_engine.format_dmy(raw_date) if raw_date else date.today().strftime("%d-%m-%Y")

    try:
        amount = Decimal(str(data.get("amount", 0)))
        if amount <= 0:
            return jsonify({"success": False, "error": "Amount must be greater than ₹0"}), 400
    except Exception:
        return jsonify({"success": False, "error": "Invalid amount provided"}), 400

    if category not in CATEGORY_NAMES:
        category = "Other"

    # 1. Budget Guardrail Inspection
    b_info = db.query(
        """SELECT b.monthly_limit, COALESCE(SUM(t.amount), 0) AS current_spent
           FROM budgets b LEFT JOIN transactions t
             ON b.user_id = t.user_id AND b.category = t.category AND t.transaction_type = 'expense'
           WHERE b.user_id = %s AND b.category = %s
           GROUP BY b.monthly_limit""",
        (uid, category),
        fetchone=True,
    )
    budget_warning = False
    warning_msg = ""
    limit_val = 0.0
    spent_val = 0.0
    if b_info:
        limit_val = float(b_info["monthly_limit"])
        spent_val = float(b_info["current_spent"])
        if limit_val > 0 and (spent_val + float(amount)) > limit_val:
            budget_warning = True
            warning_msg = "you are about to cross your monthly limit for this catagory!"

    # 2. Insert into transactions table (DO NOT DECLINE TRANSACTION)
    txn_id = f"TXN-IN-{date.today().strftime('%Y%m%d')}-{int(datetime.now().timestamp() % 100000):05d}"
    notes = f"Gateway Ref: {txn_id} | Paid via {payment_method}"
    db.query(
        """INSERT INTO transactions (user_id, description, category, amount, transaction_type, transaction_date, notes)
           VALUES (%s, %s, %s, %s, 'expense', %s, %s)""",
        (uid, merchant, category, amount, today_dmy, notes),
        commit=True,
    )

    # 3. Process Auto Spare-Change Roundup into Piggy Bank
    roundup_amt = Decimal("0.00")
    if auto_roundup:
        raw_amt = float(amount)
        ru = math.ceil(raw_amt / 10.0) * 10 - raw_amt
        if ru == 0:
            ru = 10.0
        roundup_amt = Decimal(str(round(ru, 2)))
        db.query(
            """INSERT INTO piggy_bank (user_id, action_type, amount, description, action_date)
               VALUES (%s, 'roundup', %s, %s, %s)""",
            (uid, roundup_amt, f"Gateway Round-up: {merchant} (₹{float(amount):.2f})", today_dmy),
            commit=True,
        )

    # 4. Compute updated runway telemetry
    incomes = db.query("SELECT * FROM transactions WHERE user_id = %s AND transaction_type = 'income'", (uid,))
    expenses = db.query("SELECT * FROM transactions WHERE user_id = %s AND transaction_type = 'expense'", (uid,))
    base_income = float(finance_engine.to_decimal(user.get("monthly_income", 0)))
    total_income = base_income + sum(float(finance_engine.to_decimal(t["amount"])) for t in incomes)
    total_expenses = sum(float(finance_engine.to_decimal(t["amount"])) for t in expenses)
    piggy_balance, _ = get_piggy_balance(uid)
    cockpit = finance_engine.calculate_daily_cockpit(total_income, total_expenses, float(piggy_balance))

    return jsonify({
        "success": True,
        "txn_id": txn_id,
        "merchant": merchant,
        "category": category,
        "category_icon": CATEGORY_MAP.get(category, {}).get("icon", "💳"),
        "amount": float(amount),
        "formatted_amount": f"₹{float(amount):,.2f}",
        "payment_method": payment_method,
        "date": today_dmy,
        "auto_roundup": auto_roundup,
        "roundup_saved": float(roundup_amt),
        "budget_warning": budget_warning,
        "warning_message": warning_msg,
        "category_spent": spent_val + float(amount),
        "category_limit": limit_val,
        "runway_days": cockpit.get("runway_days", 0),
        "safe_daily_spend": cockpit.get("safe_daily_spend", 0.0),
    })


@app.post("/budget")
def save_budget():
    user = get_current_user()
    uid = user["id"]
    try:
        category = request.form["category"]
        limit = Decimal(request.form["monthly_limit"])
        if category not in CATEGORY_NAMES or limit <= 0:
            raise ValueError("Invalid category or budget limit.")

        db.query(
            """INSERT INTO budgets (user_id, category, monthly_limit) VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE monthly_limit = VALUES(monthly_limit)""",
            (uid, category, limit),
            commit=True,
        )
        flash(f"Monthly budget for {category} updated to ₹{float(limit):,.2f}.", "success")
    except Exception as e:
        flash(f"Error saving budget: {e}", "error")

    return redirect(url_for("dashboard"))


@app.post("/piggy/deposit")
def piggy_deposit():
    user = get_current_user()
    uid = user["id"]
    try:
        amount = Decimal(request.form["amount"])
        description = request.form.get("description", "Manual Piggy Vault Deposit").strip()
        if amount <= 0:
            raise ValueError("Amount must be greater than ₹0.")

        today_dmy = date.today().strftime("%d-%m-%Y")
        db.query(
            """INSERT INTO piggy_bank (user_id, action_type, amount, description, action_date)
               VALUES (%s, 'deposit', %s, %s, %s)""",
            (uid, amount, description, today_dmy),
            commit=True,
        )
        flash(f"🐷 Oink! You just stashed ₹{float(amount):,.2f} on {today_dmy} in your Digital Piggy Bank!", "success")
    except Exception as e:
        flash(f"Could not deposit: {e}", "error")

    return redirect(url_for("dashboard"))


@app.post("/piggy/withdraw")
def piggy_withdraw():
    user = get_current_user()
    uid = user["id"]
    try:
        amount = Decimal(request.form["amount"])
        reason = request.form.get("reason", "Piggy Bank Withdrawal").strip()
        current_balance, _ = get_piggy_balance(uid)

        if amount <= 0:
            raise ValueError("Amount must be greater than ₹0.")
        if amount > current_balance:
            raise ValueError(f"Insufficient funds in Piggy Bank (₹{float(current_balance):,.2f} available).")

        today_dmy = date.today().strftime("%d-%m-%Y")
        db.query(
            """INSERT INTO piggy_bank (user_id, action_type, amount, description, action_date)
               VALUES (%s, 'withdrawal', %s, %s, %s)""",
            (uid, amount, reason, today_dmy),
            commit=True,
        )
        flash(f"Withdrew ₹{float(amount):,.2f} on {today_dmy} from Piggy Bank for '{reason}'.", "info")
    except Exception as e:
        flash(f"Could not withdraw: {e}", "error")

    return redirect(url_for("dashboard"))


@app.post("/goals")
def add_goal():
    user = get_current_user()
    uid = user["id"]
    try:
        title = request.form["title"].strip()
        target_amount = Decimal(request.form["target_amount"])
        initial_deposit = Decimal(request.form.get("initial_deposit", "0.00") or "0.00")
        raw_date = request.form["target_date"].strip()
        target_date = finance_engine.format_dmy(raw_date)
        icon = request.form.get("icon", "🎯").strip()
        color = request.form.get("color", "indigo").strip()

        if not title or target_amount <= 0 or not target_date:
            raise ValueError("Provide a title, target amount > ₹0, and a target date.")

        today_dmy = date.today().strftime("%d-%m-%Y")
        deduct_from_piggy = request.form.get("source") == "piggy"
        if deduct_from_piggy and initial_deposit > 0:
            piggy_bal, _ = get_piggy_balance(uid)
            if initial_deposit > piggy_bal:
                raise ValueError(f"Not enough in Piggy Bank (₹{float(piggy_bal):,.2f} available).")
            db.query(
                """INSERT INTO piggy_bank (user_id, action_type, amount, description, action_date)
                   VALUES (%s, 'withdrawal', %s, %s, %s)""",
                (uid, initial_deposit, f"Allocated to goal: {title}", today_dmy),
                commit=True,
            )

        db.query(
            """INSERT INTO savings_goals (user_id, title, target_amount, current_amount, target_date, icon, color)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (uid, title, target_amount, initial_deposit, target_date, icon, color),
            commit=True,
        )
        flash(f"Savings Goal '{title}' created with deadline {target_date} & ₹{float(initial_deposit):,.2f} seeded!", "success")
    except Exception as e:
        flash(f"Error creating goal: {e}", "error")

    return redirect(url_for("dashboard"))


@app.post("/goals/<int:goal_id>/contribute")
def contribute_goal(goal_id):
    user = get_current_user()
    uid = user["id"]
    try:
        amount = Decimal(request.form["amount"])
        source = request.form.get("source", "income")
        if amount <= 0:
            raise ValueError("Contribution must be greater than ₹0.")

        goal = db.query("SELECT * FROM savings_goals WHERE id = %s AND user_id = %s", (goal_id, uid), fetchone=True)
        if not goal:
            raise ValueError("Goal not found.")

        today_dmy = date.today().strftime("%d-%m-%Y")
        if source == "piggy":
            piggy_bal, _ = get_piggy_balance(uid)
            if amount > piggy_bal:
                raise ValueError(f"Insufficient funds in Piggy Bank (₹{float(piggy_bal):,.2f} available).")
            db.query(
                """INSERT INTO piggy_bank (user_id, action_type, amount, description, action_date)
                   VALUES (%s, 'withdrawal', %s, %s, %s)""",
                (uid, amount, f"Contributed to goal: {goal['title']}", today_dmy),
                commit=True,
            )

        new_total = Decimal(str(goal["current_amount"])) + amount
        target = Decimal(str(goal["target_amount"]))
        db.query(
            "UPDATE savings_goals SET current_amount = %s WHERE id = %s",
            (new_total, goal_id),
            commit=True,
        )

        if new_total >= target:
            flash(f"🎉 CELEBRATION! You completed your '{goal['title']}' savings goal! 🏆", "success")
        else:
            flash(f"Added ₹{float(amount):,.2f} to '{goal['title']}'! Total saved: ₹{float(new_total):,.2f} / ₹{float(target):,.2f}.", "success")
    except Exception as e:
        flash(f"Error contributing: {e}", "error")

    return redirect(url_for("dashboard"))


@app.post("/goals/<int:goal_id>/delete")
def delete_goal(goal_id):
    user = get_current_user()
    uid = user["id"]
    goal = db.query("SELECT * FROM savings_goals WHERE id = %s AND user_id = %s", (goal_id, uid), fetchone=True)
    if goal:
        saved = Decimal(str(goal["current_amount"]))
        today_dmy = date.today().strftime("%d-%m-%Y")
        if saved > 0:
            db.query(
                """INSERT INTO piggy_bank (user_id, action_type, amount, description, action_date)
                   VALUES (%s, 'deposit', %s, %s, %s)""",
                (uid, saved, f"Refund from cancelled goal: {goal['title']}", today_dmy),
                commit=True,
            )
        db.query("DELETE FROM savings_goals WHERE id = %s AND user_id = %s", (goal_id, uid), commit=True)
        flash(f"Goal '{goal['title']}' deleted. ₹{float(saved):,.2f} returned to your Piggy Bank vault.", "info")
    return redirect(url_for("dashboard"))


@app.post("/profile")
def update_profile():
    user = get_current_user()
    uid = user["id"]
    try:
        name = request.form["name"].strip()
        college = request.form.get("college_name", "Engineering College").strip()
        monthly_income = Decimal(request.form["monthly_income"])
        if not name or monthly_income < 0:
            raise ValueError
        db.query("UPDATE users SET name = %s, college_name = %s, monthly_income = %s WHERE id = %s",
                 (name, college, monthly_income, uid), commit=True)
        flash("Profile, college affiliation, and monthly income updated.", "success")
    except Exception:
        flash("Please enter a valid name and income.", "error")
    return redirect(url_for("dashboard"))


@app.post("/demo-data")
def load_demo():
    db.seed_demo_data()
    flash("✨ SpendWise Demo dataset loaded with realistic student finances & bill splits in DD-MM-YYYY! 🚀", "success")
    return redirect(url_for("dashboard"))


@app.post("/reset")
def reset_account():
    user = get_current_user()
    uid = user["id"]
    db.query("DELETE FROM transactions WHERE user_id = %s", (uid,), commit=True)
    db.query("DELETE FROM budgets WHERE user_id = %s", (uid,), commit=True)
    db.query("DELETE FROM savings_goals WHERE user_id = %s", (uid,), commit=True)
    db.query("DELETE FROM piggy_bank WHERE user_id = %s", (uid,), commit=True)
    db.query("DELETE FROM bill_splits WHERE user_id = %s", (uid,), commit=True)
    db.query("UPDATE users SET name = 'Student', college_name = 'Engineering College', monthly_income = 0, streak_days = 1 WHERE id = %s", (uid,), commit=True)
    flash("Account reset successfully. Your SpendWise platform is ready for fresh data.", "success")
    return redirect(url_for("dashboard"))


@app.get("/export/csv")
def export_csv():
    user = get_current_user()
    uid = user["id"]
    txs = db.query("SELECT * FROM transactions WHERE user_id = %s ORDER BY id DESC", (uid,))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Date (DD-MM-YYYY)", "Type", "Category", "Amount (INR)", "Description", "Notes"])
    for t in txs:
        writer.writerow([
            t["id"],
            finance_engine.format_dmy(t["transaction_date"]),
            t["transaction_type"],
            t["category"],
            f"{float(t['amount']):.2f}",
            t["description"],
            t.get("notes", ""),
        ])

    today_dmy = date.today().strftime("%d-%m-%Y")
    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=spendwise_statement_{today_dmy}.csv"},
    )


@app.get("/export/pdf")
def export_pdf():
    from pdf_generator import generate_pdf_statement
    user = get_current_user()
    uid = user["id"]

    totals = db.query(
        """SELECT
             COALESCE(SUM(CASE WHEN transaction_type = 'income' THEN amount END), 0) AS added_income,
             COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount END), 0) AS expenses
           FROM transactions WHERE user_id = %s""",
        (uid,), fetchone=True,
    )
    base_income = Decimal(str(user["monthly_income"]))
    added_income = Decimal(str(totals["added_income"] or 0))
    total_income = base_income + added_income
    expenses = Decimal(str(totals["expenses"] or 0))

    piggy_balance, _ = get_piggy_balance(uid)

    budgets = db.query(
        """SELECT b.id, b.category, b.monthly_limit, COALESCE(SUM(t.amount), 0) AS spent
           FROM budgets b LEFT JOIN transactions t
             ON b.user_id = t.user_id AND b.category = t.category AND t.transaction_type = 'expense'
           WHERE b.user_id = %s GROUP BY b.id, b.category, b.monthly_limit""",
        (uid,),
    )
    for b in budgets:
        b["monthly_limit"] = Decimal(str(b["monthly_limit"]))
        b["spent"] = Decimal(str(b["spent"]))

    goals_raw = db.query("SELECT * FROM savings_goals WHERE user_id = %s", (uid,))
    total_saved_in_goals = sum(Decimal(str(g["current_amount"])) for g in goals_raw)
    total_liquid_savings = piggy_balance + total_saved_in_goals

    category_totals = db.query(
        """SELECT category, SUM(amount) AS amount FROM transactions
           WHERE user_id = %s AND transaction_type = 'expense'
           GROUP BY category ORDER BY amount DESC""",
        (uid,),
    )

    health = finance_engine.calculate_financial_health_score(
        income=total_income,
        expenses=expenses,
        budgets_data=budgets,
        liquid_savings=total_liquid_savings,
        category_breakdown=category_totals,
    )

    cockpit = finance_engine.calculate_daily_cockpit(
        income=total_income,
        expenses=expenses,
        liquid_savings=total_liquid_savings,
        score=health["score"],
    )

    txs = db.query("SELECT * FROM transactions WHERE user_id = %s ORDER BY id DESC", (uid,))
    for t in txs:
        t["formatted_date"] = finance_engine.format_dmy(t.get("transaction_date"))

    bill_splits = db.query("SELECT * FROM bill_splits WHERE user_id = %s ORDER BY id DESC", (uid,))
    for s in bill_splits:
        s["formatted_date"] = finance_engine.format_dmy(s.get("created_date"))

    pdf_bytes = generate_pdf_statement(user, txs, totals, piggy_balance, health, cockpit, bill_splits)

    today_dmy = date.today().strftime("%d-%m-%Y")
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename=spendwise_statement_{today_dmy}.pdf"},
    )


@app.get("/api/chart-data")
def chart_data():
    user = get_current_user()
    uid = user["id"]

    category_totals = db.query(
        """SELECT category, SUM(amount) AS amount FROM transactions
           WHERE user_id = %s AND transaction_type = 'expense'
           GROUP BY category ORDER BY amount DESC""",
        (uid,),
    )
    cat_labels = [c["category"] for c in category_totals]
    cat_data = [float(c["amount"]) for c in category_totals]
    cat_colors = [CATEGORY_MAP.get(c["category"], {}).get("color", "#6b7280") for c in category_totals]

    today = date.today()
    month_labels = []
    income_data = []
    expense_data = []

    for i in range(5, -1, -1):
        dt = today.replace(day=1) - timedelta(days=i * 30)
        # Format month label as MM-YYYY
        m_label = dt.strftime("%b %Y")
        month_labels.append(m_label)

        # Match transactions using date strings
        m_pattern_dmy = f"%-{dt.strftime('%m-%Y')}"
        m_pattern_iso = f"{dt.strftime('%Y-%m')}%"

        inc_row = db.query(
            """SELECT COALESCE(SUM(amount), 0) AS amt FROM transactions
               WHERE user_id = %s AND transaction_type = 'income'
                 AND (transaction_date LIKE %s OR transaction_date LIKE %s)""",
            (uid, m_pattern_dmy, m_pattern_iso), fetchone=True,
        )
        exp_row = db.query(
            """SELECT COALESCE(SUM(amount), 0) AS amt FROM transactions
               WHERE user_id = %s AND transaction_type = 'expense'
                 AND (transaction_date LIKE %s OR transaction_date LIKE %s)""",
            (uid, m_pattern_dmy, m_pattern_iso), fetchone=True,
        )
        base = float(user["monthly_income"])
        income_data.append(round(base + float(inc_row["amt"] if inc_row else 0), 2))
        expense_data.append(round(float(exp_row["amt"] if exp_row else 0), 2))

    budgets = db.query(
        """SELECT b.category, b.monthly_limit, COALESCE(SUM(t.amount), 0) AS spent
           FROM budgets b LEFT JOIN transactions t
             ON b.user_id = t.user_id AND b.category = t.category AND t.transaction_type = 'expense'
           WHERE b.user_id = %s GROUP BY b.id, b.category, b.monthly_limit""",
        (uid,),
    )
    b_labels = [b["category"] for b in budgets]
    b_limits = [float(b["monthly_limit"]) for b in budgets]
    b_spents = [float(b["spent"]) for b in budgets]

    return jsonify({
        "categories": {
            "labels": cat_labels,
            "data": cat_data,
            "colors": cat_colors,
        },
        "cashflow": {
            "labels": month_labels,
            "income": income_data,
            "expenses": expense_data,
        },
        "budgets": {
            "labels": b_labels,
            "limits": b_limits,
            "spents": b_spents,
        },
    })


@app.route("/chat")
def chat():
    user = get_current_user()
    uid = user["id"]

    totals = db.query(
        """SELECT
             COALESCE(SUM(CASE WHEN transaction_type = 'income' THEN amount END), 0) AS added_income,
             COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount END), 0) AS expenses
           FROM transactions WHERE user_id = %s""",
        (uid,), fetchone=True,
    )
    base_income = Decimal(str(user["monthly_income"]))
    added_income = Decimal(str(totals["added_income"] or 0))
    total_income = base_income + added_income
    expenses = Decimal(str(totals["expenses"] or 0))
    net_balance = total_income - expenses

    piggy_balance, total_roundups = get_piggy_balance(uid)

    budgets = db.query(
        """SELECT b.id, b.category, b.monthly_limit, COALESCE(SUM(t.amount), 0) AS spent
           FROM budgets b LEFT JOIN transactions t
             ON b.user_id = t.user_id AND b.category = t.category AND t.transaction_type = 'expense'
           WHERE b.user_id = %s GROUP BY b.id, b.category, b.monthly_limit""",
        (uid,),
    )
    for b in budgets:
        limit = Decimal(str(b["monthly_limit"]))
        spent = Decimal(str(b["spent"]))
        b["limit_dec"] = limit
        b["spent_dec"] = spent
        b["percent"] = min(100, round(float((spent / limit) * 100))) if limit > 0 else 0
        b["overrun"] = spent > limit
        b["remaining"] = max(Decimal("0"), limit - spent)
        b["meta"] = CATEGORY_MAP.get(b["category"], {"icon": "🏷️", "color": "#6b7280"})

    goals_raw = db.query("SELECT * FROM savings_goals WHERE user_id = %s ORDER BY id ASC", (uid,))
    total_saved_in_goals = sum(Decimal(str(g["current_amount"])) for g in goals_raw)
    total_liquid_savings = piggy_balance + total_saved_in_goals

    all_txs = db.query("SELECT * FROM transactions WHERE user_id = %s ORDER BY id DESC", (uid,))
    for tx in all_txs:
        tx["formatted_date"] = finance_engine.format_dmy(tx.get("transaction_date"))
        tx["meta"] = CATEGORY_MAP.get(tx["category"], {"icon": "🏷️", "color": "#6b7280"})

    cockpit = finance_engine.calculate_daily_cockpit(
        income=total_income,
        expenses=expenses,
        liquid_savings=total_liquid_savings,
        score=80
    )
    comparison = finance_engine.compare_expenses(all_txs, user)
    trajectory = finance_engine.predict_financial_trajectory(user, total_income, expenses, total_liquid_savings, all_txs)

    history = db.get_chatbot_history(uid, limit=60)
    for h in history:
        if h.get("data_card"):
            try:
                h["parsed_data_card"] = json.loads(h["data_card"])
            except Exception:
                h["parsed_data_card"] = None
        else:
            h["parsed_data_card"] = None

        if h.get("actions_json"):
            try:
                h["parsed_actions"] = json.loads(h["actions_json"])
            except Exception:
                h["parsed_actions"] = []
        else:
            h["parsed_actions"] = []

    mem_dict, mem_list = db.get_chatbot_memory(uid)
    solved_count = mem_dict.get("queries_solved_count", "12")

    return render_template(
        "chat.html",
        user=user,
        categories=CATEGORIES,
        total_income=total_income,
        expenses=expenses,
        net_balance=net_balance,
        piggy_balance=piggy_balance,
        cockpit=cockpit,
        comparison=comparison,
        trajectory=trajectory,
        history=history,
        memory_dict=mem_dict,
        memory_list=mem_list,
        solved_count=solved_count,
        gemini_status=gemini_service.get_gemini_status(),
        today_dmy=date.today().strftime("%d-%m-%Y"),
    )


@app.route("/intelligence")
def intelligence():
    return redirect(url_for("chat"))


@app.post("/api/chat/query")
def api_chat_query():
    user = get_current_user()
    uid = user["id"]
    data = request.get_json() or {}
    query_text = (data.get("query") or "").strip()

    if not query_text:
        return jsonify({"error": "Query cannot be empty"}), 400

    all_txs = db.query("SELECT * FROM transactions WHERE user_id = %s ORDER BY id DESC", (uid,))
    budgets = db.query("SELECT * FROM budgets WHERE user_id = %s", (uid,))
    goals = db.query("SELECT * FROM savings_goals WHERE user_id = %s", (uid,))
    recurring = db.query("SELECT * FROM recurring_payments WHERE user_id = %s", (uid,))
    piggy_balance, _ = get_piggy_balance(uid)
    mem_dict, _ = db.get_chatbot_memory(uid)

    # Route through Google Gemini API (with live telemetry grounding and deterministic SFI fallback)
    result = gemini_service.query_gemini_assistant(
        query_text=query_text,
        user=user,
        all_txs=all_txs,
        budgets=budgets,
        goals=goals,
        piggy_balance=piggy_balance,
        current_memory=mem_dict,
        recurring=recurring,
    )

    learned = result.get("learned_updates", {})
    for m_key, (m_val, conf) in learned.items():
        db.update_chatbot_memory(uid, m_key, m_val, conf)
        mem_dict[m_key] = str(m_val)

    db.save_chatbot_interaction(
        user_id=uid,
        query_text=query_text,
        response_text=result["answer"],
        intent=result.get("intent", "general"),
        data_card=result.get("data_card"),
        actions_json=result.get("suggested_actions"),
        is_solved=1
    )

    return jsonify({
        "answer": result["answer"],
        "intent": result.get("intent", "general"),
        "data_card": result.get("data_card"),
        "suggested_actions": result.get("suggested_actions", []),
        "learning_badge": result.get("learning_badge"),
        "is_gemini": result.get("is_gemini", False),
        "provider": result.get("provider", "Gemini AI"),
        "memory": mem_dict,
        "solved_count": mem_dict.get("queries_solved_count", "13")
    })


@app.get("/api/chat/gemini-status")
def api_chat_gemini_status():
    return jsonify(gemini_service.get_gemini_status())


@app.post("/api/chat/set-gemini-key")
def api_chat_set_gemini_key():
    data = request.get_json() or {}
    key = data.get("api_key", "").strip()
    if not key:
        gemini_service.set_gemini_api_key("")
        return jsonify({
            "success": True,
            "message": "Gemini API Key cleared. Now using built-in autonomous engine.",
            "status": gemini_service.get_gemini_status()
        })

    success = gemini_service.set_gemini_api_key(key)
    return jsonify({
        "success": success,
        "message": "✨ Google Gemini API Key configured and active!" if success else "Failed to set Gemini API key.",
        "status": gemini_service.get_gemini_status()
    })


@app.get("/api/chat/memory")
def api_chat_memory():
    user = get_current_user()
    uid = user["id"]
    mem_dict, mem_list = db.get_chatbot_memory(uid)
    return jsonify({
        "memory_dict": mem_dict,
        "memory_list": [dict(m) for m in mem_list],
        "solved_count": mem_dict.get("queries_solved_count", "12")
    })


@app.post("/api/chat/clear-memory")
def api_chat_clear_memory():
    user = get_current_user()
    uid = user["id"]
    db.clear_chatbot_memory(uid)
    mem_dict, mem_list = db.get_chatbot_memory(uid)
    return jsonify({
        "success": True,
        "message": "AI Memory Vault reset to fresh baseline.",
        "memory_dict": mem_dict,
        "memory_list": [dict(m) for m in mem_list],
        "solved_count": "0"
    })


@app.post("/api/coach/query")
def api_coach_query():
    return api_chat_query()



@app.post("/api/sfi/parse-quick-add")
def api_sfi_parse():
    data = request.get_json() or {}
    text = data.get("text", "")
    parsed = finance_engine.parse_nlp_expense(text)
    return jsonify({
        "amount": float(parsed["amount"]),
        "category": parsed["category"],
        "description": parsed["description"],
        "suggested_roundup": float(parsed["suggested_roundup"])
    })


@app.post("/sfi/quick-add")
def sfi_quick_add():
    user = get_current_user()
    uid = user["id"]
    raw_text = request.form.get("nlp_text", "").strip()
    
    parsed = finance_engine.parse_nlp_expense(raw_text)
    amount = parsed["amount"]
    category = parsed["category"]
    description = parsed["description"] or "Quick Student Expense"
    today_dmy = date.today().strftime("%d-%m-%Y")
    
    if amount <= 0:
        flash("Could not detect a valid amount. Please specify an amount like 'Paid 150 for lunch'", "warning")
        return redirect(url_for("intelligence"))

    db.query(
        """INSERT INTO transactions (user_id, description, category, amount, transaction_type, transaction_date, notes)
           VALUES (%s, %s, %s, %s, 'expense', %s, %s)""",
        (uid, description, category, amount, today_dmy, "Logged via SFI Natural Language Assistant"),
        commit=True,
    )

    if request.form.get("auto_roundup") == "1":
        roundup = parsed["suggested_roundup"]
        if roundup > 0:
            db.query(
                """INSERT INTO piggy_bank (user_id, action_type, amount, description, action_date)
                   VALUES (%s, 'roundup', %s, %s, %s)""",
                (uid, roundup, f"SFI Auto Round-up: {description}", today_dmy),
                commit=True,
            )
            flash(f"Logged ₹{float(amount):,.2f} to {category} + stashed ₹{float(roundup):,.2f} spare change into Piggy Vault! 🐷", "success")
        else:
            flash(f"Logged ₹{float(amount):,.2f} to {category} successfully!", "success")
    else:
        flash(f"Logged ₹{float(amount):,.2f} to {category} successfully!", "success")

    return redirect(url_for("chat"))


@app.post("/sfi/achieve/<int:rec_id>")
def sfi_achieve(rec_id):
    user = get_current_user()
    uid = user["id"]
    today_dmy = date.today().strftime("%d-%m-%Y")

    rec = db.query("SELECT * FROM sfi_recommendations WHERE id = %s AND user_id = %s", (rec_id, uid), fetchone=True)
    if rec:
        db.query("UPDATE sfi_recommendations SET status = 'achieved', achieved_at = %s WHERE id = %s", (today_dmy, rec_id), commit=True)
        savings_amt = Decimal(str(rec["monthly_savings"]))
        db.query(
            """INSERT INTO sfi_savings_ledger (user_id, title, amount_saved, source, achieved_date)
               VALUES (%s, %s, %s, 'SFI Recommendation Execution', %s)""",
            (uid, rec["title"], savings_amt, today_dmy),
            commit=True,
        )
        flash(f"🎉 Achievement Unlocked! Marked '{rec['title']}' as completed. ₹{float(savings_amt):,.0f}/mo added to your verified savings ledger!", "success")
    return redirect(url_for("chat"))


@app.post("/sfi/mess-skip")
def sfi_mess_skip():
    user = get_current_user()
    uid = user["id"]
    today_dmy = date.today().strftime("%d-%m-%Y")
    meal_type = request.form.get("meal_type", "Dinner")
    rebate_amt = Decimal(request.form.get("rebate_amount", "115.00"))

    db.query(
        """INSERT INTO sfi_savings_ledger (user_id, title, amount_saved, source, achieved_date)
           VALUES (%s, %s, %s, 'Mess Skip Rebate Credit', %s)""",
        (uid, f"Hostel Mess {meal_type} Skip Rebate", rebate_amt, today_dmy),
        commit=True,
    )
    flash(f"🍛 Mess skip logged! ₹{float(rebate_amt):,.2f} rebate credited to your Student Intelligence savings tracker.", "success")
    return redirect(url_for("chat"))




if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    use_reloader = os.environ.get("USE_RELOADER", "0") == "1"
    app.run(debug=True, use_reloader=use_reloader, port=port)

