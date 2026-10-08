import unittest
from decimal import Decimal
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import finance_engine
import db
import app

class TestFinanceEngine(unittest.TestCase):
    def test_dmy_formatting(self):
        # Format DD-MM-YYYY strictly
        self.assertEqual(finance_engine.format_dmy("2026-09-11"), "11-09-2026")
        self.assertEqual(finance_engine.format_dmy("11-09-2026"), "11-09-2026")
        dt = finance_engine.parse_dmy("11-09-2026")
        self.assertEqual(dt.day, 11)
        self.assertEqual(dt.month, 9)
        self.assertEqual(dt.year, 2026)

    def test_calculate_daily_cockpit(self):
        # High student income (₹40,000), expenses (₹18,000), savings (₹50,000)
        cockpit = finance_engine.calculate_daily_cockpit(40000, 18000, 50000, 85)
        self.assertEqual(cockpit["daily_burn_rate"], 600.00) # 18000/30
        self.assertTrue(cockpit["runway_days"] > 0)
        self.assertTrue(cockpit["safe_daily_spend"] > 0)
        self.assertTrue(len(cockpit["coach_message"]) > 10)

    def test_calculate_roundup_inr(self):
        self.assertEqual(finance_engine.calculate_roundup(65.00, round_to=10), Decimal("5.00"))
        self.assertEqual(finance_engine.calculate_roundup(48.00, round_to=10), Decimal("2.00"))
        self.assertEqual(finance_engine.calculate_roundup(70.00, round_to=10), Decimal("0.00"))

    def test_student_offers_catalog(self):
        offers = finance_engine.STUDENT_OFFERS
        self.assertTrue(len(offers) >= 5)
        titles = [o["title"] for o in offers]
        self.assertTrue(any("Spotify" in t for t in titles))
        self.assertTrue(any("Apple" in t for t in titles))
        self.assertTrue(any("Adobe" in t for t in titles))


    @classmethod
    def setUpClass(cls):
        import gemini_service
        app.app.config["TESTING"] = True
        cls.client = app.app.test_client()
        db.init_db()
        db.seed_demo_data()
        cls.orig_gemini_key = gemini_service.get_gemini_api_key()
        gemini_service.set_gemini_api_key("")

    @classmethod
    def tearDownClass(cls):
        import gemini_service
        if cls.orig_gemini_key:
            gemini_service.set_gemini_api_key(cls.orig_gemini_key)

    def test_dashboard_route_spendwise_and_dmy(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        # Check Brand name SPENDWISE
        self.assertIn("SPEND", html)
        self.assertIn("WISE", html)
        # Check Cockpit fields from screenshot
        self.assertIn("RUNWAY REMAINING", html)
        self.assertIn("DAILY BURN RATE", html)
        self.assertIn("SAFE DAILY SPEND", html)
        self.assertIn("Runway Advisory", html)
        # Check Bill Splitter
        self.assertIn("Campus Bill Splitter", html)
        # Check DD-MM-YYYY format in table header
        self.assertIn("Date (DD-MM-YYYY)", html)

    def test_bill_split_crud(self):
        user = db.query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        # Create a new split
        res = self.client.post("/bill-split", data={
            "title": "Weekend Swiggy Feast",
            "total_amount": "800.00",
            "split_count": "4",
            "paid_by": "You",
            "friends": "Aarav, Rohan, Priya, Amit",
            "auto_record": "1",
            "category": "Food"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        split = db.query("SELECT * FROM bill_splits WHERE user_id = %s AND title = 'Weekend Swiggy Feast'", (user["id"],), fetchone=True)
        self.assertIsNotNone(split)
        self.assertEqual(Decimal(str(split["my_share"])), Decimal("200.00"))
        # Check date is formatted as DD-MM-YYYY
        self.assertEqual(len(split["created_date"]), 10)
        self.assertEqual(split["created_date"][2], "-")

        # Settle split
        settle_res = self.client.post(f"/bill-split/{split['id']}/settle", follow_redirects=True)
        self.assertEqual(settle_res.status_code, 200)

        # Delete split
        del_res = self.client.post(f"/bill-split/{split['id']}/delete", follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)

    def test_add_transaction_with_dmy_date(self):
        response = self.client.post("/transaction", data={
            "description": "Library Stationary",
            "category": "Education",
            "amount": "85.00",
            "transaction_type": "expense",
            "transaction_date": "11-09-2026",
            "auto_roundup": "1"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        user = db.query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        tx = db.query("SELECT * FROM transactions WHERE user_id = %s AND description = 'Library Stationary'", (user["id"],), fetchone=True)
        self.assertIsNotNone(tx)
        self.assertEqual(tx["transaction_date"], "11-09-2026")

    def test_export_csv_dmy(self):
        response = self.client.get("/export/csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/csv")
        self.assertIn(b"Date (DD-MM-YYYY)", response.data)

    def test_export_pdf(self):
        response = self.client.get("/export/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertTrue(response.data.startswith(b"%PDF"))

    def test_nlp_parsing(self):
        res1 = finance_engine.parse_nlp_expense("Paid 240 Swiggy for lunch with Rohan")
        self.assertEqual(res1["amount"], Decimal("240.00"))
        self.assertEqual(res1["category"], "Food")

        res2 = finance_engine.parse_nlp_expense("80rs auto to college campus")
        self.assertEqual(res2["amount"], Decimal("80.00"))
        self.assertEqual(res2["category"], "Transport")

    def test_expense_comparison_engine(self):
        user = db.query("SELECT * FROM users ORDER BY id LIMIT 1", fetchone=True)
        txs = db.query("SELECT * FROM transactions WHERE user_id = %s", (user["id"],))
        comp = finance_engine.compare_expenses(txs, user)
        self.assertIn("recent_period_spend", comp)
        self.assertIn("prior_period_spend", comp)
        self.assertIn("weekend_avg", comp)
        self.assertIn("benchmark_comparison", comp)
        self.assertTrue(len(comp["benchmark_comparison"]) >= 4)

    def test_trajectory_prediction(self):
        user = db.query("SELECT * FROM users ORDER BY id LIMIT 1", fetchone=True)
        txs = db.query("SELECT * FROM transactions WHERE user_id = %s", (user["id"],))
        traj = finance_engine.predict_financial_trajectory(user, 38000, 15000, 20000, txs)
        self.assertIn("runway_depletion_date", traj)
        # Check DD-MM-YYYY format
        self.assertEqual(len(traj["runway_depletion_date"]), 10)
        self.assertEqual(traj["runway_depletion_date"][2], "-")
        self.assertEqual(traj["runway_depletion_date"][5], "-")
        self.assertTrue(traj["exam_surge_buffer_needed"] > 0)

    def test_chat_route_and_telemetry(self):
        response = self.client.get("/chat")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        self.assertIn("SpendWise AI Financial Assistant", html)
        self.assertIn("SFI Backend Active", html)
        self.assertIn("AI Memory", html)
        self.assertIn("Quick Queries", html)

    def test_intelligence_redirects_to_chat(self):
        response = self.client.get("/intelligence", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/chat", response.location)

        res_follow = self.client.get("/intelligence", follow_redirects=True)
        self.assertEqual(res_follow.status_code, 200)
        self.assertIn("SpendWise AI Financial Assistant", res_follow.data.decode("utf-8"))

    def test_api_chat_query_and_self_updating_memory(self):
        # Query mentioning a new goal and concern
        response = self.client.post("/api/chat/query", json={"query": "I am saving for an iPad Pro and worried about Swiggy"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("answer", data)
        self.assertIn("learning_badge", data)
        self.assertIn("memory", data)
        # Verify learned memory was updated
        self.assertEqual(data["memory"]["spending_concern"], "High spend on Swiggy")
        
        # Verify in database
        user = db.query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        mem_dict, _ = db.get_chatbot_memory(user["id"])
        self.assertEqual(mem_dict["spending_concern"], "High spend on Swiggy")

        # Verify conversation history was recorded
        history = db.get_chatbot_history(user["id"])
        self.assertTrue(any("iPad Pro" in h["query"] for h in history))

    def test_api_chat_memory_and_clear(self):
        # 1. Get memory
        get_res = self.client.get("/api/chat/memory")
        self.assertEqual(get_res.status_code, 200)
        data = get_res.get_json()
        self.assertIn("memory_dict", data)
        self.assertIn("memory_list", data)

        # 2. Reset memory
        clear_res = self.client.post("/api/chat/clear-memory")
        self.assertEqual(clear_res.status_code, 200)
        clear_data = clear_res.get_json()
        self.assertEqual(clear_data["solved_count"], "0")

    def test_sfi_quick_add_and_achieve(self):
        # 1. Quick add redirects to chat
        res = self.client.post("/sfi/quick-add", data={
            "nlp_text": "Paid 350 Swiggy biryani dinner with friends",
            "auto_roundup": "1"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("SpendWise AI Financial Assistant", res.data.decode("utf-8"))

        # 2. Achieve recommendation
        user = db.query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        rec = db.query("SELECT * FROM sfi_recommendations WHERE user_id = %s AND status = 'active' LIMIT 1", (user["id"],), fetchone=True)
        if rec:
            achieve_res = self.client.post(f"/sfi/achieve/{rec['id']}", follow_redirects=True)
            self.assertEqual(achieve_res.status_code, 200)
            updated_rec = db.query("SELECT * FROM sfi_recommendations WHERE id = %s", (rec["id"],), fetchone=True)
            self.assertEqual(updated_rec["status"], "achieved")

    def test_eduscholar_route_removed_404(self):
        res = self.client.get("/eduscholar")
        self.assertEqual(res.status_code, 404)

    def test_chat_memory_learning_demographics(self):
        # Provide student marks and income in natural query
        res = self.client.post("/api/chat/query", json={
            "query": "My marks are 88% and family income is 2.5 lakhs, how can I save 2000 this month?"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("memory", data)
        self.assertEqual(data["memory"]["marks_percent"], "88.0%")
        self.assertIn("2.5", data["memory"]["family_income_lakhs"])

        # Check DB persistent memory
        user = db.query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        mem_dict, _ = db.get_chatbot_memory(user["id"])
        self.assertEqual(mem_dict["marks_percent"], "88.0%")
        self.assertIn("2.5", mem_dict["family_income_lakhs"])
        self.assertIsNotNone(data.get("learning_badge"))

    def test_chat_financial_what_if_simulation(self):
        res = self.client.post("/api/chat/query", json={
            "query": "How can I save ₹2,000 this month?"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["intent"], "sfi_simulation")
        self.assertEqual(data["data_card"]["type"], "simulation_card")
        self.assertIn("Runway Extension", data["answer"])

    def test_transaction_crosses_category_budget_warning_not_declined(self):
        # 1. Fetch current budget for 'Food'
        user = db.query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        uid = user["id"]
        food_budget = db.query("SELECT monthly_limit FROM budgets WHERE user_id = %s AND category = 'Food'", (uid,), fetchone=True)
        limit = float(food_budget["monthly_limit"]) if food_budget else 5000.0

        # 2. Add an expense transaction that exceeds the category limit
        large_amt = limit + 500.0
        res = self.client.post("/transaction", data={
            "description": "Grand Feast Party",
            "category": "Food",
            "amount": str(large_amt),
            "transaction_type": "expense",
            "transaction_date": "11-09-2026",
            "notes": "Testing guardrail crossing"
        }, follow_redirects=True)

        # 3. Transaction must NOT be declined (HTTP 200 after redirect)
        self.assertEqual(res.status_code, 200)

        # 4. Warning stating "you are about to cross your monthly limit for this catagory!" must be present in response
        html = res.get_data(as_text=True)
        self.assertIn("you are about to cross your monthly limit for this catagory!", html)

        # 5. Verify transaction is stored in DB (not declined)
        tx = db.query(
            "SELECT * FROM transactions WHERE user_id = %s AND description = 'Grand Feast Party'",
            (uid,),
            fetchone=True
        )
        self.assertIsNotNone(tx)
        self.assertEqual(float(tx["amount"]), large_amt)

    def test_recurring_payments_dashboard_and_crud(self):
        user = db.query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        uid = user["id"]

        # 1. Dashboard displays Recurring Transit section
        dash_res = self.client.get("/")
        self.assertEqual(dash_res.status_code, 200)
        html = dash_res.get_data(as_text=True)
        self.assertIn("Recurring Transit & Campus Subscriptions", html)
        self.assertIn("recurring-section", html)

        # 2. Add custom recurring transit payment
        res = self.client.post("/recurring-payments", data={
            "title": "Namma Metro Purple Line Pass",
            "category": "Transport",
            "amount": "800.00",
            "frequency": "Monthly",
            "payment_method": "UPI / SmartCard",
            "next_due_date": "20-09-2026",
            "auto_roundup": "1",
            "notes": "Daily commute between MG Road and Campus"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        item = db.query(
            "SELECT * FROM recurring_payments WHERE user_id = %s AND title = 'Namma Metro Purple Line Pass'",
            (uid,),
            fetchone=True
        )
        self.assertIsNotNone(item)
        self.assertEqual(Decimal(str(item["amount"])), Decimal("800.00"))
        self.assertEqual(item["status"], "Active")
        self.assertEqual(item["next_due_date"], "20-09-2026")

        # 3. 1-Click Pay & Log renewal
        pay_res = self.client.post(f"/recurring-payments/{item['id']}/pay", follow_redirects=True)
        self.assertEqual(pay_res.status_code, 200)

        # Transaction created in ledger with DD-MM-YYYY date
        logged_tx = db.query(
            "SELECT * FROM transactions WHERE user_id = %s AND description = 'Recurring: Namma Metro Purple Line Pass'",
            (uid,),
            fetchone=True
        )
        self.assertIsNotNone(logged_tx)
        self.assertEqual(Decimal(str(logged_tx["amount"])), Decimal("800.00"))
        self.assertEqual(len(logged_tx["transaction_date"]), 10)
        self.assertEqual(logged_tx["transaction_date"][2], "-")

        # Spare change auto-roundup recorded
        piggy_item = db.query(
            "SELECT * FROM piggy_bank WHERE user_id = %s AND description = 'Auto Round-up: Namma Metro Purple Line Pass'",
            (uid,),
            fetchone=True
        )
        self.assertIsNotNone(piggy_item)

        # Due date advanced
        updated_item = db.query("SELECT * FROM recurring_payments WHERE id = %s", (item["id"],), fetchone=True)
        self.assertNotEqual(updated_item["next_due_date"], "20-09-2026")

        # 4. Toggle Pause / Resume
        toggle_res = self.client.post(f"/recurring-payments/{item['id']}/toggle", follow_redirects=True)
        self.assertEqual(toggle_res.status_code, 200)
        paused_item = db.query("SELECT status FROM recurring_payments WHERE id = %s", (item["id"],), fetchone=True)
        self.assertEqual(paused_item["status"], "Paused")

        # 5. Delete recurring payment
        del_res = self.client.post(f"/recurring-payments/{item['id']}/delete", follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)
        deleted_item = db.query("SELECT * FROM recurring_payments WHERE id = %s", (item["id"],), fetchone=True)
        self.assertIsNone(deleted_item)

    def test_recurring_helpers_and_metrics(self):
        # 1. Advance due date
        next_dmy = finance_engine.advance_due_date("15-09-2026", "Monthly")
        self.assertEqual(len(next_dmy), 10)
        self.assertEqual(next_dmy[2], "-")
        self.assertEqual(next_dmy[5], "-")

        # 2. Calculate due status
        due_info = finance_engine.calculate_due_status("15-09-2026")
        self.assertIn("status", due_info)
        self.assertIn("badge_class", due_info)

        # 3. Calculate recurring metrics
        sample_payments = [
            {"title": "Metro Pass", "category": "Transport", "amount": 800, "frequency": "Monthly", "status": "Active", "next_due_date": "15-09-2026"},
            {"title": "Bus Pass", "category": "Transport", "amount": 450, "frequency": "Monthly", "status": "Active", "next_due_date": "18-09-2026"},
            {"title": "Jio 5G", "category": "Bills", "amount": 299, "frequency": "Monthly", "status": "Active", "next_due_date": "25-09-2026"},
        ]
        metrics = finance_engine.calculate_recurring_metrics(sample_payments)
        self.assertEqual(metrics["active_count"], 3)
        self.assertEqual(metrics["transit_monthly"], Decimal("1250.00"))
        self.assertEqual(metrics["total_monthly"], Decimal("1549.00"))

    def test_chatbot_recurring_transit_query(self):
        res = self.client.post("/api/chat/query", json={
            "query": "When is my metro recharge due and how much do I spend on bus fare?"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["intent"], "sfi_subscriptions")
        self.assertIn("Metro", data["answer"])
        self.assertEqual(data["data_card"]["type"], "recurring_card")

    def test_gemini_status_and_key_endpoints(self):
        # 1. Get Gemini Status
        status_res = self.client.get("/api/chat/gemini-status")
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.get_json()
        self.assertIn("available", status_data)
        self.assertIn("has_key", status_data)
        self.assertIn("model", status_data)
        self.assertEqual(status_data["model"], "gemini-3.5-flash-lite")

        # 2. Set Gemini Key
        set_res = self.client.post("/api/chat/set-gemini-key", json={
            "api_key": "AIzaSyTestMockKeyForSpendWise123"
        })
        self.assertEqual(set_res.status_code, 200)
        set_data = set_res.get_json()
        self.assertTrue(set_data["success"])
        self.assertTrue(set_data["status"]["has_key"])
        self.assertIn("AIza", set_data["status"]["masked_key"])

        # 3. Clear Gemini Key
        clear_res = self.client.post("/api/chat/set-gemini-key", json={"api_key": ""})
        self.assertEqual(clear_res.status_code, 200)
        clear_data = clear_res.get_json()
        self.assertTrue(clear_data["success"])
        self.assertFalse(clear_data["status"]["has_key"])

    def test_gemini_system_context_builder(self):
        import gemini_service
        user = {"name": "Arjun Sharma", "college_name": "RV College of Engineering", "monthly_income": 35000}
        telemetry = {
            "cockpit": {"runway_days": 42, "safe_daily_spend": 650.0, "daily_burn_rate": 480.0},
            "trajectory": {"runway_depletion_date": "24-10-2026", "exam_date_dmy": "15-10-2026", "exam_surge_buffer_needed": 1800.0},
            "comparison": {"weekend_surge_pct": 28.5}
        }
        txs = [{"transaction_date": "10-09-2026", "description": "Metro Recharge", "category": "Transport", "amount": 800.0, "transaction_type": "expense"}]
        budgets = [{"category": "Food", "monthly_limit": 6000.0, "spent": 3200.0}]
        goals = [{"title": "MacBook Pro", "current_amount": 15000.0, "target_amount": 85000.0, "target_date": "31-12-2026"}]
        recurring = [{"title": "Namma Metro Pass", "category": "Transport", "amount": 800.0, "frequency": "Monthly", "next_due_date": "15-09-2026", "payment_method": "UPI", "status": "Active"}]
        memory = {"living_situation": "hostel"}

        context = gemini_service.build_financial_system_context(user, telemetry, txs, budgets, goals, recurring, memory)
        self.assertIn("Arjun Sharma", context)
        self.assertIn("42 Days", context)
        self.assertIn("₹650.00/day", context)
        self.assertIn("Metro Recharge", context)
        self.assertIn("Namma Metro Pass", context)
        self.assertIn("hostel", context)
        self.assertIn("DD-MM-YYYY", context)

    def test_gemini_query_assistant_fallback(self):
        import gemini_service
        # Clear any key to test deterministic fallback
        gemini_service.set_gemini_api_key("")
        res = self.client.post("/api/chat/query", json={"query": "When will my money run out?"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("answer", data)
        self.assertFalse(data["is_gemini"])
        self.assertIn("depletion", data["answer"].lower())

    def test_chat_page_renders_gemini_ui(self):
        res = self.client.get("/chat")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Google Gemini", html)
        self.assertIn("geminiModal", html)
        self.assertIn("Google Gemini Flash", html)

    def test_payment_gateway_page_renders(self):
        res = self.client.get("/pay")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Campus Payment Gateway", html)
        self.assertIn("Food", html)
        self.assertIn("Transport", html)
        self.assertIn("Scan & Pay via UPI", html)
        self.assertIn("Quick Campus Presets", html)

    def test_payment_gateway_check_budget_api(self):
        # 1. Normal spending within limit
        res_normal = self.client.get("/api/pay/check-budget?category=Food&amount=20")
        self.assertEqual(res_normal.status_code, 200)
        data_normal = res_normal.get_json()
        self.assertEqual(data_normal["category"], "Food")
        self.assertFalse(data_normal["warning"])

        # 2. Crossing limit triggers warning
        res_over = self.client.get("/api/pay/check-budget?category=Food&amount=999999")
        self.assertEqual(res_over.status_code, 200)
        data_over = res_over.get_json()
        self.assertTrue(data_over["warning"])
        self.assertIn("you are about to cross your monthly limit for this catagory!", data_over["warning_message"])

    def test_payment_gateway_process_successful(self):
        user = db.query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        res = self.client.post("/api/pay/process", json={
            "merchant": "Campus Canteen Fresh Meal",
            "amount": "145.00",
            "category": "Food",
            "payment_method": "UPI",
            "auto_roundup": True
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["merchant"], "Campus Canteen Fresh Meal")
        self.assertEqual(data["category"], "Food")
        self.assertEqual(data["amount"], 145.00)
        self.assertTrue(data["txn_id"].startswith("TXN-IN-"))
        self.assertEqual(len(data["date"]), 10)
        self.assertEqual(data["date"][2], "-")
        self.assertEqual(data["date"][5], "-")

        # Verify transaction logged in DB
        tx = db.query(
            "SELECT * FROM transactions WHERE user_id = %s AND description = 'Campus Canteen Fresh Meal'",
            (user["id"],),
            fetchone=True
        )
        self.assertIsNotNone(tx)
        self.assertEqual(float(tx["amount"]), 145.00)
        self.assertEqual(tx["category"], "Food")
        self.assertEqual(len(tx["transaction_date"]), 10)

    def test_payment_gateway_roundup_into_piggy_bank(self):
        user = db.query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        res = self.client.post("/api/pay/process", json={
            "merchant": "Bookstore Notebook",
            "amount": "63.00",
            "category": "Education",
            "payment_method": "Card",
            "auto_roundup": True
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["roundup_saved"], 7.00)

        # Verify Piggy Bank record
        piggy_rec = db.query(
            "SELECT * FROM piggy_bank WHERE user_id = %s AND description LIKE '%Bookstore Notebook%'",
            (user["id"],),
            fetchone=True
        )
        self.assertIsNotNone(piggy_rec)
        self.assertEqual(float(piggy_rec["amount"]), 7.00)

    def test_payment_gateway_warning_not_declined(self):
        user = db.query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
        uid = user["id"]
        food_b = db.query("SELECT monthly_limit FROM budgets WHERE user_id = %s AND category = 'Food'", (uid,), fetchone=True)
        limit = float(food_b["monthly_limit"]) if food_b else 5000.0

        # Attempt payment that crosses the limit
        excess_amt = limit + 1000.0
        res = self.client.post("/api/pay/process", json={
            "merchant": "Weekend Gourmet Feast",
            "amount": str(excess_amt),
            "category": "Food",
            "payment_method": "UPI",
            "auto_roundup": False
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        # Must be successful (NOT declined)
        self.assertTrue(data["success"])
        # Warning flag and exact warning message must be present
        self.assertTrue(data["budget_warning"])
        self.assertEqual(data["warning_message"], "you are about to cross your monthly limit for this catagory!")

        # Verify logged in DB
        tx = db.query(
            "SELECT * FROM transactions WHERE user_id = %s AND description = 'Weekend Gourmet Feast'",
            (uid,),
            fetchone=True
        )
        self.assertIsNotNone(tx)
        self.assertEqual(float(tx["amount"]), excess_amt)


if __name__ == "__main__":
    unittest.main()


