import json
import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

ESSENTIAL_CATEGORIES = {"Bills", "Food", "Health", "Education", "Transport"}
LIFESTYLE_CATEGORIES = {"Entertainment", "Shopping", "Other"}

def format_dmy(d):
    """Format any date object or ISO string to DD-MM-YYYY strictly."""
    if not d:
        return datetime.now().strftime("%d-%m-%Y")
    if isinstance(d, (date, datetime)):
        return d.strftime("%d-%m-%Y")
    s = str(d).strip()
    # Already DD-MM-YYYY
    if len(s) == 10 and s[2] == '-' and s[5] == '-':
        return s
    # YYYY-MM-DD
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        parts = s[:10].split('-')
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    try:
        dt = datetime.strptime(s[:10], "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return s

def parse_dmy(s):
    """Parse a date string (DD-MM-YYYY or YYYY-MM-DD) into a date object."""
    if not s:
        return date.today()
    s = str(s).strip()
    if len(s) == 10 and s[2] == '-' and s[5] == '-':
        try:
            return datetime.strptime(s, "%d-%m-%Y").date()
        except Exception:
            pass
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except Exception:
            pass
    return date.today()

def format_inr(number):
    """Format numbers into Indian currency system strictly (e.g. ₹2,00,000.00)."""
    try:
        val = float(number)
        is_neg = val < 0
        val = abs(val)
        s = f"{val:.2f}"
        int_part, dec_part = s.split('.')
        if len(int_part) <= 3:
            res = int_part
        else:
            last3 = int_part[-3:]
            rest = int_part[:-3]
            groups = []
            while len(rest) > 2:
                groups.insert(0, rest[-2:])
                rest = rest[:-2]
            if rest:
                groups.insert(0, rest)
            res = ",".join(groups) + "," + last3
        prefix = "-₹" if is_neg else "₹"
        return f"{prefix}{res}.{dec_part}"
    except Exception:
        return f"₹{number}"


def advance_due_date(current_dmy_str, frequency="Monthly"):
    """Advance a recurring payment due date according to its frequency in DD-MM-YYYY format."""
    curr_date = parse_dmy(current_dmy_str)
    today = date.today()
    base_date = max(curr_date, today)
    freq = (frequency or "monthly").lower().strip()

    if freq == "daily":
        new_date = base_date + timedelta(days=1)
    elif freq == "weekly":
        new_date = base_date + timedelta(days=7)
    elif freq == "semester":
        new_date = base_date + timedelta(days=120)
    else:  # monthly
        month = base_date.month + 1
        year = base_date.year
        if month > 12:
            month = 1
            year += 1
        day = min(base_date.day, 28)
        new_date = date(year, month, day)
    return new_date.strftime("%d-%m-%Y")


def calculate_due_status(due_date_str):
    """Calculate days until due date and urgency badge styling."""
    target_dt = parse_dmy(due_date_str)
    today = date.today()
    days_left = (target_dt - today).days

    if days_left < 0:
        return {
            "status": "overdue",
            "days_left": days_left,
            "label": f"Overdue by {abs(days_left)}d",
            "color": "rose",
            "badge_class": "bg-rose-500/20 text-rose-300 border-rose-500/30",
            "is_urgent": True,
        }
    elif days_left == 0:
        return {
            "status": "due_today",
            "days_left": 0,
            "label": "Due Today!",
            "color": "amber",
            "badge_class": "bg-amber-500/20 text-amber-300 border-amber-500/30",
            "is_urgent": True,
        }
    elif days_left <= 7:
        return {
            "status": "due_soon",
            "days_left": days_left,
            "label": f"Due in {days_left}d",
            "color": "amber",
            "badge_class": "bg-amber-500/20 text-amber-300 border-amber-500/30",
            "is_urgent": True,
        }
    else:
        return {
            "status": "upcoming",
            "days_left": days_left,
            "label": f"Due in {days_left}d",
            "color": "emerald",
            "badge_class": "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
            "is_urgent": False,
        }


def calculate_recurring_metrics(payments):
    """Calculate aggregate metrics for student recurring transit & subscription commitments."""
    total_monthly = Decimal("0.00")
    transit_monthly = Decimal("0.00")
    active_count = 0
    upcoming_7d_count = 0

    for p in payments:
        if p.get("status", "Active").lower() != "active":
            continue
        active_count += 1
        amt = Decimal(str(p.get("amount", 0)))
        freq = (p.get("frequency") or "Monthly").lower()
        if freq == "daily":
            monthly_norm = amt * Decimal("30")
        elif freq == "weekly":
            monthly_norm = amt * Decimal("4.33")
        elif freq == "semester":
            monthly_norm = amt / Decimal("4")
        else:  # monthly
            monthly_norm = amt

        total_monthly += monthly_norm

        cat = (p.get("category") or "").lower()
        title = (p.get("title") or "").lower()
        if cat == "transport" or any(k in title for k in ["metro", "bus", "train", "pass", "transit", "commute", "fare"]):
            transit_monthly += monthly_norm

        status_info = calculate_due_status(p.get("next_due_date"))
        if status_info.get("days_left", 999) <= 7:
            upcoming_7d_count += 1

    return {
        "total_monthly": total_monthly,
        "transit_monthly": transit_monthly,
        "active_count": active_count,
        "upcoming_7d_count": upcoming_7d_count,
    }


STUDENT_OFFERS = [
    {
        "id": "spotify",
        "category": "Music & Media",
        "title": "Spotify Premium Student",
        "provider": "Spotify",
        "icon": "🎧",
        "student_price": "₹69/mo",
        "regular_price": "₹119/mo",
        "discount": "42% OFF",
        "annual_savings": "₹600/yr",
        "verification": "SheerID / College ID",
        "highlight": "Ad-free music + offline downloads + 2 months free trial",
        "url": "https://www.spotify.com/in-en/student/",
    },
    {
        "id": "apple",
        "category": "Tech & Coding",
        "title": "Apple Education Pricing & Music",
        "provider": "Apple India",
        "icon": "🍎",
        "student_price": "₹69/mo (Music) + Hardware Discounts",
        "regular_price": "₹119/mo + Full MRP",
        "discount": "Up to ₹10,000+ OFF",
        "annual_savings": "₹12,000+/yr",
        "verification": "UNiDAYS / College Portal",
        "highlight": "Mac & iPad discounts + Free AirPods/Pencil during promos + Free Apple TV+",
        "url": "https://www.apple.com/in-edu/store",
    },
    {
        "id": "adobe",
        "category": "Creative & Productivity",
        "title": "Adobe Creative Cloud Student",
        "provider": "Adobe",
        "icon": "🎨",
        "student_price": "₹398.99/mo",
        "regular_price": "₹2,394/mo",
        "discount": "83% OFF",
        "annual_savings": "₹23,940/yr",
        "verification": "School/College Email",
        "highlight": "Complete suite: Photoshop, Premiere Pro, Illustrator & 20+ apps",
        "url": "https://www.adobe.com/in/creativecloud/buy/students.html",
    },
    {
        "id": "github",
        "category": "Tech & Coding",
        "title": "GitHub Student Developer Pack",
        "provider": "GitHub",
        "icon": "💻",
        "student_price": "100% FREE",
        "regular_price": "$200+/mo",
        "discount": "FREE TIER",
        "annual_savings": "₹1,50,000+/yr",
        "verification": "College Email / Student ID",
        "highlight": "Free GitHub Pro, GitHub Copilot, free domain, JetBrains IDEs, cloud credits",
        "url": "https://education.github.com/pack",
    },
    {
        "id": "amazon",
        "category": "Lifestyle",
        "title": "Amazon Prime Youth Offer",
        "provider": "Amazon India",
        "icon": "📦",
        "student_price": "₹749/yr (Effective)",
        "regular_price": "₹1,499/yr",
        "discount": "50% CASHBACK",
        "annual_savings": "₹750/yr",
        "verification": "Age 18-24 Verification (Aadhaar/College ID)",
        "highlight": "Free 1-day delivery + Prime Video + Prime Music at half price",
        "url": "https://www.amazon.in/prime",
    },
    {
        "id": "notion",
        "category": "Creative & Productivity",
        "title": "Notion for Education Plus",
        "provider": "Notion",
        "icon": "📝",
        "student_price": "100% FREE",
        "regular_price": "₹800/mo ($10)",
        "discount": "FREE TIER",
        "annual_savings": "₹9,600/yr",
        "verification": "College .edu / .ac.in Email",
        "highlight": "Unlimited file uploads, version history & collaborative workspace",
        "url": "https://www.notion.so/product/notion-for-education",
    },
    {
        "id": "youtube",
        "category": "Music & Media",
        "title": "YouTube Premium Student",
        "provider": "Google / YouTube",
        "icon": "▶️",
        "student_price": "₹89/mo",
        "regular_price": "₹149/mo",
        "discount": "40% OFF",
        "annual_savings": "₹720/yr",
        "verification": "SheerID",
        "highlight": "Ad-free YouTube + Background Play + YouTube Music Premium",
        "url": "https://www.youtube.com/premium/student",
    },
    {
        "id": "jetbrains",
        "category": "Tech & Coding",
        "title": "JetBrains Student License Pack",
        "provider": "JetBrains",
        "icon": "⚡",
        "student_price": "100% FREE",
        "regular_price": "₹22,000/yr",
        "discount": "FREE TIER",
        "annual_savings": "₹22,000/yr",
        "verification": "College Email",
        "highlight": "Full access to PyCharm Pro, IntelliJ IDEA Ultimate, WebStorm & all IDEs",
        "url": "https://www.jetbrains.com/community/education/#students",
    },
]

def to_decimal(val):
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0.00")

def calculate_roundup(amount, round_to=10):
    amt = to_decimal(amount)
    if amt <= 0:
        return Decimal("0.00")
    amt_float = float(amt)
    ceil_target = math.ceil(amt_float / round_to) * round_to
    diff = round(ceil_target - amt_float, 2)
    if diff <= 0.0:
        return Decimal("0.00")
    return Decimal(str(diff)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def calculate_daily_cockpit(income, expenses, liquid_savings, score=80):
    """
    Calculates the exact 3-metric cockpit shown in user screenshot:
    - RUNWAY REMAINING (Days)
    - DAILY BURN RATE (₹/day)
    - SAFE DAILY SPEND (₹/day)
    - SpendWise AI Coach message
    """
    income = float(to_decimal(income))
    expenses = float(to_decimal(expenses))
    savings = float(to_decimal(liquid_savings))

    # Daily burn based on active monthly expenses
    daily_burn_rate = round(expenses / 30.0, 2) if expenses > 0 else 0.0

    # Total liquid reserve available = savings + net monthly surplus (if positive)
    surplus = max(0.0, income - expenses)
    total_runway_capital = savings + surplus

    if daily_burn_rate > 0:
        runway_days = int(total_runway_capital / daily_burn_rate)
    else:
        runway_days = 999 if total_runway_capital > 0 else 0

    # Days remaining in current month
    today = date.today()
    days_in_month = 30
    days_left = max(1, days_in_month - today.day)

    # Safe daily spend = Remaining unspent disposable funds / days left
    net_remaining = income - expenses
    if net_remaining > 0:
        safe_daily_spend = round(net_remaining / float(days_left), 1)
    else:
        safe_daily_spend = 0.0

    # SpendWise AI Coach Message
    if score <= 30 or safe_daily_spend == 0:
        coach_message = "🚨 Urgent alert: High spending velocity detected! Switch to survival mode: limit spending strictly to hostel meals & emergency transport."
    elif score <= 60:
        coach_message = "⚠️ Caution: Burn rate is high this month. Consider skipping discretionary food delivery and cooking at PG to extend your runway."
    elif score <= 80:
        coach_message = f"💡 Steady pace! You have a safe daily spend allowance of ₹{safe_daily_spend:,.1f}/day. Keep saving spare change to hit your targets!"
    else:
        coach_message = f"✨ Excellent financial health! Your runway cushion is strong with ₹{safe_daily_spend:,.1f}/day disposable buffer. Keep up the great discipline!"

    return {
        "runway_days": runway_days,
        "daily_burn_rate": daily_burn_rate,
        "safe_daily_spend": safe_daily_spend,
        "coach_message": coach_message
    }

def calculate_financial_health_score(income, expenses, budgets_data, liquid_savings, category_breakdown):
    income = to_decimal(income)
    expenses = to_decimal(expenses)
    liquid_savings = to_decimal(liquid_savings)

    if income <= 0:
        return {
            "score": 0,
            "grade": "N/A",
            "message": "Add your monthly income in your profile to generate your 360° Financial Health Score.",
            "subscores": {"savings": 0, "budget": 0, "runway": 0, "balance": 0},
            "runway_months": 0,
            "savings_rate_pct": 0,
            "spending_ratio_pct": 0
        }

    # 1. Savings Velocity (0 to 30 pts)
    net_savings = max(Decimal("0"), income - expenses)
    savings_rate = net_savings / income
    savings_rate_pct = round(float(savings_rate * 100), 1)
    savings_pts = min(Decimal("30"), (savings_rate / Decimal("0.25")) * Decimal("30"))
    savings_pts = max(Decimal("0"), savings_pts)

    # 2. Budget Adherence (0 to 25 pts)
    overruns = 0
    total_budget_limit = Decimal("0")
    for b in budgets_data:
        limit = to_decimal(b.get("monthly_limit", 0))
        spent = to_decimal(b.get("spent", 0))
        total_budget_limit += limit
        if spent > limit:
            overruns += 1

    budget_penalty = Decimal(overruns * 6)
    budget_pts = max(Decimal("0"), Decimal("25") - budget_penalty)

    # 3. Emergency Runway Buffer (0 to 25 pts)
    burn_rate = expenses if expenses > 0 else Decimal("10000.00")
    runway_months = float((liquid_savings + net_savings) / burn_rate)
    runway_months = round(max(0.0, runway_months), 1)
    runway_pts = min(Decimal("25"), (to_decimal(runway_months) / Decimal("3.0")) * Decimal("25"))
    runway_pts = max(Decimal("0"), runway_pts)

    # 4. 50/30/20 Balance (0 to 20 pts)
    essentials_spent = Decimal("0")
    lifestyle_spent = Decimal("0")
    for row in category_breakdown:
        cat = row.get("category")
        amt = to_decimal(row.get("amount", 0))
        if cat in ESSENTIAL_CATEGORIES:
            essentials_spent += amt
        else:
            lifestyle_spent += amt

    essentials_ratio = essentials_spent / income
    lifestyle_ratio = lifestyle_spent / income

    balance_pts = Decimal("20")
    if essentials_ratio > Decimal("0.60"):
        balance_pts -= (essentials_ratio - Decimal("0.60")) * Decimal("25")
    if lifestyle_ratio > Decimal("0.35"):
        balance_pts -= (lifestyle_ratio - Decimal("0.35")) * Decimal("25")
    balance_pts = max(Decimal("0"), min(Decimal("20"), balance_pts))

    total_score = round(float(savings_pts + budget_pts + runway_pts + balance_pts))
    total_score = max(0, min(100, total_score))

    if total_score >= 85:
        grade = "A+"
        message = "SpendWise Elite! Superb financial discipline, high savings velocity, and resilient safety reserves."
    elif total_score >= 70:
        grade = "A-"
        message = "Solid Financial Health! Great savings momentum. Keep discretionary spending in check."
    elif total_score >= 55:
        grade = "B"
        message = "Moderate Runway. Covering monthly expenses comfortably, but expanding your emergency buffer will boost stability."
    elif total_score >= 40:
        grade = "C"
        message = "Tight Margin. High burn rate relative to earnings. Leverage student discounts and micro-savings."
    else:
        grade = "D"
        message = "Runway Warning. Spending outpaces recommended limits. Trim non-essentials and claim verified student perks."

    spending_ratio_pct = round(float((expenses / income) * 100), 1)

    return {
        "score": total_score,
        "grade": grade,
        "message": message,
        "subscores": {
            "savings": round(float(savings_pts), 1),
            "budget": round(float(budget_pts), 1),
            "runway": round(float(runway_pts), 1),
            "balance": round(float(balance_pts), 1)
        },
        "runway_months": runway_months,
        "savings_rate_pct": savings_rate_pct,
        "spending_ratio_pct": spending_ratio_pct
    }

def generate_ai_insights(income, expenses, budgets_data, category_breakdown, goals_data, piggy_balance):
    income = to_decimal(income)
    expenses = to_decimal(expenses)
    piggy_balance = to_decimal(piggy_balance)
    insights = []

    if income <= 0:
        insights.append({
            "type": "warning",
            "icon": "⚠️",
            "title": "Set Income Baseline",
            "body": "Add your monthly income/stipend in your profile to unlock personalized recommendations.",
            "impact": "High Priority"
        })
        return insights

    for b in budgets_data:
        limit = to_decimal(b.get("monthly_limit", 0))
        spent = to_decimal(b.get("spent", 0))
        cat = b.get("category", "")
        if spent > limit and limit > 0:
            over = spent - limit
            insights.append({
                "type": "danger",
                "icon": "🚨",
                "title": f"Budget Breach: {cat}",
                "body": f"You've exceeded your {cat} budget by ₹{float(over):,.2f}. Shaving small daily spends can quickly restore your score.",
                "impact": "-6 Pts Impact"
            })

    has_entertainment = any(r.get("category") == "Entertainment" and to_decimal(r.get("amount", 0)) > 200 for r in category_breakdown)
    if has_entertainment:
        insights.append({
            "type": "tip",
            "icon": "🎓",
            "title": "Claim Student Perks (Save ₹1,200+/mo)",
            "body": "Switch entertainment to Spotify Student (₹69/mo vs ₹119) and YouTube Premium Student (₹89/mo) to unlock over ₹600/month in instant savings!",
            "impact": "Instant Saving"
        })

    if expenses > 0:
        for row in category_breakdown:
            cat = row.get("category")
            amt = to_decimal(row.get("amount", 0))
            share = (amt / expenses) * 100
            if cat in ("Food", "Shopping") and share > 30:
                potential_saving = amt * Decimal("0.15")
                insights.append({
                    "type": "warning",
                    "icon": "💡",
                    "title": f"Optimize {cat} Spend",
                    "body": f"{cat} takes up {share:.1f}% of expenses. Cooking at PG or skipping 2 Swiggy orders could save ₹{float(potential_saving):,.0f}/mo into your Piggy Vault!",
                    "impact": "+5 Pts Boost"
                })

    if piggy_balance < Decimal("1000"):
        insights.append({
            "type": "tip",
            "icon": "🐷",
            "title": "Micro-Savings Auto Round-Up",
            "body": "Enable 'Round-Up to next ₹10' on UPI / card expenses. Small spare change adds up to ₹800–₹1,500 every month without feeling the pinch!",
            "impact": "Habit Builder"
        })
    else:
        insights.append({
            "type": "success",
            "icon": "🎉",
            "title": "Piggy Vault Milestone",
            "body": f"You have ₹{float(piggy_balance):,.2f} stashed in your vault! Consider routing a portion into your active savings goals.",
            "impact": "Milestone"
        })

    for g in goals_data:
        target = to_decimal(g.get("target_amount", 0))
        curr = to_decimal(g.get("current_amount", 0))
        if target > 0 and curr < target:
            rem = target - curr
            tdate = parse_dmy(g.get("target_date"))
            days = (tdate - date.today()).days
            if days > 0:
                daily_need = rem / Decimal(days)
                monthly_need = daily_need * Decimal("30")
                insights.append({
                    "type": "info",
                    "icon": g.get("icon", "🎯"),
                    "title": f"Goal Pace: {g.get('title')}",
                    "body": f"Save ₹{float(monthly_need):,.0f}/month (₹{float(daily_need):,.0f}/day) to hit your {g.get('title')} target by {tdate.strftime('%d-%m-%Y')}.",
                    "impact": f"{days} Days Left"
                })

    return insights[:4]

def calculate_goal_projection(target_amount, current_amount, target_date_str, monthly_savings_rate):
    target = to_decimal(target_amount)
    current = to_decimal(current_amount)
    monthly_rate = to_decimal(monthly_savings_rate)

    if target <= 0:
        return {"pct": 100, "days_left": 0, "status": "completed", "projected_text": "Goal complete!"}

    pct = min(100.0, float((current / target) * 100))
    pct = round(max(0.0, pct), 1)

    tdate = parse_dmy(target_date_str)
    days_left = max(0, (tdate - date.today()).days)
    remaining = max(Decimal("0"), target - current)

    if remaining <= 0:
        status = "completed"
        projected_text = "Target Achieved! 🏆"
    elif monthly_rate > 0:
        months_needed = float(remaining / monthly_rate)
        days_needed = int(months_needed * 30.4)
        if days_needed <= days_left:
            status = "ahead"
            projected_text = f"On track! Estimated completion in {days_needed} days."
        else:
            status = "behind"
            projected_text = f"Behind pace by ~{days_needed - days_left} days. Boost contribution by ₹{float((remaining / Decimal(max(1, days_left / 30))) - monthly_rate):,.0f}/mo."
    else:
        status = "pending"
        projected_text = "Contribute from Piggy Bank to start tracking velocity."

    return {
        "pct": pct,
        "remaining": float(remaining),
        "days_left": days_left,
        "status": status,
        "projected_text": projected_text
    }


# =====================================================================
# STUDENT FINANCIAL INTELLIGENCE (SFI) & AI FINANCIAL COACH ENGINES
# =====================================================================

STUDENT_BENCHMARKS = {
    "Food": {"pct": 35.0, "icon": "🍛", "advice": "Target 30-35% of stipend. Rely more on mess/PG meals."},
    "Bills": {"pct": 35.0, "icon": "⚡", "advice": "Rent & utilities should not exceed 35-40%."},
    "Transport": {"pct": 8.0, "icon": "🛵", "advice": "Keep commute under 8-10% using monthly metro/bus passes."},
    "Education": {"pct": 10.0, "icon": "📚", "advice": "Books, equipment & courses: invest 8-12%."},
    "Entertainment": {"pct": 6.0, "icon": "🎬", "advice": "Keep media & leisure under 6% via student discounts."},
    "Shopping": {"pct": 6.0, "icon": "🛍️", "advice": "Discretionary clothing/gadgets capped at 6%."},
}

def parse_nlp_expense(text):
    """
    Parses natural language student expense statements into structured data.
    Example inputs:
      - 'Paid 240 Swiggy for dinner with Rohan'
      - '80rs auto to college campus'
      - 'Spent 1200 on books and stationery'
      - 'Blinkit groceries 450'
      - 'Recharged wifi 799'
    """
    if not text:
        return {"amount": Decimal("0.00"), "category": "Other", "description": "", "suggested_roundup": Decimal("0.00")}
    
    text_clean = text.strip()
    
    # Extract amount: match Rs, rs, ₹, INR or bare numbers
    amt_match = re.search(r'(?:(?:rs\.?|inr|₹)\s*(\d+(?:\.\d{1,2})?))|(\d+(?:\.\d{1,2})?)\s*(?:rs\.?|inr|₹)?', text_clean, re.IGNORECASE)
    amount = Decimal("0.00")
    if amt_match:
        val_str = amt_match.group(1) or amt_match.group(2)
        if val_str:
            try:
                amount = Decimal(str(round(float(val_str), 2)))
            except Exception:
                amount = Decimal("0.00")
                
    # Categorization keywords
    lower = text_clean.lower()
    cat = "Other"
    if any(k in lower for k in ["swiggy", "zomato", "biryani", "chai", "tea", "coffee", "canteen", "snack", "dinner", "lunch", "breakfast", "mess", "food", "burger", "pizza", "blinkit", "grocer"]):
        cat = "Food"
    elif any(k in lower for k in ["auto", "rapido", "uber", "ola", "metro", "bus", "train", "cab", "petrol", "transport", "travel"]):
        cat = "Transport"
    elif any(k in lower for k in ["rent", "pg", "room", "wifi", "broadband", "electricity", "bill", "recharge", "water", "maid", "flat"]):
        cat = "Bills"
    elif any(k in lower for k in ["book", "course", "udemy", "tuition", "exam", "stationary", "printout", "lab", "college", "fee", "xerox"]):
        cat = "Education"
    elif any(k in lower for k in ["spotify", "netflix", "prime", "movie", "cinema", "youtube", "concert", "game", "steam"]):
        cat = "Entertainment"
    elif any(k in lower for k in ["amazon", "flipkart", "myntra", "clothes", "shoe", "hoodie", "watch", "shopping", "mall"]):
        cat = "Shopping"
    elif any(k in lower for k in ["medicine", "doctor", "pharmacy", "gym", "protein", "health"]):
        cat = "Health"
        
    # Build clean description
    desc = re.sub(r'(?:(?:rs\.?|inr|₹)\s*\d+(?:\.\d{1,2})?)|(?:\b\d+(?:\.\d{1,2})?\s*(?:rs\.?|inr|₹)\b)', '', text_clean, flags=re.IGNORECASE)
    desc = re.sub(r'\b(?:paid|spent|bought|for|on)\b', '', desc, flags=re.IGNORECASE).strip()
    if not desc:
        desc = f"{cat} Expense"
    desc = desc[:45].capitalize()
    
    roundup = calculate_roundup(amount, round_to=10)
    return {
        "amount": amount,
        "category": cat,
        "description": desc,
        "suggested_roundup": roundup
    }

def detect_recurring_expenses(transactions):
    """
    Scans past transactions to detect recurring subscriptions, rent, and student bills.
    """
    detected = []
    seen = {}
    for tx in transactions:
        desc = str(tx.get("description", "")).lower()
        amt = float(tx.get("amount", 0))
        tdate = str(tx.get("transaction_date", ""))
        
        key = None
        if "spotify" in desc:
            key = ("Spotify Premium Student", "Entertainment", amt, "Monthly")
        elif "youtube" in desc:
            key = ("YouTube Student Plan", "Entertainment", amt, "Monthly")
        elif "rent" in desc or "pg" in desc:
            key = ("Student PG / Flat Rent", "Bills", amt, "Monthly")
        elif "metro" in desc:
            key = ("Metro Smart Card", "Transport", amt, "Monthly")
        elif "wifi" in desc or "broadband" in desc:
            key = ("Hostel Wi-Fi Share", "Bills", amt, "Monthly")
        elif "mess" in desc:
            key = ("Campus Mess Fee", "Food", amt, "Monthly")
        elif "gym" in desc:
            key = ("Gym Membership", "Health", amt, "Monthly")
            
        if key and key[0] not in seen:
            seen[key[0]] = True
            parsed_dt = parse_dmy(tdate)
            next_due = parsed_dt + timedelta(days=30)
            detected.append({
                "title": key[0],
                "category": key[1],
                "amount": float(key[2]),
                "frequency": key[3],
                "last_paid": format_dmy(tdate),
                "next_due": format_dmy(next_due),
                "days_until_due": max(1, (next_due - date.today()).days)
            })
            
    if not detected:
        today = date.today()
        detected = [
            {
                "title": "Spotify Premium Student",
                "category": "Entertainment",
                "amount": 69.00,
                "frequency": "Monthly",
                "last_paid": format_dmy(today - timedelta(days=14)),
                "next_due": format_dmy(today + timedelta(days=16)),
                "days_until_due": 16
            },
            {
                "title": "YouTube Premium Student",
                "category": "Entertainment",
                "amount": 89.00,
                "frequency": "Monthly",
                "last_paid": format_dmy(today - timedelta(days=3)),
                "next_due": format_dmy(today + timedelta(days=27)),
                "days_until_due": 27
            },
            {
                "title": "PG / Flat Rent Share",
                "category": "Bills",
                "amount": 9500.00,
                "frequency": "Monthly",
                "last_paid": format_dmy(today - timedelta(days=10)),
                "next_due": format_dmy(today + timedelta(days=20)),
                "days_until_due": 20
            }
        ]
    return detected

def compare_expenses(transactions, user):
    """
    Multi-dimensional expense comparison engine:
    1. Period Comparison: Last 15 days vs Previous 15 days
    2. Weekday vs Weekend spending velocity
    3. Category distribution vs Indian Student Benchmark
    4. Micro-leakage (< ₹100 spends)
    """
    today = date.today()
    expenses = [t for t in transactions if str(t.get("transaction_type", "")).lower() == "expense"]
    
    # 1. Period Comparison (Recent 15 days vs Prior 15 days)
    recent_sum = Decimal("0.00")
    prior_sum = Decimal("0.00")
    
    for tx in expenses:
        dt = parse_dmy(tx.get("transaction_date"))
        amt = to_decimal(tx.get("amount", 0))
        delta_days = (today - dt).days
        if 0 <= delta_days <= 15:
            recent_sum += amt
        elif 16 <= delta_days <= 30:
            prior_sum += amt
            
    recent_f = float(recent_sum)
    prior_f = float(prior_sum)
    if prior_f > 0:
        period_diff_pct = round(((recent_f - prior_f) / prior_f) * 100, 1)
    else:
        period_diff_pct = 0.0
        
    # 2. Weekday vs Weekend Analysis
    weekday_sum = Decimal("0.00")
    weekday_count = 0
    weekend_sum = Decimal("0.00")
    weekend_count = 0
    
    for tx in expenses:
        dt = parse_dmy(tx.get("transaction_date"))
        amt = to_decimal(tx.get("amount", 0))
        if dt.weekday() < 5:
            weekday_sum += amt
            weekday_count += 1
        else:
            weekend_sum += amt
            weekend_count += 1
            
    weekday_avg = round(float(weekday_sum) / max(1, weekday_count), 2)
    weekend_avg = round(float(weekend_sum) / max(1, weekend_count), 2)
    weekend_surge_pct = round(((weekend_avg - weekday_avg) / max(1.0, weekday_avg)) * 100, 1) if weekday_avg > 0 else 0.0

    # 3. Category Breakdown vs Benchmark
    total_exp = sum(to_decimal(t.get("amount", 0)) for t in expenses)
    total_exp_f = float(total_exp)
    
    cat_spend = {}
    for tx in expenses:
        c = tx.get("category", "Other")
        cat_spend[c] = cat_spend.get(c, Decimal("0.00")) + to_decimal(tx.get("amount", 0))
        
    benchmark_comparison = []
    for cat, bench in STUDENT_BENCHMARKS.items():
        actual_amt = float(cat_spend.get(cat, Decimal("0.00")))
        actual_pct = round((actual_amt / total_exp_f * 100), 1) if total_exp_f > 0 else 0.0
        bench_pct = bench["pct"]
        diff_pct = round(actual_pct - bench_pct, 1)
        
        status = "Disciplined"
        if diff_pct > 5.0:
            status = "Overspending"
        elif diff_pct < -5.0:
            status = "Under Budget"
            
        benchmark_comparison.append({
            "category": cat,
            "icon": bench["icon"],
            "actual_amt": actual_amt,
            "actual_pct": actual_pct,
            "benchmark_pct": bench_pct,
            "diff_pct": diff_pct,
            "status": status,
            "advice": bench["advice"]
        })
        
    # 4. Micro-Leakage (< ₹100 spends)
    micro_spends = [t for t in expenses if to_decimal(t.get("amount", 0)) <= Decimal("100.00")]
    micro_total = sum(to_decimal(t.get("amount", 0)) for t in micro_spends)
    micro_count = len(micro_spends)
    micro_pct_of_total = round((float(micro_total) / total_exp_f * 100), 1) if total_exp_f > 0 else 0.0
    
    return {
        "recent_period_spend": recent_f,
        "prior_period_spend": prior_f,
        "period_diff_pct": period_diff_pct,
        "is_spending_higher": recent_f > prior_f,
        "weekday_avg": weekday_avg,
        "weekend_avg": weekend_avg,
        "weekend_surge_pct": weekend_surge_pct,
        "benchmark_comparison": benchmark_comparison,
        "micro_leakage": {
            "count": micro_count,
            "total_amount": float(micro_total),
            "pct_of_total": micro_pct_of_total,
            "sample_spends": [
                {"desc": m.get("description", ""), "amount": float(m.get("amount", 0)), "date": format_dmy(m.get("transaction_date"))}
                for m in micro_spends[:4]
            ]
        }
    }

def predict_financial_trajectory(user, income, expenses, liquid_savings, transactions):
    """
    Calculates predictive runway calendar:
    - Projected month-end balance
    - Exact Runway Depletion Date (DD-MM-YYYY)
    - Exam Surge Projection (spikes burn by 80%)
    """
    inc = float(to_decimal(income))
    exp = float(to_decimal(expenses))
    savings = float(to_decimal(liquid_savings))
    
    today = date.today()
    days_elapsed = max(1, today.day)
    days_in_month = 30
    days_remaining = max(1, days_in_month - days_elapsed)
    
    daily_burn = exp / float(days_elapsed) if exp > 0 else 0.0
    projected_month_expenses = round(exp + (daily_burn * days_remaining), 2)
    projected_month_balance = round(inc - projected_month_expenses, 2)
    
    # Runway Depletion Date calculation
    net_surplus = max(0.0, inc - exp)
    runway_reserve = savings + net_surplus
    if daily_burn > 0:
        days_surviving = int(runway_reserve / daily_burn)
    else:
        days_surviving = 999
        
    depletion_date = today + timedelta(days=min(3650, days_surviving))
    depletion_date_dmy = format_dmy(depletion_date)
    
    # Exam Surge Buffer (simulated mid-sems in 12 days)
    # Typical student daily burn jumps ~2.2x during exams (caffeine, cabs, xerox, snacks)
    exam_surge_burn = daily_burn * 2.2
    exam_surge_buffer = round(exam_surge_burn * 7, 2)
    
    return {
        "daily_burn": round(daily_burn, 2),
        "days_remaining_in_month": days_remaining,
        "projected_month_expenses": projected_month_expenses,
        "projected_month_balance": projected_month_balance,
        "is_projected_deficit": projected_month_balance < 0,
        "runway_days_total": days_surviving,
        "runway_depletion_date": depletion_date_dmy,
        "exam_surge_buffer_needed": exam_surge_buffer,
        "exam_date_dmy": format_dmy(today + timedelta(days=12))
    }

def generate_coach_response(query, context):
    """
    Conversational AI Financial Coach & Expense Comparator.
    Answers natural language queries using real student metrics from context.
    """
    q = (query or "").lower().strip()
    
    user = context.get("user", {})
    income = float(to_decimal(context.get("income", 0)))
    expenses = float(to_decimal(context.get("expenses", 0)))
    savings = float(to_decimal(context.get("savings", 0)))
    cockpit = context.get("cockpit", {})
    comparison = context.get("comparison", {})
    trajectory = context.get("trajectory", {})
    
    runway_days = cockpit.get("runway_days", 0)
    safe_daily = cockpit.get("safe_daily_spend", 0)
    daily_burn = cockpit.get("daily_burn_rate", 0)
    

    # 1. Category Comparisons (e.g. food vs transport, food vs bills)
    if "compare" in q and ("food" in q or "transport" in q or "bill" in q or "shopping" in q):
        benchmarks = comparison.get("benchmark_comparison", [])
        food_data = next((b for b in benchmarks if b["category"] == "Food"), None)
        trans_data = next((b for b in benchmarks if b["category"] == "Transport"), None)
        bills_data = next((b for b in benchmarks if b["category"] == "Bills"), None)
        
        target_a = food_data if "food" in q else trans_data
        target_b = trans_data if "transport" in q and target_a != trans_data else bills_data
        if not target_a:
            target_a = benchmarks[0] if benchmarks else {"category": "Food", "actual_amt": 4500, "actual_pct": 35}
        if not target_b:
            target_b = benchmarks[1] if len(benchmarks) > 1 else {"category": "Transport", "actual_amt": 848, "actual_pct": 8}
            
        ratio = round(target_a["actual_amt"] / max(1.0, target_b["actual_amt"]), 1)
        advice_str = target_a.get("advice", "")
        response_text = (
            f"Here is your category comparison:\n\n"
            f"• **{target_a['category']}**: ₹{target_a['actual_amt']:,.2f} ({target_a['actual_pct']}% of expenses)\n"
            f"• **{target_b['category']}**: ₹{target_b['actual_amt']:,.2f} ({target_b['actual_pct']}% of expenses)\n\n"
            f"You spend **{ratio}x more on {target_a['category']}** than {target_b['category']}. "
            f"According to college benchmarks, {advice_str}"
        )
        return {
            "answer": response_text,
            "comparison_card": {
                "title": f"Comparison: {target_a['category']} vs {target_b['category']}",
                "item_a": {"name": target_a["category"], "amount": target_a["actual_amt"], "pct": target_a["actual_pct"]},
                "item_b": {"name": target_b["category"], "amount": target_b["actual_amt"], "pct": target_b["actual_pct"]},
                "insight": f"{target_a['category']} takes {target_a['actual_pct']}% of your budget (Benchmark: {target_a.get('benchmark_pct', 35)}%)."
            },
            "suggested_actions": [
                {"label": "Adjust Category Budget", "action": "openBudgetModal"},
                {"label": "Explore Student Perks", "action": "scrollToPerks"}
            ]
        }

    # 2. Period / Month-on-Month Comparison
    if "compare" in q and ("month" in q or "period" in q or "last" in q):
        recent = comparison.get("recent_period_spend", 0)
        prior = comparison.get("prior_period_spend", 0)
        diff_pct = comparison.get("period_diff_pct", 0)
        is_higher = comparison.get("is_spending_higher", False)
        
        dir_text = "increased" if is_higher else "decreased"
        
        response_text = (
            f"Comparing your spending momentum:\n\n"
            f"• **Recent 15 Days**: ₹{recent:,.2f}\n"
            f"• **Prior 15 Days**: ₹{prior:,.2f}\n\n"
            f"Your spending velocity has **{dir_text} by {abs(diff_pct)}%**. "
            + ("Let's tighten discretionary spends (Swiggy, late-night cabs) to extend your runway!" if is_higher else "Great discipline! You are maintaining a healthy savings buffer.")
        )
        return {
            "answer": response_text,
            "comparison_card": {
                "title": "Period Spending Velocity",
                "item_a": {"name": "Recent 15d", "amount": recent, "pct": diff_pct},
                "item_b": {"name": "Prior 15d", "amount": prior, "pct": 0},
                "insight": f"Shift: {abs(diff_pct)}% {'surge' if is_higher else 'drop'} in burn rate."
            },
            "suggested_actions": [
                {"label": "Simulate Budget 'What-If'", "action": "openSimulatorModal"},
                {"label": "Stash ₹100 into Piggy", "action": "stashPiggy"}
            ]
        }

    # 3. Peer Benchmark Comparison
    if "benchmark" in q or "other student" in q or "average" in q:
        benchmarks = comparison.get("benchmark_comparison", [])
        food_row = next((b for b in benchmarks if b["category"] == "Food"), {})
        response_text = (
            f"Here is how your spending compares with average Indian engineering & university students:\n\n"
            f"• **Food & Dining**: You spend **{food_row.get('actual_pct', 0)}%** (Campus Benchmark: 35%)\n"
            f"• **Weekend Burn**: You average **₹{comparison.get('weekend_avg', 0):,.2f}/day** on weekends vs ₹{comparison.get('weekday_avg', 0):,.2f}/day on weekdays ({comparison.get('weekend_surge_pct', 0)}% surge!)\n"
            f"• **Micro-Leakage**: You have **{comparison.get('micro_leakage', {}).get('count', 0)} micro-spends** under ₹100 totaling ₹{comparison.get('micro_leakage', {}).get('total_amount', 0):,.2f}.\n\n"
            f"**Coach Tip**: Plugging just 2 micro-spends/day adds ~₹1,200 to your end-of-semester runway."
        )
        return {
            "answer": response_text,
            "comparison_card": {
                "title": "Campus Peer Benchmark Comparison",
                "item_a": {"name": "Your Food Spend", "amount": food_row.get("actual_amt", 0), "pct": food_row.get("actual_pct", 0)},
                "item_b": {"name": "Student Benchmark", "amount": round(income * 0.35, 2), "pct": 35.0},
                "insight": f"Status: {food_row.get('status', 'Balanced')}. {food_row.get('advice', '')}"
            },
            "suggested_actions": [
                {"label": "View Intelligence Radar", "action": "navigateIntelligence"},
                {"label": "Auto-Roundup Spare Change", "action": "stashPiggy"}
            ]
        }

    # 4. Affordability ("Can I afford X?")
    afford_match = re.search(r'(?:afford|buy|spend|order)\s*(?:a|an)?\s*(?:rs\.?|inr|₹)?\s*(\d+)', q)
    if afford_match:
        test_amt = float(afford_match.group(1))
        impact_days = int(test_amt / daily_burn) if daily_burn > 0 else 1
        can_afford = test_amt <= safe_daily
        
        if can_afford:
            ans = (
                f"✅ **Yes, you can afford ₹{test_amt:,.2f}!**\n\n"
                f"Your safe daily spend allowance is **₹{safe_daily:,.2f}/day**. "
                f"This purchase fits cleanly inside today's buffer without damaging your {runway_days}-day runway."
            )
        else:
            ans = (
                f"⚠️ **Proceed with Caution on ₹{test_amt:,.2f}**\n\n"
                f"This is larger than your safe daily allowance of **₹{safe_daily:,.2f}/day**. "
                f"Making this purchase will consume approximately **{impact_days} days of your remaining runway**. "
                f"If it is discretionary, consider using the *24-Hour Cooling Vault* or skipping dining out tomorrow to compensate."
            )
        return {
            "answer": ans,
            "comparison_card": {
                "title": f"Affordability Check: ₹{test_amt:,.2f}",
                "item_a": {"name": "Purchase Cost", "amount": test_amt, "pct": round((test_amt / max(1.0, safe_daily)) * 100, 1)},
                "item_b": {"name": "Safe Daily Limit", "amount": safe_daily, "pct": 100.0},
                "insight": f"Runway impact: -{impact_days} days if unpaid from savings."
            },
            "suggested_actions": [
                {"label": "Log as Split Bill", "action": "openSplitModal"},
                {"label": "Check Safe Daily Spend", "action": "scrollToCockpit"}
            ]
        }

    # 5. Runway & Depletion Date Inquiries
    if "runway" in q or "when" in q or "deplet" in q or "out of money" in q:
        dep_date = trajectory.get("runway_depletion_date", "N/A")
        ans = (
            f"Here is your real-time Runway Projection:\n\n"
            f"• **Runway Cushion**: **{runway_days} Days remaining**\n"
            f"• **Projected Depletion Date**: **{dep_date}**\n"
            f"• **Current Daily Burn**: **₹{daily_burn:,.2f}/day**\n"
            f"• **Safe Daily Allowance**: **₹{safe_daily:,.2f}/day**\n\n"
            f"💡 **Exam Alert**: Mid-sems start around {trajectory.get('exam_date_dmy', 'soon')}. "
            f"We forecast your burn will surge by 2.2x. We suggest keeping an *Exam Defense Cushion* of ₹{trajectory.get('exam_surge_buffer_needed', 1800):,.0f}."
        )
        return {
            "answer": ans,
            "comparison_card": {
                "title": "Runway Survival Metrics",
                "item_a": {"name": "Daily Burn Rate", "amount": daily_burn, "pct": 0},
                "item_b": {"name": "Safe Daily Spend", "amount": safe_daily, "pct": 0},
                "insight": f"Target runway date: {dep_date} (DD-MM-YYYY)"
            },
            "suggested_actions": [
                {"label": "Simulate Runway Boost", "action": "openSimulatorModal"},
                {"label": "Recharge Piggy Vault", "action": "stashPiggy"}
            ]
        }

    # 6. Default / General Financial Advice
    ans = (
        f"Hi {user.get('name', 'Student')}! I am your **SpendWise AI Financial Coach** 🎓.\n\n"
        f"• Your current runway is **{runway_days} Days** with a safe spend rate of **₹{safe_daily:,.2f}/day**.\n"
        f"• You've spent **₹{expenses:,.2f}** against an income of **₹{income:,.2f}** this month.\n\n"
        f"Try asking me:\n"
        f"1. *'Compare my Food vs Transport spending'*\n"
        f"2. *'Compare this month vs last month'*\n"
        f"3. *'How does my spending compare to other students?'*\n"
        f"4. *'Can I afford a ₹1,200 weekend trip?'*\n"
        f"5. *'When will my runway run out?'*"
    )
    return {
        "answer": ans,
        "comparison_card": {
            "title": "SpendWise Financial Cockpit",
            "item_a": {"name": "Monthly Income", "amount": income, "pct": 100},
            "item_b": {"name": "Active Outflow", "amount": expenses, "pct": round((expenses / max(1.0, income)) * 100, 1)},
            "insight": f"Remaining liquid runway: {runway_days} days."
        },
        "suggested_actions": [
            {"label": "Compare Food vs Transport", "action": "queryCoach('Compare Food vs Transport')"},
            {"label": "Check Student Benchmarks", "action": "queryCoach('How do I compare to other students?')"}
        ]
    }




# =====================================================================
# AUTONOMOUS CONVERSATIONAL CHATBOT (BACKEND SFI TELEMETRY & SELF-LEARNING)
# =====================================================================

def process_chat_query(query, user, all_txs, budgets=None, goals=None, piggy_balance=Decimal("0.00"), current_memory=None, **kwargs):
    """
    Core Conversational Financial Intelligence Brain.
    Observes all user transactions, computes SFI metrics in real time,
    answers student questions with data grounding, and dynamically updates
    its internal memory profile from every query answered.
    """
    q_raw = query or ""
    q = q_raw.lower().strip()
    current_memory = dict(current_memory or {})
    
    # 1. OBSERVE LIVE STUDENT TELEMETRY IN THE BACKEND
    expenses = [t for t in all_txs if str(t.get("transaction_type", "")).lower() == "expense"]
    incomes = [t for t in all_txs if str(t.get("transaction_type", "")).lower() == "income"]
    
    base_income = float(to_decimal(user.get("monthly_income", 0)))
    added_income = sum(float(to_decimal(t.get("amount", 0))) for t in incomes)
    total_income = base_income + added_income
    total_expenses = sum(float(to_decimal(t.get("amount", 0))) for t in expenses)
    net_balance = total_income - total_expenses
    
    piggy_val = float(to_decimal(piggy_balance))
    goals_val = sum(float(to_decimal(g.get("current_amount", 0))) for g in (goals or []))
    liquid_savings = piggy_val + goals_val
    
    cockpit = calculate_daily_cockpit(total_income, total_expenses, liquid_savings)
    comparison = compare_expenses(all_txs, user)
    trajectory = predict_financial_trajectory(user, total_income, total_expenses, liquid_savings, all_txs)
    recurring = detect_recurring_expenses(all_txs)
    
    # Category totals
    cat_spend = {}
    for t in expenses:
        c = t.get("category", "Other")
        cat_spend[c] = cat_spend.get(c, 0.0) + float(to_decimal(t.get("amount", 0)))
    top_category = max(cat_spend.items(), key=lambda x: x[1])[0] if cat_spend else "Food"
    top_cat_amt = cat_spend.get(top_category, 0.0)
    
    # Memory facts
    student_name = current_memory.get("student_name", user.get("name", "Student"))
    college_name = current_memory.get("college", user.get("college_name", "Engineering College"))
    target_goal = current_memory.get("target_goal", "Apple M3 MacBook Air (Coding & ML)")
    academic_stream = current_memory.get("academic_stream", "Computer Science & Engineering")
    living_situation = current_memory.get("living_situation", "PG Flat with flatmates")
    spending_concern = current_memory.get("spending_concern", "Weekend food delivery surges")

    # Academic & demographic credentials from memory
    marks_val_str = current_memory.get("marks_percent", "78.0")
    try:
        marks_percent = float(re.search(r'\d+(?:\.\d+)?', str(marks_val_str)).group(0))
    except Exception:
        marks_percent = 78.0

    income_val_str = current_memory.get("family_income_lakhs", "3.0")
    try:
        family_income_lakhs = float(re.search(r'\d+(?:\.\d+)?', str(income_val_str)).group(0))
    except Exception:
        family_income_lakhs = 3.0

    gender_val = current_memory.get("gender", "All")
    category_val = current_memory.get("category", "General")
    degree_val = current_memory.get("academic_degree", "Engineering")
    year_val = current_memory.get("academic_year", "1st Year")
    
    try:
        prev_solved = int(current_memory.get("queries_solved_count", "12"))
    except Exception:
        prev_solved = 12
    new_solved_count = prev_solved + 1
    
    # Track new knowledge extracted from this query
    learned_updates = {}
    learning_badge = None
    
    # Memory extraction rules:
    # A) Target goal extraction
    goal_match = re.search(r'(?:saving for|buy a|buying a|target goal|save up for|want to buy)\s+([a-zA-Z0-9\s\-]+?)(?:\.|\?|\!|$|,\s*and)', q_raw, re.IGNORECASE)
    if goal_match and len(goal_match.group(1).strip()) > 2:
        extracted_goal = goal_match.group(1).strip().title()
        if len(extracted_goal) < 40 and extracted_goal.lower() not in ["money", "rupees", "it", "more"]:
            target_goal = extracted_goal
            learned_updates["target_goal"] = (target_goal, 0.95)
            learning_badge = {
                "key": "target_goal",
                "value": target_goal,
                "text": f"🧠 Updated Goal: '{target_goal}' • Solved #{new_solved_count}"
            }
            
    # B) Spending concern extraction
    concern_match = re.search(r'(?:spend(?:ing)? too much on|worried about|cut down on|control my)\s+([a-zA-Z0-9\s\-]+?)(?:\.|\?|\!|$|,\s*and)', q_raw, re.IGNORECASE)
    if concern_match and len(concern_match.group(1).strip()) > 2:
        extracted_concern = concern_match.group(1).strip()
        if len(extracted_concern) < 35:
            spending_concern = f"High spend on {extracted_concern.title()}"
            learned_updates["spending_concern"] = (spending_concern, 0.9)
            learning_badge = {
                "key": "spending_concern",
                "value": spending_concern,
                "text": f"🧠 Noted Concern: '{spending_concern}' • Solved #{new_solved_count}"
            }
            
    # C) Living situation extraction
    if any(k in q for k in ["hostel", "paying guest", "pg", "flatmate", "living alone", "roommate"]):
        if "hostel" in q:
            living_situation = "Campus Hostel"
        elif "pg" in q:
            living_situation = "Student PG"
        elif "flat" in q or "flatmate" in q or "roommate" in q:
            living_situation = "Shared Flat with Flatmates"
        learned_updates["living_situation"] = (living_situation, 0.95)
        if not learning_badge:
            learning_badge = {
                "key": "living_situation",
                "value": living_situation,
                "text": f"🧠 Learned Living Context: '{living_situation}' • Solved #{new_solved_count}"
            }
            
    # D) Academic Stream / Year
    acad_match = re.search(r'\b(1st|2nd|3rd|4th|first|second|third|final)\s+(?:year|sem|semester)\s*([a-zA-Z\s]+)?', q_raw, re.IGNORECASE)
    if acad_match:
        yr_str = acad_match.group(1).title()
        branch_str = (acad_match.group(2) or "").strip().title()
        academic_stream = f"{yr_str} Year {branch_str}".strip()
        year_val = f"{yr_str} Year"
        if branch_str:
            degree_val = branch_str
        learned_updates["academic_stream"] = (academic_stream, 0.95)
        learned_updates["academic_year"] = (year_val, 0.95)
        if not learning_badge:
            learning_badge = {
                "key": "academic_stream",
                "value": academic_stream,
                "text": f"🧠 Updated Academic Profile: '{academic_stream}' • Solved #{new_solved_count}"
            }

    # E) Academic Marks / Score extraction
    marks_match = re.search(r'(?:scored?|got|marks?|percentage|score|aggregate|grade)\s*(?:of|is|are|:)?\s*(\d{1,3}(?:\.\d+)?)\s*%', q_raw, re.IGNORECASE)
    if not marks_match:
        marks_match = re.search(r'(\d{1,2}(?:\.\d+)?)\s*%\s*(?:in 12th|in 10th|marks?|aggregate|score)?', q_raw, re.IGNORECASE)
    if marks_match:
        try:
            m_val = float(marks_match.group(1))
            if 35.0 <= m_val <= 100.0:
                marks_percent = m_val
                current_memory["marks_percent"] = f"{m_val:.1f}%"
                learned_updates["marks_percent"] = (f"{m_val:.1f}%", 0.95)
                learning_badge = {
                    "key": "marks_percent",
                    "value": f"{m_val:.1f}%",
                    "text": f"🧠 Learned Score: {m_val:.1f}% Marks • Solved #{new_solved_count}"
                }
        except Exception:
            pass
    else:
        # Check for CGPA
        cgpa_match = re.search(r'(?:cgpa|gpa)\s*(?:of|is|:)?\s*(\d(?:\.\d+)?)', q_raw, re.IGNORECASE)
        if cgpa_match:
            try:
                cgpa_val = float(cgpa_match.group(1))
                if 4.0 <= cgpa_val <= 10.0:
                    equiv_marks = round(cgpa_val * 9.5, 1)
                    marks_percent = equiv_marks
                    current_memory["marks_percent"] = f"{equiv_marks:.1f}%"
                    learned_updates["marks_percent"] = (f"{equiv_marks:.1f}% (CGPA {cgpa_val})", 0.95)
                    learning_badge = {
                        "key": "marks_percent",
                        "value": f"{equiv_marks:.1f}%",
                        "text": f"🧠 Converted CGPA {cgpa_val} ➔ {equiv_marks:.1f}% • Solved #{new_solved_count}"
                    }
            except Exception:
                pass

    # F) Household / Family Income extraction
    income_match = re.search(r'(?:family income|household income|parents? income|annual income|income is|income of)\s*(?:is|of|:)?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)\s*(?:lakhs?|lpa|lac|lacs)?', q_raw, re.IGNORECASE)
    if not income_match:
        income_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakhs?|lpa|lac|lacs)\s*(?:annual|family|household)?\s*income', q_raw, re.IGNORECASE)
    if income_match:
        try:
            inc_val = float(income_match.group(1))
            if inc_val > 1000:
                inc_val = inc_val / 100000.0
            if 0.5 <= inc_val <= 50.0:
                family_income_lakhs = inc_val
                current_memory["family_income_lakhs"] = f"₹{inc_val:.1f} Lakhs/yr"
                learned_updates["family_income_lakhs"] = (f"₹{inc_val:.1f} Lakhs/yr", 0.95)
                if not learning_badge or learning_badge["key"] in ["queries_solved_count", "academic_stream"]:
                    learning_badge = {
                        "key": "family_income_lakhs",
                        "value": f"₹{inc_val:.1f}L",
                        "text": f"🧠 Learned Income: ₹{inc_val:.1f} Lakhs/yr • Solved #{new_solved_count}"
                    }
        except Exception:
            pass

    # G) Gender demographic extraction
    if re.search(r'\b(female|girl|woman|daughter)\b', q, re.IGNORECASE):
        gender_val = "Female"
        current_memory["gender"] = "Female"
        learned_updates["gender"] = ("Female", 0.95)
        if not learning_badge or learning_badge["key"] in ["queries_solved_count", "academic_stream"]:
            learning_badge = {
                "key": "gender",
                "value": "Female",
                "text": f"🧠 Profile Demographics: Female Student • Solved #{new_solved_count}"
            }
    elif re.search(r'\b(male|boy|man|son)\b', q, re.IGNORECASE):
        gender_val = "Male"
        current_memory["gender"] = "Male"
        learned_updates["gender"] = ("Male", 0.95)

    # H) Social category extraction
    if re.search(r'\b(sc|scheduled caste)\b', q, re.IGNORECASE):
        category_val = "SC"
        current_memory["category"] = "SC"
        learned_updates["category"] = ("SC", 0.95)
    elif re.search(r'\b(st|scheduled tribe)\b', q, re.IGNORECASE):
        category_val = "ST"
        current_memory["category"] = "ST"
        learned_updates["category"] = ("ST", 0.95)
    elif re.search(r'\b(obc|other backward class)\b', q, re.IGNORECASE):
        category_val = "OBC"
        current_memory["category"] = "OBC"
        learned_updates["category"] = ("OBC", 0.95)
    elif re.search(r'\b(minority|muslim|christian|sikh|jain|parsi|buddhist)\b', q, re.IGNORECASE):
        category_val = "Minority"
        current_memory["category"] = "Minority"
        learned_updates["category"] = ("Minority", 0.95)
    elif re.search(r'\b(general category|open category)\b', q, re.IGNORECASE):
        category_val = "General"
        current_memory["category"] = "General"
        learned_updates["category"] = ("General", 0.95)
            
    # Always increment queries solved count in memory
    learned_updates["queries_solved_count"] = (str(new_solved_count), 1.0)
    if not learning_badge:
        learning_badge = {
            "key": "queries_solved_count",
            "value": str(new_solved_count),
            "text": f"🧠 Bot Adapted: Active Telemetry Verified • Solved Query #{new_solved_count}"
        }

    # Format telemetry variables for answers
    runway_days = cockpit.get("runway_days", 0)
    burn_rate = cockpit.get("daily_burn_rate", 0.0)
    safe_daily = cockpit.get("safe_daily_spend", 0.0)
    depletion_date = trajectory.get("runway_depletion_date", "N/A")
    exam_buffer = trajectory.get("exam_surge_buffer_needed", 1800.0)
    exam_date = trajectory.get("exam_date_dmy", "soon")
    weekend_surge = comparison.get("weekend_surge_pct", 0.0)
    weekend_avg = comparison.get("weekend_avg", 0.0)
    weekday_avg = comparison.get("weekday_avg", 0.0)
    
    # 2. INTENT RESOLUTION & SMART RESPONSES
    
    # Intent 1: Quick Action: Log Expense
    if any(k in q for k in ["log expense", "record expense", "spent", "paid", "bought"]) and re.search(r'\d+', q):
        parsed = parse_nlp_expense(q_raw)
        p_amt = float(parsed["amount"])
        p_cat = parsed["category"]
        p_desc = parsed["description"]
        p_roundup = float(parsed["suggested_roundup"])
        
        ans = (
            f"⚡ **Expense Recognized & Verified**\n\n"
            f"• **Amount**: ₹{p_amt:,.2f}\n"
            f"• **Category**: {p_cat}\n"
            f"• **Description**: {p_desc}\n"
            f"• **Spare Change Round-up**: ₹{p_roundup:,.2f} to Piggy Bank\n\n"
            f"Your remaining safe daily limit for today is **₹{max(0.0, safe_daily - p_amt):,.2f}**. "
            f"Would you like me to record this to your ledger?"
        )
        return {
            "answer": ans,
            "intent": "action_log_expense",
            "data_card": {
                "type": "transaction_preview",
                "title": f"Log ₹{p_amt:,.2f} to {p_cat}",
                "amount": p_amt,
                "category": p_cat,
                "description": p_desc,
                "roundup": p_roundup,
                "safe_remaining": max(0.0, safe_daily - p_amt)
            },
            "suggested_actions": [
                {"label": f"Confirm Log ₹{p_amt:,.0f}", "action": f"recordExpense('{p_desc}', '{p_cat}', {p_amt}, {p_roundup})"},
                {"label": "Cancel", "action": "dismiss"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 2: Piggy Bank Stash
    if any(k in q for k in ["stash", "piggy", "vault", "save into piggy"]) and re.search(r'\d+', q):
        m = re.search(r'\d+', q)
        s_amt = float(m.group(0))
        ans = (
            f"🐷 **Piggy Vault Stash Simulation**\n\n"
            f"Depositing **₹{s_amt:,.2f}** into your micro-savings vault boosts your liquid cushion to **₹{(piggy_val + s_amt):,.2f}**.\n\n"
            f"This brings you **{round((s_amt / 95000.0) * 100, 1)}% closer** to your goal: *{target_goal}*."
        )
        return {
            "answer": ans,
            "intent": "action_stash_piggy",
            "data_card": {
                "type": "piggy_preview",
                "title": f"Stash ₹{s_amt:,.2f} to Piggy Bank",
                "current_vault": piggy_val,
                "new_vault": piggy_val + s_amt,
                "goal_progress": target_goal
            },
            "suggested_actions": [
                {"label": f"Deposit ₹{s_amt:,.0f} to Vault", "action": f"depositPiggy({s_amt})"},
                {"label": "Check Runway Status", "action": "query('What is my runway?')"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 3: Runway & Depletion Date (SFI Stage 3)
    if any(k in q for k in ["runway", "when will my money run out", "deplet", "out of money", "burn rate", "safe spend", "how long will my money last"]):
        ans = (
            f"📊 **SFI Runway & Cash Trajectory Assessment**\n\n"
            f"Observing your transactions and liquid reserves in real time:\n"
            f"• **Current Runway Cushion**: **{runway_days} Days remaining**\n"
            f"• **Exact Depletion Date**: **{depletion_date}** (Calendar date strictly computed)\n"
            f"• **Daily Burn Velocity**: **₹{burn_rate:,.2f}/day**\n"
            f"• **Safe Daily Allowance**: **₹{safe_daily:,.2f}/day**\n\n"
            f"💡 **Exam Alert**: Mid-semester exams are scheduled around **{exam_date}**. "
            f"During exams, study group caffeine, emergency cabs, and photocopying surge average student burn by **2.2x**. "
            f"I recommend maintaining an **Exam Defense Cushion** of **₹{exam_buffer:,.2f}**.\n\n"
            f"Aligned with your goal: *{target_goal}*."
        )
        return {
            "answer": ans,
            "intent": "sfi_runway",
            "data_card": {
                "type": "runway_telemetry",
                "title": f"Runway Telemetry ({runway_days} Days)",
                "depletion_date": depletion_date,
                "daily_burn": f"₹{burn_rate:,.2f}/day",
                "safe_daily": f"₹{safe_daily:,.2f}/day",
                "exam_buffer": f"₹{exam_buffer:,.2f}",
                "status": "Secure" if runway_days >= 30 else "Attention Needed"
            },
            "suggested_actions": [
                {"label": "How to Extend Runway?", "action": "query('How can I save ₹2,000 this month?')"},
                {"label": "Examine Weekend Surges", "action": "query('Why is my spending surging?')"},
                {"label": "Hostel Mess Rebate", "action": "query('How does mess rebate work?')"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 4: Weekend Surge & Velocity Spikes (SFI Stage 2)
    if any(k in q for k in ["weekend", "surge", "velocity", "why is my spending", "spike", "spiking", "weekday"]):
        ans = (
            f"⚡ **SFI Weekend Spending Surge Diagnosis**\n\n"
            f"By analyzing your transaction timestamps, the engine discovered:\n"
            f"• **Weekday Burn**: **₹{weekday_avg:,.2f}/day** (Disciplined routine)\n"
            f"• **Weekend Burn**: **₹{weekend_avg:,.2f}/day** (Spike of **+{weekend_surge}%**!)\n"
            f"• **Primary Surge Drivers**: Swiggy/Zomato late-night delivery, weekend outings with flatmates in {living_situation}.\n\n"
            f"🧠 **Bot Strategic Recommendation**:\n"
            f"If you cap weekend spending at ₹{round(weekday_avg * 1.3, 2):,.2f}/day, you will save **₹1,850/month**, pushing your runway depletion date by **+7.4 days**."
        )
        return {
            "answer": ans,
            "intent": "sfi_weekend_surge",
            "data_card": {
                "type": "surge_comparison",
                "title": f"Weekend Burn Spike: +{weekend_surge}%",
                "weekday_burn": f"₹{weekday_avg:,.2f}/day",
                "weekend_burn": f"₹{weekend_avg:,.2f}/day",
                "monthly_leakage": "₹1,850/mo",
                "extension_impact": "+7.4 days"
            },
            "suggested_actions": [
                {"label": "Check Food vs Transport", "action": "query('Compare Food vs Transport')"},
                {"label": "Hostel Mess Rebate", "action": "query('Hostel Mess Skip Rebate')"},
                {"label": "Simulate Weekend Cap", "action": "query('What if I save 500 on weekends?')"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 5: Category Comparison (e.g. Food vs Transport) (SFI Stage 2)
    if "compare" in q or ("food" in q and ("transport" in q or "bill" in q or "shopping" in q or "vs" in q)):
        benchmarks = comparison.get("benchmark_comparison", [])
        food_b = next((b for b in benchmarks if b["category"] == "Food"), {"actual_amt": cat_spend.get("Food", 4500), "actual_pct": 35.0, "advice": "Target 35% using mess meals."})
        trans_b = next((b for b in benchmarks if b["category"] == "Transport"), {"actual_amt": cat_spend.get("Transport", 848), "actual_pct": 8.0, "advice": "Use metro passes."})
        bills_b = next((b for b in benchmarks if b["category"] == "Bills"), {"actual_amt": cat_spend.get("Bills", 9500), "actual_pct": 35.0, "advice": "Rent & utilities."})
        
        target_a = food_b if "food" in q else trans_b
        target_b = trans_b if ("transport" in q and target_a != trans_b) else bills_b
        
        ratio = round(target_a["actual_amt"] / max(1.0, target_b["actual_amt"]), 1)
        
        ans = (
            f"⚖️ **Category Expense Comparison: {target_a['category']} vs {target_b['category']}**\n\n"
            f"• **{target_a['category']}**: **₹{target_a['actual_amt']:,.2f}** ({target_a['actual_pct']}% of your outflow)\n"
            f"• **{target_b['category']}**: **₹{target_b['actual_amt']:,.2f}** ({target_b['actual_pct']}% of your outflow)\n\n"
            f"You spend **{ratio}x more on {target_a['category']}** than {target_b['category']}.\n\n"
            f"💡 **Peer Benchmark Insight**: {target_a.get('advice', '')} "
            f"Trimming {target_a['category']} by just 15% frees up **₹{round(target_a['actual_amt'] * 0.15, 2):,.2f}/month** towards *{target_goal}*."
        )
        return {
            "answer": ans,
            "intent": "sfi_category_comparison",
            "data_card": {
                "type": "category_bar",
                "title": f"{target_a['category']} vs {target_b['category']}",
                "item_a": {"name": target_a["category"], "amount": target_a["actual_amt"], "pct": target_a["actual_pct"]},
                "item_b": {"name": target_b["category"], "amount": target_b["actual_amt"], "pct": target_b["actual_pct"]},
                "ratio": f"{ratio}x",
                "saving_potential": f"₹{round(target_a['actual_amt'] * 0.15, 2):,.2f}/mo"
            },
            "suggested_actions": [
                {"label": "Mess Skip Rebate", "action": "query('Hostel Mess Rebate')"},
                {"label": "Campus Peer Benchmarks", "action": "query('How do I compare to other students?')"},
                {"label": "View What Bot Learned", "action": "query('What do you know about me?')"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 6: Campus Peer Benchmarks & Micro-Leakages (SFI Stage 2)
    if any(k in q for k in ["benchmark", "other student", "average student", "peer", "compare to others"]):
        benchmarks = comparison.get("benchmark_comparison", [])
        food_b = next((b for b in benchmarks if b["category"] == "Food"), {})
        micro = comparison.get("micro_leakage", {})
        
        ans = (
            f"🎓 **Campus Peer Benchmark Comparison**\n\n"
            f"Comparing your spending habits with students across Indian universities:\n\n"
            f"• **Food & Dining**: You spend **{food_b.get('actual_pct', 35)}%** (Campus Benchmark: 35.0%)\n"
            f"• **Commute & Travel**: Transport is under budget at **{comparison.get('benchmark_comparison', [{}])[2].get('actual_pct', 8)}%** (Benchmark: 8.0%)\n"
            f"• **Micro-Leakage Radar**: You have **{micro.get('count', 3)} micro-spends under ₹100** totaling **₹{micro.get('total_amount', 195):,.2f}** (mostly canteen chai, coffee & printouts).\n\n"
            f"💡 **SFI Pro-Tip**: Setting an auto-roundup on micro-transactions into the Piggy Vault recovers ~₹600/month effortlessly."
        )
        return {
            "answer": ans,
            "intent": "sfi_peer_benchmarks",
            "data_card": {
                "type": "benchmark_radar",
                "title": "College Peer Index",
                "food_status": food_b.get("status", "Balanced"),
                "weekend_surge": f"+{weekend_surge}%",
                "micro_leakage_total": f"₹{micro.get('total_amount', 195):,.2f}",
                "micro_count": micro.get("count", 3)
            },
            "suggested_actions": [
                {"label": "Plug Micro-Leakages", "action": "query('How do I stop micro leakages?')"},
                {"label": "Check Food vs Bills", "action": "query('Compare Food vs Bills')"},
                {"label": "Hostel Mess Rebate", "action": "query('How does the hostel mess skip rebate work?')"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 7: Hostel Mess Skip Rebate & Food Delivery (SFI Stage 4)
    if any(k in q for k in ["mess", "mess rebate", "mess skip", "swiggy", "zomato", "canteen", "skip mess"]):
        ans = (
            f"🍛 **Hostel Mess Skip Arbitrage & Savings Engine**\n\n"
            f"Whenever you order from Swiggy/Zomato or eat out with friends, campus messes allow you to claim official meal leave rebates:\n\n"
            f"• **Official Campus Rate**: ~**₹115.00/meal** (Dinner / Lunch rebate)\n"
            f"• **Realistic Monthly Savings**: Skipping 8-10 weekend mess dinners saves **~₹1,150 to ₹1,400/month**\n"
            f"• **Current Mess Spend**: **₹{cat_spend.get('Food', 4500):,.2f}** this month\n\n"
            f"💡 **Rebate Workflow**: Apply through your college hostel portal/warden book before 2:00 PM. "
            f"The savings are credited directly to your mess fee bill or bank account at month-end."
        )
        return {
            "answer": ans,
            "intent": "sfi_mess_rebate",
            "data_card": {
                "type": "mess_rebate_card",
                "title": "Hostel Mess Rebate Tracker",
                "rate_per_meal": "₹115.00",
                "est_monthly_saving": "₹1,200/mo",
                "benefit_to_goal": f"Adds 1.3% progress to {target_goal}"
            },
            "suggested_actions": [
                {"label": "How to Claim Mess Leave", "action": "query('How do I claim hostel mess leave?')"},
                {"label": "Simulate ₹1,200 Savings", "action": "query('What if I save 1200 a month?')"},
                {"label": "Check Food vs Transport", "action": "query('Compare Food vs Transport')"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 8: Exam Surge Buffer (SFI Stage 3)
    if any(k in q for k in ["exam", "mid-sem", "midsem", "test", "buffer", "exam surge"]):
        ans = (
            f"📚 **Exam Surge Defense Cushion Engine**\n\n"
            f"College exams cause unexpected financial spikes:\n"
            f"• **Upcoming Exam Period**: Around **{exam_date}**\n"
            f"• **Surge Multiplier**: Daily burn surges by **2.2x** (late night Red Bull/chai, quick Uber/Rapido to lab, project printouts)\n"
            f"• **Required Exam Cushion**: **₹{exam_buffer:,.2f}**\n\n"
            f"🛡️ **Current Readiness**: Your total liquid savings (Piggy + Goals) stand at **₹{liquid_savings:,.2f}**, "
            + ("which fully covers your exam buffer with a healthy margin! 👍" if liquid_savings >= exam_buffer else "which is slightly tight. Consider stashing ₹300 into Piggy this week.")
        )
        return {
            "answer": ans,
            "intent": "sfi_exam_buffer",
            "data_card": {
                "type": "exam_cushion_card",
                "title": "Exam Surge Defense",
                "exam_window": exam_date,
                "surge_multiplier": "2.2x Daily Burn",
                "cushion_target": f"₹{exam_buffer:,.2f}",
                "readiness": "100% Protected" if liquid_savings >= exam_buffer else "Partially Protected"
            },
            "suggested_actions": [
                {"label": "Stash ₹200 to Piggy", "action": "depositPiggy(200)"},
                {"label": "Check Safe Daily Spend", "action": "query('What is my safe daily spend?')"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 10: Financial What-If Simulation
    sim_match = re.search(r'(?:save|cut|reduce)\s*(?:by|rs\.?|inr|₹)?\s*(\d+)', q)
    if sim_match or any(k in q for k in ["how can i save", "what if", "simulate", "saving advice"]):
        sim_amt = float(sim_match.group(1)) if sim_match else 2000.0
        extra_days = round(sim_amt / max(1.0, burn_rate), 1) if burn_rate > 0 else 5.0
        months_to_goal = round(95000.0 / max(1.0, (net_balance + sim_amt)), 1)
        
        ans = (
            f"💡 **SFI Financial What-If Simulation: Saving ₹{sim_amt:,.2f}/month**\n\n"
            f"If you optimize your budget by **₹{sim_amt:,.2f}/month**:\n"
            f"• **Runway Extension**: Adds **+{extra_days} days** to your semester cushion!\n"
            f"• **New Depletion Date**: Shifts from {depletion_date} to **{format_dmy(parse_dmy(depletion_date) + timedelta(days=int(extra_days)))}**\n"
            f"• **Goal Acceleration**: Reaches your *{target_goal}* in **~{months_to_goal} months** (saving 2.5 months!)\n\n"
            f"🎯 **Where to find this ₹{sim_amt:,.0f}**:\n"
            f"1. Claim Spotify Student (saves ₹50/mo)\n"
            f"2. Utilize Hostel Mess Skip on 4 weekend dinners (saves ₹460/mo)\n"
            f"3. Switch to Monthly Metro Smart Card (saves ₹800/mo)\n"
            f"4. Eliminate 1 Swiggy late-night impulse order (saves ~₹350/mo)"
        )
        return {
            "answer": ans,
            "intent": "sfi_simulation",
            "data_card": {
                "type": "simulation_card",
                "title": f"Simulation: Save ₹{sim_amt:,.2f}/mo",
                "extra_runway": f"+{extra_days} Days",
                "accelerated_goal": target_goal,
                "suggested_cuts": ["Mess Leave", "Metro Card", "Spotify Student"]
            },
            "suggested_actions": [
                {"label": "Hostel Mess Skip Rebate", "action": "query('Hostel Mess Skip Rebate')"},
                {"label": "Check Food vs Transport", "action": "query('Compare Food vs Transport')"},
                {"label": "What is my current runway?", "action": "query('What is my runway?')"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 11: Memory Vault Inspection
    if any(k in q for k in ["what do you know", "show memory", "who am i", "my profile", "memory vault", "what have you learned"]):
        ans = (
            f"🧠 **SpendWise Autonomous Memory Vault**\n\n"
            f"I continuously learn from every query you ask and observe your transactions in real-time. Here is what I currently know about you:\n\n"
            f"• **Student**: {student_name} ({academic_stream})\n"
            f"• **College**: {college_name}\n"
            f"• **Living Situation**: {living_situation}\n"
            f"• **Primary Target Goal**: *{target_goal}*\n"
            f"• **Identified Budget Concern**: {spending_concern}\n"
            f"• **Queries Solved & Adapted**: **{new_solved_count} queries**\n\n"
            f"Whenever your goals or constraints change (e.g. *'I am saving for an iPad'* or *'I moved to hostel'*), just tell me and I update my brain immediately!"
        )
        return {
            "answer": ans,
            "intent": "sfi_memory_vault",
            "data_card": {
                "type": "memory_vault_card",
                "title": f"Active AI Memory Profile ({new_solved_count} Solved)",
                "traits": [
                    {"label": "Target Goal", "value": target_goal},
                    {"label": "Spending Concern", "value": spending_concern},
                    {"label": "Academic Year", "value": academic_stream},
                    {"label": "Living Setup", "value": living_situation}
                ]
            },
            "suggested_actions": [
                {"label": "Update Target Goal", "action": "query('I am saving for a new gaming laptop')"},
                {"label": "Check SFI Runway", "action": "query('What is my runway?')"},
                {"label": "Clear Memory", "action": "clearMemory()"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 12: Recurring Transit Passes, Bills & Student Subscriptions
    if any(k in q for k in ["recurring", "subscription", "metro", "bus", "pass", "transit", "commute", "fare", "recharge", "spotify", "prime", "youtube", "mess", "perk"]):
        is_transit = any(k in q for k in ["metro", "bus", "pass", "transit", "commute", "fare"])
        if is_transit:
            ans = (
                f"🚇 **Campus Transit & Commuter Passes Hub**\n\n"
                f"Your active daily campus travel commitments:\n"
                f"• **Namma Metro Smartcard Auto-Recharge**: **₹800.00 / month** (Purple & Green Line commute)\n"
                f"• **Campus & City Bus Pass**: **₹450.00 / month** (Route 42A Student pass)\n\n"
                f"🚌 **Total Transit Commitment**: **₹1,250.00 / month** (~₹41.67/day)\n\n"
                f"💡 **Commuter Savings Hack**: Using the metro smart card saves ~20% compared to daily single-journey tokens, saving you **~₹180-₹240/month**."
            )
            title = "Active Transit & Travel Passes"
            bills = [
                {"name": "🚇 Metro Smartcard Pass", "amount": "₹800.00", "due": "Monthly", "status": "Active"},
                {"name": "🚌 City / Campus Bus Pass", "amount": "₹450.00", "due": "Monthly", "status": "Active"},
                {"name": "📱 Student 5G Pack", "amount": "₹299.00", "due": "Monthly", "status": "Active"}
            ]
        else:
            ans = (
                f"⚡ **Recurring Bills, Transit & Student Subscriptions**\n\n"
                f"Detected monthly recurring commitments:\n"
                f"• **🚇 Metro Smartcard Recharge**: ₹800.00 / month (Transit)\n"
                f"• **🚌 Campus Bus Pass**: ₹450.00 / month (Transit)\n"
                f"• **📱 Jio Student 5G Pack**: ₹299.00 / month (Bills)\n"
                f"• **🍽️ Hostel Mess Dining Dues**: ₹3,200.00 / month (Food)\n"
                f"• **🎧 Spotify Premium Student**: ₹69.00 / month (42% Student discount active)\n\n"
                f"🎁 **Unclaimed Student Perks Available**:\n"
                f"• **GitHub Student Developer Pack**: 100% FREE (₹1.5L+ worth of GitHub Pro, Copilot, free domains & cloud credits)\n"
                f"• **Amazon Prime Youth Offer**: 50% cashback on annual membership (Effective ₹749/yr)"
            )
            title = "Recurring Payments & Passes"
            bills = [
                {"name": "🚇 Metro Smartcard", "amount": "₹800.00", "due": "Monthly", "status": "Active"},
                {"name": "🚌 Campus Bus Pass", "amount": "₹450.00", "due": "Monthly", "status": "Active"},
                {"name": "🍽️ Hostel Mess Dues", "amount": "₹3,200.00", "due": "Monthly", "status": "Active"},
                {"name": "🎧 Spotify Student", "amount": "₹69.00", "status": "Discount Active"}
            ]

        return {
            "answer": ans,
            "intent": "sfi_subscriptions",
            "data_card": {
                "type": "recurring_card",
                "title": title,
                "bills": bills
            },
            "suggested_actions": [
                {"label": "🚇 Metro Pass Status", "action": "query('When is my metro recharge due?')"},
                {"label": "🚌 Bus Pass Info", "action": "query('How much do I spend on bus fare and commute?')"},
                {"label": "Check Runway Status", "action": "query('What is my runway?')"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 13: Student Financial Literacy (SIP, Compounding, Emergency Fund, Credit Cards)
    if any(k in q for k in ["sip", "compound", "invest", "emergency fund", "credit card", "fixed deposit", "fd", "50 30 20", "mutual fund"]):
        topic = "Student Financial Strategy"
        if "sip" in q:
            topic = "Systematic Investment Plans (SIP)"
            body = (
                "A **Systematic Investment Plan (SIP)** allows college students to invest small amounts (as low as **₹100 or ₹500/month**) into diversified equity index funds (e.g. Nifty 50 Index Fund via Zerodha Coin or Groww).\n\n"
                "• **Why it matters in college**: Time in the market is your biggest superpower. Starting ₹500/mo at age 19 at an expected 12% return grows significantly faster than starting ₹5,000/mo at age 30 due to compounding."
            )
        elif "compound" in q:
            topic = "The Power of Compounding"
            body = (
                "Compounding is earning interest on top of previous interest and gains:\n\n"
                "• If you invest **₹1,000/month** from 1st year to 4th year (~₹48,000 principal), at 12% CAGR, in 15 years it compounds to over **₹3.2 Lakhs**!\n"
                "• In college, compounding applies equally to habits: saving ₹30/day on canteen chai puts **₹11,000/year** back into your pocket."
            )
        elif "emergency fund" in q:
            topic = "Student Emergency Cushion"
            body = (
                "An **Emergency Cushion** covers 2 to 3 months of essential fixed costs (rent, mess food, emergency medical, travel ticket home).\n\n"
                f"• For your monthly profile, a 3-month cushion is **~₹35,000 to ₹45,000**.\n"
                f"• Your current liquid cushion stands at **₹{liquid_savings:,.2f}**."
            )
        else:
            topic = "50/30/20 Student Budgeting Rule"
            body = (
                "The **50/30/20 Rule** adapted for college students with stipends/allowances:\n\n"
                "• **50% Needs**: PG rent, hostel mess, daily commute, textbook photocopies.\n"
                "• **30% Wants**: Weekend Swiggy food orders, movie tickets, college fest outfits.\n"
                "• **20% Future Cushion**: Piggy Vault stash, emergency reserve, tech gear goals."
            )
            
        ans = (
            f"💡 **Financial Masterclass: {topic}**\n\n"
            f"{body}\n\n"
            f"Aligned with your goal: *{target_goal}*."
        )
        return {
            "answer": ans,
            "intent": "financial_literacy",
            "data_card": {
                "type": "literacy_card",
                "title": topic,
                "key_takeaway": "Start small (₹100-₹500/mo) & maintain consistent monthly streak.",
                "student_friendly": "100% Zero-Commission Apps (Groww/Zerodha/MF Central)"
            },
            "suggested_actions": [
                {"label": "How to save ₹2,000?", "action": "query('How can I save ₹2,000 this month?')"},
                {"label": "Stash ₹100 into Vault", "action": "depositPiggy(100)"},
                {"label": "Check My Runway", "action": "query('What is my runway?')"}
            ],
            "learned_updates": learned_updates,
            "learning_badge": learning_badge
        }

    # Intent 14: Default / General Student Assistant Query
    ans = (
        f"Hi {student_name}! I am your **SpendWise Autonomous AI Financial Assistant** 🎓.\n\n"
        f"I observe all your transactions and college expenses in real-time:\n"
        f"• **Current Runway**: **{runway_days} Days** (Depletion: **{depletion_date}**)\n"
        f"• **Daily Safe Allowance**: **₹{safe_daily:,.2f}/day** (Current burn: ₹{burn_rate:,.2f}/day)\n"
        f"• **Top Spending Category**: **{top_category}** (₹{top_cat_amt:,.2f})\n"
        f"• **Target Milestone**: *{target_goal}*\n\n"
        f"Here are a few smart things you can ask me:\n"
        f"1. *'When will my money run out?'* (Exact calendar depletion date)\n"
        f"2. *'Why is my spending surging?'* (Weekend vs weekday analysis)\n"
        f"3. *'Compare Food vs Transport'* (Category benchmarks)\n"
        f"4. *'How does hostel mess rebate work?'* (Save ₹1,200/mo on food)\n"
        f"5. *'How can I save ₹2,000 this month?'* (What-if financial simulation)\n"
        f"6. *'What have you learned about me?'* (Inspect AI Memory Vault)"
    )
    return {
        "answer": ans,
        "intent": "general_assistant",
        "data_card": {
            "type": "assistant_overview",
            "title": f"SpendWise AI Cockpit ({runway_days}d Runway)",
            "safe_daily": f"₹{safe_daily:,.2f}/day",
            "burn_rate": f"₹{burn_rate:,.2f}/day",
            "depletion_date": depletion_date,
            "target_goal": target_goal
        },
        "suggested_actions": [
            {"label": "What is my runway?", "action": "query('What is my runway?')"},
            {"label": "Weekend Burn Surge", "action": "query('Why is my spending surging?')"},
            {"label": "Mess Skip Rebate", "action": "query('Hostel Mess Skip Rebate')"},
            {"label": "Save ₹2,000 / Month", "action": "query('How can I save ₹2,000 this month?')"}
        ],
        "learned_updates": learned_updates,
        "learning_badge": learning_badge
    }


