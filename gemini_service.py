import os
import json
import logging
from decimal import Decimal
from datetime import date

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

import finance_engine

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODELS = [
    DEFAULT_GEMINI_MODEL,
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
]
KEY_FILE = os.path.join(os.path.dirname(__file__), "gemini_key.txt")


def get_gemini_api_key():
    """Retrieve Gemini API key from environment or local key file."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key and key.strip():
        return key.strip()
    if os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, "r", encoding="utf-8") as f:
                saved_key = f.read().strip()
                if saved_key:
                    return saved_key
        except Exception:
            pass
    return None


def set_gemini_api_key(key):
    """Save Gemini API key to runtime environment and key file."""
    clean_key = (key or "").strip()
    if clean_key:
        os.environ["GEMINI_API_KEY"] = clean_key
        try:
            with open(KEY_FILE, "w", encoding="utf-8") as f:
                f.write(clean_key)
        except Exception as e:
            logger.warning(f"Failed to persist Gemini API key to file: {e}")
        return True
    else:
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
        if os.path.exists(KEY_FILE):
            try:
                os.remove(KEY_FILE)
            except Exception:
                pass
        return False


def get_gemini_client():
    """Get an initialized google-genai Client if key is available."""
    if not GENAI_AVAILABLE:
        return None
    key = get_gemini_api_key()
    if not key:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        logger.error(f"Failed to initialize Gemini Client: {e}")
        return None


def get_gemini_status():
    """Return current status of Gemini API configuration."""
    key = get_gemini_api_key()
    has_key = bool(key and len(key) > 5)
    masked_key = f"{key[:4]}...{key[-4:]}" if has_key and len(key) >= 10 else ("Configured" if has_key else "Not Configured")
    return {
        "available": GENAI_AVAILABLE,
        "has_key": has_key,
        "masked_key": masked_key,
        "model": DEFAULT_GEMINI_MODEL,
        "provider": f"Google Gemini ({DEFAULT_GEMINI_MODEL})" if has_key else "SpendWise Autonomous Engine (Rule-based Fallback)",
    }


def build_financial_system_context(user, telemetry, txs, budgets, goals, recurring, memory):
    """Construct structured context grounding Gemini in the student's actual finances."""
    cockpit = telemetry.get("cockpit", {})
    trajectory = telemetry.get("trajectory", {})
    comparison = telemetry.get("comparison", {})

    tx_summary = []
    for t in (txs or [])[:12]:
        tx_summary.append(
            f"- {t.get('transaction_date')}: {t.get('description')} ({t.get('category')}) -> "
            f"{'+' if str(t.get('transaction_type')).lower() == 'income' else '-'}₹{float(t.get('amount', 0)):,.2f}"
        )

    budget_summary = []
    for b in (budgets or []):
        budget_summary.append(
            f"- {b.get('category')}: Limit ₹{float(b.get('monthly_limit', 0)):,.2f} | Spent ₹{float(b.get('spent', 0)):,.2f}"
        )

    goals_summary = []
    for g in (goals or []):
        goals_summary.append(
            f"- {g.get('title')}: Saved ₹{float(g.get('current_amount', 0)):,.2f} / Target ₹{float(g.get('target_amount', 0)):,.2f} (Due: {g.get('target_date')})"
        )

    recurring_summary = []
    for r in (recurring or []):
        recurring_summary.append(
            f"- {r.get('title')} ({r.get('category')}): ₹{float(r.get('amount', 0)):,.2f}/{r.get('frequency', 'Monthly')} | Next Due: {r.get('next_due_date')} | Mode: {r.get('payment_method')} | Status: {r.get('status')}"
        )

    context = f"""
STUDENT IDENTITY & PROFILE:
- Name: {user.get('name', 'Student')}
- College: {user.get('college_name', 'Engineering College')}
- Monthly Base Income/Stipend: ₹{float(user.get('monthly_income', 0)):,.2f}
- Active Budgeting Streak: {user.get('streak_days', 14)} days
- Today's Date: {date.today().strftime('%d-%m-%Y')}

LIVE TELEMETRY GROUND TRUTH:
- Calculated Runway: {cockpit.get('runway_days', 0)} Days
- Calendar Depletion Date: {trajectory.get('runway_depletion_date', 'N/A')}
- Safe Daily Spending Allowance: ₹{cockpit.get('safe_daily_spend', 0.0):,.2f}/day
- Current Daily Burn Velocity: ₹{cockpit.get('daily_burn_rate', 0.0):,.2f}/day
- Weekend Burn Surge: +{comparison.get('weekend_surge_pct', 0.0)}% compared to weekdays
- Upcoming Exam Surge Date: around {trajectory.get('exam_date_dmy', 'mid-sems')} (Exam Defense Cushion Needed: ₹{trajectory.get('exam_surge_buffer_needed', 1800.0):,.2f})

RECENT TRANSACTIONS LEDGER (Dates in DD-MM-YYYY):
{chr(10).join(tx_summary) if tx_summary else 'No recent transactions.'}

CATEGORY BUDGET GUARDRAILS:
{chr(10).join(budget_summary) if budget_summary else 'No budgets set.'}

SAVINGS GOALS & MILESTONES:
{chr(10).join(goals_summary) if goals_summary else 'No active goals.'}

RECURRING TRANSIT & CAMPUS PASSES (Metro, Bus, Mess, 5G):
{chr(10).join(recurring_summary) if recurring_summary else 'No recurring payments.'}

AI MEMORY TRAITS LEARNED:
{json.dumps(memory or {}, indent=2)}
"""
    return context.strip()


def query_gemini_assistant(query_text, user, all_txs, budgets=None, goals=None, piggy_balance=Decimal("0.00"), current_memory=None, recurring=None):
    """
    Query Google Gemini API with real-time financial telemetry grounding.
    Falls back gracefully to the deterministic SFI engine if Gemini key is missing or call fails.
    """
    client = get_gemini_client()
    uid = user.get("id", 1)
    current_memory = dict(current_memory) if current_memory else {}

    # 1. Compute ground-truth telemetry from transactions
    expenses = [t for t in (all_txs or []) if str(t.get("transaction_type", "")).lower() == "expense"]
    incomes = [t for t in (all_txs or []) if str(t.get("transaction_type", "")).lower() == "income"]

    base_income = float(finance_engine.to_decimal(user.get("monthly_income", 0)))
    added_income = sum(float(finance_engine.to_decimal(t.get("amount", 0))) for t in incomes)
    total_income = base_income + added_income
    total_expenses = sum(float(finance_engine.to_decimal(t.get("amount", 0))) for t in expenses)

    piggy_val = float(finance_engine.to_decimal(piggy_balance))
    goals_val = sum(float(finance_engine.to_decimal(g.get("current_amount", 0))) for g in (goals or []))
    liquid_savings = piggy_val + goals_val

    cockpit = finance_engine.calculate_daily_cockpit(total_income, total_expenses, liquid_savings)
    comparison = finance_engine.compare_expenses(all_txs, user)
    trajectory = finance_engine.predict_financial_trajectory(user, total_income, total_expenses, liquid_savings, all_txs)

    telemetry = {
        "cockpit": cockpit,
        "trajectory": trajectory,
        "comparison": comparison,
    }

    # If Gemini client cannot be initialized, use fallback immediately
    if not client:
        result = finance_engine.process_chat_query(
            query=query_text,
            user=user,
            all_txs=all_txs,
            budgets=budgets,
            goals=goals,
            piggy_balance=piggy_balance,
            current_memory=current_memory,
        )
        result["is_gemini"] = False
        result["provider"] = "SpendWise Engine (Fallback)"
        return result

    # 2. Build live grounding prompt
    financial_context = build_financial_system_context(
        user=user,
        telemetry=telemetry,
        txs=all_txs,
        budgets=budgets,
        goals=goals,
        recurring=recurring,
        memory=current_memory,
    )

    system_instruction = """You are SpendWise AI, an autonomous financial intelligence copilot and mentor built for Indian college students. You are powered directly by Google Gemini API (gemini-3.5-flash-lite / gemini-3.6-flash).
Your mission is to provide empathetic, hyper-practical, and mathematically grounded financial advice tailored to Indian college students.
SpendWise features an interactive Campus Payment Gateway at /pay where students can select categories (Food, Transport, Bills, Education, Entertainment, Shopping, Health, Other) and pay via UPI or Card with real-time budget guardrail warnings.

CORE OPERATIONAL RULES:
1. Currency: Always use Indian Rupees (₹ INR).
2. Dates: Always format dates strictly as DD-MM-YYYY.
3. Tone: Encouraging, analytical, student-relatable, emoji-accented, and actionable.
4. Telemetry Grounding: Always cite the student's actual numbers (e.g. runway days, depletion date, safe daily spend, metro/bus passes, and category budgets) provided in the live context.
5. Payment Gateway: If a student asks how to pay for something or make a transaction, refer them to /pay.
6. Output Schema: You MUST output a strictly valid JSON object matching this schema:
{
  "answer": "Comprehensive Markdown response with clear bullet points, bold key numbers, and helpful advice.",
  "intent": "short intent identifier, e.g. sfi_runway, sfi_transit, sfi_budget, sfi_simulation, general_assistant",
  "data_card": {
    "type": "runway_telemetry | recurring_card | simulation_card | budget_guardrail | assistant_overview",
    "title": "Short title for the visual card",
    "metrics": [{"label": "Metric Name", "value": "Metric Value"}]
  },
  "suggested_actions": [
    {"label": "Button Text", "action": "query('Follow-up query prompt')"}
  ],
  "learned_updates": {
    "trait_name": "extracted fact about the user"
  }
}"""

    prompt = f"{financial_context}\n\nSTUDENT USER QUERY:\n\"{query_text}\"\n\nAnalyze the query in light of the student's live financial data and return the JSON response."

    last_error = None
    response_text = None
    model_used = None

    # Deduplicate while preserving order
    seen_models = set()
    candidate_models = []
    for m in FALLBACK_MODELS:
        if m and m not in seen_models:
            seen_models.add(m)
            candidate_models.append(m)

    for candidate in candidate_models:
        try:
            response = client.models.generate_content(
                model=candidate,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.6,
                    response_mime_type="application/json",
                ),
            )
            txt = response.text or ""
            if txt.strip():
                response_text = txt
                model_used = candidate
                break
        except Exception as err:
            logger.warning(f"Failed with model {candidate}: {err}")
            last_error = err
            continue

    if not response_text or not model_used:
        logger.warning(f"All Google Gemini models failed ({last_error}). Falling back to local SFI engine.")
        result = finance_engine.process_chat_query(
            query=query_text,
            user=user,
            all_txs=all_txs,
            budgets=budgets,
            goals=goals,
            piggy_balance=piggy_balance,
            current_memory=current_memory,
        )
        result["is_gemini"] = False
        result["provider"] = "SpendWise Engine (Fallback)"
        result["fallback_reason"] = str(last_error)
        return result

    try:
        clean_text = response_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            parsed = json.loads(clean_text)
        except Exception:
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(clean_text[start:end+1])
                except Exception:
                    parsed = {"answer": clean_text}
            else:
                parsed = {"answer": clean_text}

        if not isinstance(parsed, dict):
            parsed = {"answer": str(parsed)}

        answer = parsed.get("answer", "")
        intent = parsed.get("intent", "gemini_assistant")
        data_card = parsed.get("data_card")
        suggested_actions = parsed.get("suggested_actions", [])
        learned_updates_raw = parsed.get("learned_updates", {})

        learned_updates = {}
        for k, v in learned_updates_raw.items():
            if isinstance(v, (tuple, list)) and len(v) == 2:
                learned_updates[k] = (str(v[0]), float(v[1]))
            else:
                learned_updates[k] = (str(v), 0.95)

        old_count = int(current_memory.get("queries_solved_count", "12") or 12)
        new_count = old_count + 1
        learned_updates["queries_solved_count"] = (str(new_count), 1.0)

        learning_badge = {
            "key": "gemini_intelligence",
            "value": f"Solved #{new_count}",
            "text": f"✨ Powered by Google Gemini ({model_used}) • Solved Query #{new_count}",
        }

        return {
            "answer": answer,
            "intent": intent,
            "data_card": data_card,
            "suggested_actions": suggested_actions,
            "learned_updates": learned_updates,
            "learning_badge": learning_badge,
            "is_gemini": True,
            "provider": f"Google Gemini ({model_used})",
            "model_used": model_used,
        }

    except Exception as e:
        logger.warning(f"Failed to parse Gemini response ({e}). Falling back to local SFI engine.")
        result = finance_engine.process_chat_query(
            query=query_text,
            user=user,
            all_txs=all_txs,
            budgets=budgets,
            goals=goals,
            piggy_balance=piggy_balance,
            current_memory=current_memory,
        )
        result["is_gemini"] = False
        result["provider"] = "SpendWise Engine (Fallback)"
        result["fallback_reason"] = f"JSON parse error: {e}"
        return result
