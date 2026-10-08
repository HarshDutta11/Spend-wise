import os
import json
import sqlite3
from decimal import Decimal
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

sqlite3.register_adapter(Decimal, lambda d: float(d))
sqlite3.register_converter("NUMERIC", lambda b: Decimal(b.decode('utf-8')) if b else Decimal("0.00"))

DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join(os.path.dirname(__file__), "runway.db"))

def get_db_connection():
    if DB_TYPE == "mysql":
        try:
            import mysql.connector
            return mysql.connector.connect(
                host=os.getenv("MYSQL_HOST", "localhost"),
                port=int(os.getenv("MYSQL_PORT", "3306")),
                user=os.getenv("MYSQL_USER", "root"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                database=os.getenv("MYSQL_DATABASE", "student_finance"),
            )
        except Exception as e:
            conn = sqlite3.connect(SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            return conn
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def query(sql, values=(), fetchone=False, commit=False):
    connection = get_db_connection()
    is_sqlite = isinstance(connection, sqlite3.Connection)
    
    if is_sqlite:
        sql = sql.replace("%s", "?")
        if "ON DUPLICATE KEY UPDATE" in sql:
            sql = sql.replace("ON DUPLICATE KEY UPDATE monthly_limit = VALUES(monthly_limit)",
                              "ON CONFLICT(user_id, category) DO UPDATE SET monthly_limit = excluded.monthly_limit")
        sanitized_values = tuple(float(v) if isinstance(v, Decimal) else v for v in values)
        cursor = connection.cursor()
    else:
        sanitized_values = values
        cursor = connection.cursor(dictionary=True)

    cursor.execute(sql, sanitized_values)
    if fetchone:
        row = cursor.fetchone()
        result = dict(row) if (is_sqlite and row) else row
    else:
        rows = cursor.fetchall()
        result = [dict(r) for r in rows] if is_sqlite else rows

    if commit:
        connection.commit()
    cursor.close()
    connection.close()
    return result

def init_db():
    connection = get_db_connection()
    is_sqlite = isinstance(connection, sqlite3.Connection)
    cursor = connection.cursor()

    if is_sqlite:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'Student',
            college_name TEXT NOT NULL DEFAULT 'Engineering College',
            monthly_income NUMERIC NOT NULL DEFAULT 0,
            avatar TEXT DEFAULT '🎓',
            streak_days INTEGER DEFAULT 14,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            amount NUMERIC NOT NULL,
            transaction_type TEXT NOT NULL,
            transaction_date TEXT NOT NULL, -- strictly DD-MM-YYYY
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            monthly_limit NUMERIC NOT NULL,
            UNIQUE(user_id, category),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS savings_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            target_amount NUMERIC NOT NULL,
            current_amount NUMERIC NOT NULL DEFAULT 0,
            target_date TEXT NOT NULL, -- strictly DD-MM-YYYY
            icon TEXT DEFAULT '🎯',
            color TEXT DEFAULT 'indigo',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS piggy_bank (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            amount NUMERIC NOT NULL,
            description TEXT NOT NULL,
            action_date TEXT NOT NULL, -- strictly DD-MM-YYYY
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_code TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            icon TEXT NOT NULL,
            unlocked_at TEXT NOT NULL, -- strictly DD-MM-YYYY
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_splits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            total_amount NUMERIC NOT NULL,
            paid_by TEXT NOT NULL DEFAULT 'You',
            my_share NUMERIC NOT NULL,
            split_count INTEGER NOT NULL DEFAULT 2,
            friends TEXT NOT NULL,
            settled INTEGER NOT NULL DEFAULT 0,
            created_date TEXT NOT NULL, -- strictly DD-MM-YYYY
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sfi_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            rec_key TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            monthly_savings NUMERIC NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            achieved_at TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sfi_savings_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            amount_saved NUMERIC NOT NULL,
            source TEXT NOT NULL,
            achieved_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scholarships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            provider TEXT NOT NULL,
            award_amount_inr NUMERIC NOT NULL,
            award_period TEXT NOT NULL,
            deadline_dmy TEXT NOT NULL,
            description TEXT NOT NULL,
            min_marks_percent NUMERIC NOT NULL DEFAULT 60.0,
            max_family_income_lakhs NUMERIC NOT NULL DEFAULT 8.0,
            eligible_degree TEXT NOT NULL,
            eligible_year TEXT NOT NULL,
            gender TEXT NOT NULL DEFAULT 'All',
            category_caste TEXT NOT NULL DEFAULT 'All',
            official_portal_url TEXT NOT NULL,
            claim_process_steps TEXT NOT NULL,
            required_documents TEXT NOT NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_scholarship_tracker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scholarship_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Bookmarked',
            application_date_dmy TEXT DEFAULT '',
            disbursed_amount_inr NUMERIC DEFAULT 0,
            notes TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (scholarship_id) REFERENCES scholarships (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            response TEXT NOT NULL,
            intent TEXT NOT NULL DEFAULT 'general',
            data_card TEXT DEFAULT '',
            actions_json TEXT DEFAULT '[]',
            is_solved INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chatbot_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            memory_key TEXT NOT NULL,
            memory_value TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, memory_key),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurring_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            amount NUMERIC NOT NULL,
            frequency TEXT NOT NULL DEFAULT 'Monthly',
            payment_method TEXT NOT NULL DEFAULT 'UPI / SmartCard',
            next_due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            auto_roundup INTEGER NOT NULL DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL DEFAULT 'Student',
            college_name VARCHAR(255) NOT NULL DEFAULT 'Engineering College',
            monthly_income DECIMAL(12,2) NOT NULL DEFAULT 0,
            avatar VARCHAR(50) DEFAULT '🎓',
            streak_days INT DEFAULT 14,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            description VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL,
            amount DECIMAL(12,2) NOT NULL,
            transaction_type VARCHAR(50) NOT NULL,
            transaction_date VARCHAR(20) NOT NULL,
            notes VARCHAR(255) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            category VARCHAR(100) NOT NULL,
            monthly_limit DECIMAL(12,2) NOT NULL,
            UNIQUE KEY unique_user_cat (user_id, category),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS savings_goals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            target_amount DECIMAL(12,2) NOT NULL,
            current_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
            target_date VARCHAR(20) NOT NULL,
            icon VARCHAR(50) DEFAULT '🎯',
            color VARCHAR(50) DEFAULT 'indigo',
            status VARCHAR(50) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS piggy_bank (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            action_type VARCHAR(50) NOT NULL,
            amount DECIMAL(12,2) NOT NULL,
            description VARCHAR(255) NOT NULL,
            action_date VARCHAR(20) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            badge_code VARCHAR(100) NOT NULL UNIQUE,
            title VARCHAR(255) NOT NULL,
            description VARCHAR(255) NOT NULL,
            icon VARCHAR(50) NOT NULL,
            unlocked_at VARCHAR(20) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_splits (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            total_amount DECIMAL(12,2) NOT NULL,
            paid_by VARCHAR(100) NOT NULL DEFAULT 'You',
            my_share DECIMAL(12,2) NOT NULL,
            split_count INT NOT NULL DEFAULT 2,
            friends VARCHAR(255) NOT NULL,
            settled INT NOT NULL DEFAULT 0,
            created_date VARCHAR(20) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sfi_recommendations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            rec_key VARCHAR(100) NOT NULL UNIQUE,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            category VARCHAR(100) NOT NULL,
            monthly_savings DECIMAL(12,2) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            achieved_at VARCHAR(20) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sfi_savings_ledger (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            amount_saved DECIMAL(12,2) NOT NULL,
            source VARCHAR(100) NOT NULL,
            achieved_date VARCHAR(20) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scholarships (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            provider VARCHAR(255) NOT NULL,
            award_amount_inr DECIMAL(12,2) NOT NULL,
            award_period VARCHAR(100) NOT NULL,
            deadline_dmy VARCHAR(20) NOT NULL,
            description TEXT NOT NULL,
            min_marks_percent DECIMAL(5,2) NOT NULL DEFAULT 60.00,
            max_family_income_lakhs DECIMAL(5,2) NOT NULL DEFAULT 8.00,
            eligible_degree VARCHAR(100) NOT NULL,
            eligible_year VARCHAR(100) NOT NULL,
            gender VARCHAR(50) NOT NULL DEFAULT 'All',
            category_caste VARCHAR(100) NOT NULL DEFAULT 'All',
            official_portal_url VARCHAR(255) NOT NULL,
            claim_process_steps TEXT NOT NULL,
            required_documents TEXT NOT NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_scholarship_tracker (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            scholarship_id INT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'Bookmarked',
            application_date_dmy VARCHAR(20) DEFAULT '',
            disbursed_amount_inr DECIMAL(12,2) DEFAULT 0,
            notes TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (scholarship_id) REFERENCES scholarships (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            query TEXT NOT NULL,
            response TEXT NOT NULL,
            intent VARCHAR(100) NOT NULL DEFAULT 'general',
            data_card TEXT DEFAULT NULL,
            actions_json TEXT DEFAULT NULL,
            is_solved INT NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chatbot_memory (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            memory_key VARCHAR(100) NOT NULL,
            memory_value TEXT NOT NULL,
            confidence DECIMAL(3,2) NOT NULL DEFAULT 1.00,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_user_mem (user_id, memory_key),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurring_payments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL,
            amount DECIMAL(12,2) NOT NULL,
            frequency VARCHAR(50) NOT NULL DEFAULT 'Monthly',
            payment_method VARCHAR(100) NOT NULL DEFAULT 'UPI / SmartCard',
            next_due_date VARCHAR(20) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'Active',
            auto_roundup INT NOT NULL DEFAULT 1,
            notes VARCHAR(255) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)

    connection.commit()
    cursor.close()
    connection.close()

    seed_scholarships()

    user = query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
    if not user:
        today_dmy = date.today().strftime("%d-%m-%Y")
        query("INSERT INTO users (name, college_name, monthly_income, streak_days) VALUES (%s, %s, %s, %s)",
              ("Student", "Engineering College", 38000.00, 14), commit=True)
        seed_demo_data()

def seed_demo_data():
    user = query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
    if not user:
        query("INSERT INTO users (name, college_name, monthly_income, streak_days) VALUES (%s, %s, %s, %s)",
              ("Student", "Engineering College", 38000.00, 14), commit=True)
        user = query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
    
    uid = user["id"]
    query("UPDATE users SET name = %s, college_name = %s, monthly_income = %s, streak_days = %s WHERE id = %s",
          ("Student", "Engineering College", 38000.00, 14, uid), commit=True)

    query("DELETE FROM transactions WHERE user_id = %s", (uid,), commit=True)
    query("DELETE FROM budgets WHERE user_id = %s", (uid,), commit=True)
    query("DELETE FROM savings_goals WHERE user_id = %s", (uid,), commit=True)
    query("DELETE FROM piggy_bank WHERE user_id = %s", (uid,), commit=True)
    query("DELETE FROM badges WHERE user_id = %s", (uid,), commit=True)
    query("DELETE FROM bill_splits WHERE user_id = %s", (uid,), commit=True)
    query("DELETE FROM sfi_recommendations WHERE user_id = %s", (uid,), commit=True)
    query("DELETE FROM sfi_savings_ledger WHERE user_id = %s", (uid,), commit=True)
    query("DELETE FROM chatbot_conversations WHERE user_id = %s", (uid,), commit=True)
    query("DELETE FROM chatbot_memory WHERE user_id = %s", (uid,), commit=True)
    query("DELETE FROM recurring_payments WHERE user_id = %s", (uid,), commit=True)

    today = date.today()

    # All dates strictly formatted in DD-MM-YYYY
    sample_txs = [
        ("AI Fellowship Research Stipend", "Education", 25000.00, "income", (today - timedelta(days=2)).strftime("%d-%m-%Y"), "Direct college deposit"),
        ("Freelance Full-Stack Deliverable", "Other", 13000.00, "income", (today - timedelta(days=12)).strftime("%d-%m-%Y"), "Client milestone payment via UPI"),
        ("PG / Student Flat Rent Share", "Bills", 9500.00, "expense", (today - timedelta(days=10)).strftime("%d-%m-%Y"), "Split with flatmates"),
        ("Blinkit & Fresh Groceries", "Food", 1420.00, "expense", (today - timedelta(days=1)).strftime("%d-%m-%Y"), "Weekly cook prep supplies"),
        ("Evening Chai & Samosa Break", "Food", 65.00, "expense", (today - timedelta(days=1)).strftime("%d-%m-%Y"), "Study group snacks"),
        ("Swiggy Weekend Biryani Order", "Food", 265.00, "expense", (today - timedelta(days=5)).strftime("%d-%m-%Y"), "Hackathon team dinner"),
        ("Metro Smart Card Recharge", "Transport", 800.00, "expense", (today - timedelta(days=9)).strftime("%d-%m-%Y"), "Monthly commute pass"),
        ("Rapido Bike Ride to Campus", "Transport", 48.00, "expense", (today - timedelta(days=4)).strftime("%d-%m-%Y"), "Morning rush to lab"),
        ("Spotify Premium Student", "Entertainment", 69.00, "expense", (today - timedelta(days=14)).strftime("%d-%m-%Y"), "Official student discount plan"),
        ("YouTube Premium Student Plan", "Entertainment", 89.00, "expense", (today - timedelta(days=3)).strftime("%d-%m-%Y"), "Student ad-free plan"),
        ("System Design & Algorithms Book", "Education", 650.00, "expense", (today - timedelta(days=8)).strftime("%d-%m-%Y"), "Campus bookstore"),
        ("Fitness & Badminton Pass", "Health", 1200.00, "expense", (today - timedelta(days=11)).strftime("%d-%m-%Y"), "Campus rec membership"),
        ("Flipkart Winter Sale Hoodie", "Shopping", 1150.00, "expense", (today - timedelta(days=6)).strftime("%d-%m-%Y"), "College fest outfit"),
    ]

    for desc, cat, amt, ttype, tdate, notes in sample_txs:
        query("""INSERT INTO transactions (user_id, description, category, amount, transaction_type, transaction_date, notes)
                 VALUES (%s, %s, %s, %s, %s, %s, %s)""",
              (uid, desc, cat, amt, ttype, tdate, notes), commit=True)

    budgets = [
        ("Food", 4500.00),
        ("Bills", 10000.00),
        ("Transport", 1500.00),
        ("Education", 2500.00),
        ("Entertainment", 1200.00),
        ("Shopping", 2000.00),
        ("Health", 1500.00),
        ("Other", 1500.00),
    ]
    for cat, limit in budgets:
        query("""INSERT INTO budgets (user_id, category, monthly_limit) VALUES (%s, %s, %s)
                 ON DUPLICATE KEY UPDATE monthly_limit = VALUES(monthly_limit)""",
              (uid, cat, limit), commit=True)

    # Goals with target dates in DD-MM-YYYY
    goals = [
        ("Apple M3 MacBook Air", 95000.00, 62000.00, (today + timedelta(days=60)).strftime("%d-%m-%Y"), "💻", "indigo"),
        ("Emergency Cushion (3 Months)", 45000.00, 32000.00, (today + timedelta(days=90)).strftime("%d-%m-%Y"), "🛡️", "emerald"),
        ("Goa National Hackathon Trip", 12000.00, 7800.00, (today + timedelta(days=35)).strftime("%d-%m-%Y"), "✈️", "amber"),
    ]
    for title, target, curr, tdate, icon, color in goals:
        query("""INSERT INTO savings_goals (user_id, title, target_amount, current_amount, target_date, icon, color)
                 VALUES (%s, %s, %s, %s, %s, %s, %s)""",
              (uid, title, target, curr, tdate, icon, color), commit=True)

    # Piggy Bank with action dates in DD-MM-YYYY
    piggy_entries = [
        ("deposit", 2500.00, "Monthly Stipend Pocket Stash", (today - timedelta(days=7)).strftime("%d-%m-%Y")),
        ("roundup", 5.00, "Round-up: Chai & Samosa (₹65 -> ₹70)", (today - timedelta(days=1)).strftime("%d-%m-%Y")),
        ("roundup", 5.00, "Round-up: Swiggy Biryani (₹265 -> ₹270)", (today - timedelta(days=5)).strftime("%d-%m-%Y")),
        ("roundup", 2.00, "Round-up: Rapido Bike (₹48 -> ₹50)", (today - timedelta(days=4)).strftime("%d-%m-%Y")),
        ("roundup", 1.00, "Round-up: Spotify Student (₹69 -> ₹70)", (today - timedelta(days=14)).strftime("%d-%m-%Y")),
        ("roundup", 11.00, "Round-up: YouTube Student (₹89 -> ₹100)", (today - timedelta(days=3)).strftime("%d-%m-%Y")),
        ("deposit", 1000.00, "Freelance Milestone Reward Stash", (today - timedelta(days=3)).strftime("%d-%m-%Y")),
    ]
    for atype, amt, desc, adate in piggy_entries:
        query("""INSERT INTO piggy_bank (user_id, action_type, amount, description, action_date)
                 VALUES (%s, %s, %s, %s, %s)""",
              (uid, atype, amt, desc, adate), commit=True)

    # Badges with unlock dates in DD-MM-YYYY
    badges = [
        ("first_save", "First Rupee Stashed", "Made your first deposit into the Digital Piggy Bank", "🐷", (today - timedelta(days=7)).strftime("%d-%m-%Y")),
        ("roundup_hero", "UPI Micro-Saver", "Stashed spare change automatically on non-round UPI transactions", "🪙", (today - timedelta(days=6)).strftime("%d-%m-%Y")),
        ("goal_setter", "Visionary Saver", "Created 3 milestone savings goals with velocity forecasting", "🎯", (today - timedelta(days=5)).strftime("%d-%m-%Y")),
        ("budget_boss", "Runway Guardian", "Maintained discipline within student category budgets", "🛡️", (today - timedelta(days=2)).strftime("%d-%m-%Y")),
    ]
    for bcode, title, desc, icon, udate in badges:
        query("""INSERT INTO badges (user_id, badge_code, title, description, icon, unlocked_at)
                 VALUES (%s, %s, %s, %s, %s, %s)""",
              (uid, bcode, title, desc, icon, udate), commit=True)

    # Seed Bill Splits with DD-MM-YYYY dates
    splits = [
        ("Hostel Swiggy Pizza Feast", 960.00, "You", 240.00, 4, "Rohan (₹240), Priya (₹240), Amit (₹240)", 0, (today - timedelta(days=2)).strftime("%d-%m-%Y")),
        ("Hackathon Late Night Cab", 380.00, "Rohan", 190.00, 2, "You (₹190), Rohan (₹190)", 0, (today - timedelta(days=4)).strftime("%d-%m-%Y")),
    ]
    for title, tot, pby, mshare, scount, frnds, stl, cdate in splits:
        query("""INSERT INTO bill_splits (user_id, title, total_amount, paid_by, my_share, split_count, friends, settled, created_date)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
              (uid, title, tot, pby, mshare, scount, frnds, stl, cdate), commit=True)

    # Seed SFI Recommendations
    recs = [
        ("rec_spotify", "Claim Spotify Student Verification", "Switch to verified student rate ₹69/mo (regular ₹119/mo)", "Entertainment", 600.00, "achieved", (today - timedelta(days=5)).strftime("%d-%m-%Y")),
        ("rec_mess_cut", "Hostel Mess Skip Arbitrage", "Avail official mess leave rebate when ordering Swiggy/dining out", "Food", 1200.00, "active", ""),
        ("rec_metro_pass", "Switch to Monthly Metro Card", "Replace daily Rapido/auto rides with subsidized student metro pass", "Transport", 800.00, "active", ""),
        ("rec_github_pack", "Unlock GitHub Student Developer Pack", "Claim ₹1.5L+ in free cloud servers, Copilot & domains", "Education", 2500.00, "achieved", (today - timedelta(days=12)).strftime("%d-%m-%Y")),
        ("rec_chai_roundup", "Plug Micro-Chai Leakage", "Automate round-ups on campus canteen tea & samosa breaks", "Food", 450.00, "active", ""),
    ]
    for rkey, rtitle, rdesc, rcat, rsav, rstatus, rach in recs:
        query("""INSERT INTO sfi_recommendations (user_id, rec_key, title, description, category, monthly_savings, status, achieved_at)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
              (uid, rkey, rtitle, rdesc, rcat, rsav, rstatus, rach), commit=True)

    # Seed SFI Savings Ledger
    savings_items = [
        ("Spotify Student Verification", 600.00, "Student Perks Radar", (today - timedelta(days=5)).strftime("%d-%m-%Y")),
        ("GitHub Developer Pack Cloud Credits", 2500.00, "Institutional Discount", (today - timedelta(days=12)).strftime("%d-%m-%Y")),
    ]
    for stitle, samt, ssrc, sdate in savings_items:
        query("""INSERT INTO sfi_savings_ledger (user_id, title, amount_saved, source, achieved_date)
                 VALUES (%s, %s, %s, %s, %s)""",
              (uid, stitle, samt, ssrc, sdate), commit=True)

    # Seed Recurring Transit, Passes & Campus Subscriptions
    recurring_samples = [
        ("Namma Metro Smartcard Auto-Recharge", "Transport", 800.00, "Monthly", "UPI / SmartCard", (today + timedelta(days=5)).strftime("%d-%m-%Y"), "Active", 1, "Purple & Green Line Daily Commute"),
        ("Campus & City Bus Pass", "Transport", 450.00, "Monthly", "Cash / Counter", (today + timedelta(days=11)).strftime("%d-%m-%Y"), "Active", 1, "Route 42A Student Pass"),
        ("Jio Student 5G Unlimited Pack", "Bills", 299.00, "Monthly", "UPI / Auto-Debit", (today + timedelta(days=16)).strftime("%d-%m-%Y"), "Active", 1, "2GB/Day + Unlimited 5G Data"),
        ("Hostel Mess Dining Dues", "Food", 3200.00, "Monthly", "NetBanking / UPI", (today + timedelta(days=3)).strftime("%d-%m-%Y"), "Active", 0, "Hostel Block-B Mess Subscription"),
        ("Spotify Premium Student", "Entertainment", 69.00, "Monthly", "UPI / Auto-Debit", (today + timedelta(days=21)).strftime("%d-%m-%Y"), "Active", 1, "Verified Student Discount Plan"),
    ]
    for title, cat, amt, freq, pmethod, ndate, status, aup, notes in recurring_samples:
        query("""INSERT INTO recurring_payments (user_id, title, category, amount, frequency, payment_method, next_due_date, status, auto_roundup, notes)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
              (uid, title, cat, amt, freq, pmethod, ndate, status, aup, notes), commit=True)

    # Seed baseline student traits in chatbot memory
    initial_memories = [
        ("student_name", "Student", 1.0),
        ("college", "Engineering College", 1.0),
        ("academic_stream", "Computer Science & Engineering (B.Tech)", 1.0),
        ("living_situation", "PG Flat with 3 flatmates", 0.95),
        ("target_goal", "Apple M3 MacBook Air (Coding & ML)", 1.0),
        ("spending_concern", "Weekend food delivery surges (Swiggy/Zomato)", 0.9),
        ("runway_safety_cushion", "Maintain 30+ days liquid cushion", 0.85),
        ("queries_solved_count", "12", 1.0),
    ]
    for m_key, m_val, conf in initial_memories:
        update_chatbot_memory(uid, m_key, m_val, conf)

    # Seed sample conversations showing real SFI intelligence
    initial_chats = [
        (
            "What is my current runway and daily spending speed?",
            "Your runway is healthy at **42 Days** with a safe spend limit of **₹612.00/day**! At your current burn rate of **₹512.00/day**, your funds comfortably cover the semester. We calculated an exact runway date with an extra **2.2x buffer** for upcoming exam weeks.",
            "sfi_runway",
            {"burn_rate": "₹512.00/day", "safe_daily": "₹612.00/day", "runway_days": 42, "status": "Secure"},
            ["Check Food Budget", "View Exam Buffer", "Simulate ₹500 Savings"],
            1
        ),
        (
            "How can I cut down my food expenses without starving?",
            "Your weekend food orders spike by **+134%** compared to weekdays. By taking advantage of the **Hostel Mess Skip Rebate** (saving ~₹1,200/mo) and batch ordering groceries on Blinkit, you can save **₹2,400 monthly** towards your *Apple M3 MacBook Air* goal.",
            "sfi_mess_rebate",
            {"potential_savings": "₹2,400/mo", "action": "Mess Rebate + Bulk Groceries", "impact": "Adds 6.2 days to runway"},
            ["Mess Leave Process", "Food vs Transport", "Safe Daily Spend"],
            1
        )
    ]
    for q, r, intent, dc, acts, sol in initial_chats:
        save_chatbot_interaction(uid, q, r, intent, dc, acts, sol)


def seed_scholarships():
    existing = query("SELECT count(*) as cnt FROM scholarships", fetchone=True)
    count = existing["cnt"] if existing else 0
    if count > 0:
        return

    scholarships = [
        (
            "Reliance Foundation Undergraduate Scholarship",
            "Reliance Foundation",
            200000.00,
            "Across 4-year degree (₹50,000/yr)",
            "15-10-2026",
            "Premier merit-cum-means scholarship supporting meritorious undergraduate students with holistic development grants and mentoring throughout their degree.",
            60.0,
            15.0,
            "Engineering, MBBS, B.Sc, B.Com, BA",
            "1st Year",
            "All",
            "All",
            "https://www.scholarships.reliancefoundation.org",
            json.dumps([
                "Step 1: Verify eligibility — Enrolled in 1st year full-time undergraduate degree with min 60% in Class 12.",
                "Step 2: Submit online application on the official Reliance Foundation Scholarship portal with personal and household income details.",
                "Step 3: Complete mandatory 60-minute online proctored aptitude test (verbal, analytical & numerical sections).",
                "Step 4: Upload scanned Class 10/12 marksheets, college bonafide enrollment certificate, and parent's income proof/ITR.",
                "Step 5: Merit list selection followed by direct bank transfer of ₹50,000 annually into student's Aadhaar-linked savings account."
            ]),
            json.dumps([
                "Class 10th & 12th Board passing marksheets",
                "Official college bonafide certificate or current semester fee receipt",
                "Family Income Certificate issued by competent authority (Tehsildar/SDM) or parent's latest ITR",
                "Student's Aadhaar Card (linked to mobile & bank)",
                "Cancelled bank cheque or copy of student bank passbook"
            ])
        ),
        (
            "Central Sector Scheme of Scholarships (CSSS / NSP)",
            "Ministry of Education, Govt of India",
            12000.00,
            "Annual grant (₹12,000 UG / ₹20,000 PG)",
            "31-10-2026",
            "Centrally funded scholarship for students who scored above 80th percentile in their respective Class 12 state/central education boards.",
            80.0,
            4.5,
            "All General & Professional Degrees",
            "1st Year",
            "All",
            "All",
            "https://scholarships.gov.in",
            json.dumps([
                "Step 1: Check board-wise cutoff percentile (must be above 80th percentile in 12th board).",
                "Step 2: Complete One-Time Registration (OTR) on the National Scholarship Portal (NSP) using student Aadhaar.",
                "Step 3: Fill the CSSS scheme application form and choose your registered higher educational institute.",
                "Step 4: Submit physical documents to your College Scholarship Nodal Officer for electronic verification.",
                "Step 5: Ministry approves list; funds disbursed directly via Public Financial Management System (PFMS) Direct Benefit Transfer (DBT)."
            ]),
            json.dumps([
                "Class 12th Marks Card and Board Passing Certificate",
                "Competent Authority Family Income Certificate (< ₹4.5 Lakh/annum)",
                "College Admission Fee Challan / Bonafide Certificate",
                "Bank Account Passbook (Aadhaar Seeded & Active NPCI mapper)",
                "Domicile / State Residence Certificate"
            ])
        ),
        (
            "AICTE Pragati Scholarship for Girls",
            "All India Council for Technical Education (AICTE)",
            50000.00,
            "Per Year (Total ₹2,00,000 for degree)",
            "31-12-2026",
            "Flagship national scheme empowering meritorious female students entering technical degree programs in AICTE-approved colleges.",
            60.0,
            8.0,
            "Engineering, B.Tech, B.Arch, Pharmacy",
            "1st Year",
            "Female Only",
            "All",
            "https://scholarships.gov.in",
            json.dumps([
                "Step 1: Obtain admission to 1st year of technical degree in an AICTE approved college through centralized counseling or merit.",
                "Step 2: Register on NSP (scholarships.gov.in) under the AICTE Pragati Scheme tab.",
                "Step 3: Upload Class 10, 12, and CET/JEE rank cards along with father/mother income certificate (< ₹8 Lakh).",
                "Step 4: Institute nodal officer verifies student admission and AICTE approval status.",
                "Step 5: ₹50,000 lump sum transferred annually to cover college fees, books, and laptop/equipment."
            ]),
            json.dumps([
                "Class 10th & 12th Marksheets",
                "CET / JEE Entrance Scorecard & Centralized Allotment Letter",
                "Parental Annual Income Certificate (< ₹8 Lakh) from Revenue Officer",
                "Tuition Fee Receipt for current academic year",
                "AICTE College Approval Reference Number"
            ])
        ),
        (
            "Tata Capital Pankh Scholarship Programme",
            "Tata Capital",
            50000.00,
            "Per Year (Up to 80% tuition waiver)",
            "15-11-2026",
            "CSR initiative providing financial assistance to undergraduate students from economically weaker sections to prevent academic dropouts.",
            60.0,
            2.5,
            "B.Tech, B.Com, B.Sc, BCA, BBA",
            "All Years",
            "All",
            "All",
            "https://www.buddy4study.com/page/tata-capital-pankh-scholarship-programme",
            json.dumps([
                "Step 1: Confirm minimum 60% aggregate in the preceding academic qualifying examination.",
                "Step 2: Apply via the Tata Capital Pankh portal / Buddy4Study matching engine.",
                "Step 3: Submit family income certificate (< ₹2.5 Lakhs) and current university admission receipt.",
                "Step 4: Shortlisted candidates undergo telephone background review by Tata CSR evaluation committee.",
                "Step 5: Scholarship award cheque/NEFT sanctioned to college fee account or student bank account."
            ]),
            json.dumps([
                "Previous semester / Class 12 marksheet",
                "Valid Government-issued Family Income Proof (Tehsildar/SDM)",
                "College Student ID card & Bonafide letter",
                "Current year college fee breakdown and receipt",
                "Student Bank Passbook or Bank Statement"
            ])
        ),
        (
            "Kotak Kanya Scholarship",
            "Kotak Education Foundation",
            150000.00,
            "Per Year (Total up to ₹6,00,000)",
            "30-09-2026",
            "High-impact scholarship supporting exceptional girl students pursuing professional degrees in top NIRF/NAAC accredited institutions across India.",
            85.0,
            6.0,
            "Engineering, MBBS, Architecture, Integrated LLB",
            "1st Year",
            "Female Only",
            "All",
            "https://kotakeducation.org/kotak-kanya-scholarship/",
            json.dumps([
                "Step 1: Check eligibility — Female candidate with >= 85% marks in Class 12 Board exams & annual family income <= ₹6 Lakhs.",
                "Step 2: Fill detailed profile on Kotak Education Foundation portal with academic credentials and aspirational essay.",
                "Step 3: Upload Class 10/12 scorecards, entrance rank, and parent's income proof (ITR / Form 16 / Salary slips).",
                "Step 4: Participate in two rounds of evaluation: online document screening and panel telephonic/video interview.",
                "Step 5: Selected scholars receive ₹1.5 Lakhs annually towards tuition, hostel, and academic learning tools."
            ]),
            json.dumps([
                "Class 10th and 12th Board Marksheets (>= 85% aggregate)",
                "National/State entrance examination scorecard (JEE, NEET, CLAT, etc.)",
                "Bonafide certificate from accredited college",
                "Parent's Income certificate / Form 16 / Salary slips",
                "Aadhaar card & Passport size photograph"
            ])
        ),
        (
            "HDFC Bank Parivartan's ECSS Programme",
            "HDFC Bank CSR",
            75000.00,
            "Annual merit-cum-need grant",
            "15-12-2026",
            "Educational Crisis Support Scholarship assisting students undergoing financial stress to complete their diploma, undergraduate or postgraduate studies.",
            55.0,
            2.5,
            "All UG & PG Degrees",
            "All Years",
            "All",
            "All",
            "https://www.hdfcbank.com/personal/about-us/community-initiatives/parivartan",
            json.dumps([
                "Step 1: Review qualification requirements — Minimum 55% marks in previous examination and family income <= ₹2.5 Lakhs.",
                "Step 2: Submit online application on HDFC Parivartan ECSS portal.",
                "Step 3: Document proof of financial need or family crisis along with institutional fee structure.",
                "Step 4: Screening and verification by HDFC Bank CSR evaluation panel.",
                "Step 5: Direct electronic disbursement of scholarship grant up to ₹75,000."
            ]),
            json.dumps([
                "Previous year mark sheets / grade cards",
                "Income Certificate issued by Gram Panchayat / Tehsildar / SDM",
                "College Admission proof & tuition fee structure",
                "Proof of family financial crisis (if applicable)",
                "Bank passbook or cancelled cheque"
            ])
        ),
        (
            "ONGC Scholarship for Meritorious Students",
            "ONGC Foundation",
            48000.00,
            "Annual Grant (₹4,000/month)",
            "30-11-2026",
            "Prestigious national grant by Oil and Natural Gas Corporation providing dedicated assistance to economically disadvantaged SC/ST/OBC engineering and medical students.",
            60.0,
            2.0,
            "Engineering (B.Tech), MBBS, MBA",
            "1st Year",
            "All",
            "SC/ST/OBC",
            "https://www.ongcscholar.org",
            json.dumps([
                "Step 1: Confirm eligibility — 1st year full-time Engineering or Medical student belonging to SC, ST, or OBC category with family income <= ₹2 Lakhs.",
                "Step 2: Register on ONGC Foundation online scholarship portal and enter academic records.",
                "Step 3: Download completed application form and get it physically certified and signed by College Dean/Principal.",
                "Step 4: Upload scanned certified application along with caste and income certificates.",
                "Step 5: Annual grant of ₹48,000 transferred in equal quarterly disbursements directly to student's bank account."
            ]),
            json.dumps([
                "Caste Certificate issued by designated State Government Authority",
                "Class 12th passing mark sheet (min 60%)",
                "Income Certificate from Tehsildar / Sub-Divisional Magistrate",
                "College Principal certified application form",
                "Student PAN Card & Aadhaar Card"
            ])
        ),
        (
            "Post-Matric Scholarship Scheme for Minorities",
            "Ministry of Minority Affairs (MoMA / NSP)",
            20000.00,
            "Tuition fee waiver + Maintenance allowance",
            "30-11-2026",
            "Government of India financial support for meritorious students belonging to notified minority communities (Muslim, Christian, Sikh, Buddhist, Jain, Parsi).",
            50.0,
            2.5,
            "All Higher Education UG & PG Degrees",
            "All Years",
            "All",
            "Minority",
            "https://scholarships.gov.in",
            json.dumps([
                "Step 1: Complete NSP One-Time Registration (OTR) with Aadhaar authentication.",
                "Step 2: Select 'Post Matric Scholarship Schemes Minorities CS' on NSP portal.",
                "Step 3: Upload minority self-declaration, income certificate (< ₹2.5L), and previous year marksheet.",
                "Step 4: Application scrutinized by College Verification Officer and forwarded to District Welfare Officer.",
                "Step 5: Sanction order issued; allowance credited via PFMS Direct Benefit Transfer."
            ]),
            json.dumps([
                "Self-declaration of minority community signed by student/parent",
                "Previous year academic mark sheet (min 50% marks)",
                "Annual Family Income Certificate (< ₹2.5 Lakhs)",
                "College Fee Challan / Receipt",
                "Aadhaar card linked bank account"
            ])
        ),
        (
            "Santoor Women's Scholarship",
            "Wipro Cares & Azim Premji Foundation",
            24000.00,
            "Annual Grant for entire 3-4 year degree",
            "31-10-2026",
            "Specialized grant supporting young women from underprivileged backgrounds who have completed schooling from government schools to pursue higher college education.",
            55.0,
            4.0,
            "Humanities, Liberal Arts, Sciences, Commerce",
            "1st Year",
            "Female Only",
            "All",
            "https://www.santoorscholarship.com",
            json.dumps([
                "Step 1: Check criteria — Passed 10th and 12th from a local government school, enrolled in 1st year degree program.",
                "Step 2: Apply online on Santoor Scholarship portal or submit physical form through affiliated college welfare cell.",
                "Step 3: Attach government school passing certificates, family ration card, and college admission proof.",
                "Step 4: Telephonic verification and home locality assessment by Santoor NGO partner.",
                "Step 5: Annual ₹24,000 grant credited every year until course completion."
            ]),
            json.dumps([
                "10th and 12th Marksheets from State Government School",
                "College Admission Receipt & Student ID Card",
                "Government Ration Card (BPL) or Income Certificate",
                "Student Bank Passbook in nationalized bank",
                "Aadhaar Card"
            ])
        )
    ]

    for title, prov, amt, period, dead, desc, min_m, max_inc, deg, yr, gnd, cst, url, steps, docs in scholarships:
        query("""INSERT INTO scholarships (title, provider, award_amount_inr, award_period, deadline_dmy,
                                          description, min_marks_percent, max_family_income_lakhs,
                                          eligible_degree, eligible_year, gender, category_caste,
                                          official_portal_url, claim_process_steps, required_documents)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
              (title, prov, amt, period, dead, desc, min_m, max_inc, deg, yr, gnd, cst, url, steps, docs), commit=True)

    # Seed demo user tracked scholarships
    user = query("SELECT id FROM users ORDER BY id LIMIT 1", fetchone=True)
    if user:
        uid = user["id"]
        rel_sc = query("SELECT id FROM scholarships WHERE title LIKE '%Reliance%' LIMIT 1", fetchone=True)
        aicte_sc = query("SELECT id FROM scholarships WHERE title LIKE '%Central Sector%' LIMIT 1", fetchone=True)
        today_dmy = date.today().strftime("%d-%m-%Y")
        if rel_sc:
            query("""INSERT INTO student_scholarship_tracker (user_id, scholarship_id, status, application_date_dmy, notes)
                     VALUES (%s, %s, %s, %s, %s)""",
                  (uid, rel_sc["id"], "Documents Ready", today_dmy, "Aadhaar linked to bank; marks cards verified"), commit=True)
        if aicte_sc:
            query("""INSERT INTO student_scholarship_tracker (user_id, scholarship_id, status, application_date_dmy, notes)
                     VALUES (%s, %s, %s, %s, %s)""",
                  (uid, aicte_sc["id"], "Applied", today_dmy, "NSP OTR Application Submitted; pending college nodal review"), commit=True)


def get_all_scholarships():
    return query("SELECT * FROM scholarships ORDER BY award_amount_inr DESC")


def get_scholarship_by_id(scholarship_id):
    return query("SELECT * FROM scholarships WHERE id = %s", (scholarship_id,), fetchone=True)


def get_user_scholarship_tracker(user_id):
    return query("""
        SELECT t.*, s.title, s.provider, s.award_amount_inr, s.award_period, s.deadline_dmy, s.official_portal_url
        FROM student_scholarship_tracker t
        JOIN scholarships s ON t.scholarship_id = s.id
        WHERE t.user_id = %s
        ORDER BY t.updated_at DESC
    """, (user_id,))


def track_scholarship(user_id, scholarship_id, status, notes=""):
    existing = query("""
        SELECT id FROM student_scholarship_tracker
        WHERE user_id = %s AND scholarship_id = %s
    """, (user_id, scholarship_id), fetchone=True)
    today_dmy = date.today().strftime("%d-%m-%Y")
    if existing:
        query("""
            UPDATE student_scholarship_tracker
            SET status = %s, notes = %s, application_date_dmy = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (status, notes, today_dmy, existing["id"]), commit=True)
    else:
        query("""
            INSERT INTO student_scholarship_tracker (user_id, scholarship_id, status, application_date_dmy, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, scholarship_id, status, today_dmy, notes), commit=True)


# =====================================================================
# CHATBOT & SFI ASSISTANT CONVERSATION & MEMORY HELPERS
# =====================================================================

def get_chatbot_history(user_id, limit=60):
    return query("""
        SELECT * FROM chatbot_conversations
        WHERE user_id = %s
        ORDER BY id ASC
        LIMIT %s
    """, (user_id, limit))


def save_chatbot_interaction(user_id, query_text, response_text, intent="general", data_card=None, actions_json=None, is_solved=1):
    dc_str = json.dumps(data_card) if isinstance(data_card, (dict, list)) else (str(data_card) if data_card else "")
    act_str = json.dumps(actions_json) if isinstance(actions_json, (dict, list)) else (str(actions_json) if actions_json else "[]")
    query("""
        INSERT INTO chatbot_conversations (user_id, query, response, intent, data_card, actions_json, is_solved)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (user_id, query_text, response_text, intent, dc_str, act_str, int(is_solved)), commit=True)


def get_chatbot_memory(user_id):
    rows = query("""
        SELECT memory_key, memory_value, confidence, updated_at
        FROM chatbot_memory
        WHERE user_id = %s
        ORDER BY updated_at DESC
    """, (user_id,))
    mem_dict = {r["memory_key"]: r["memory_value"] for r in rows}
    return mem_dict, rows


def update_chatbot_memory(user_id, memory_key, memory_value, confidence=1.0):
    existing = query("""
        SELECT id FROM chatbot_memory WHERE user_id = %s AND memory_key = %s
    """, (user_id, memory_key), fetchone=True)
    if existing:
        query("""
            UPDATE chatbot_memory
            SET memory_value = %s, confidence = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (str(memory_value), float(confidence), existing["id"]), commit=True)
    else:
        query("""
            INSERT INTO chatbot_memory (user_id, memory_key, memory_value, confidence)
            VALUES (%s, %s, %s, %s)
        """, (user_id, memory_key, str(memory_value), float(confidence)), commit=True)


def clear_chatbot_memory(user_id):
    query("DELETE FROM chatbot_memory WHERE user_id = %s", (user_id,), commit=True)
    query("DELETE FROM chatbot_conversations WHERE user_id = %s", (user_id,), commit=True)
    # Re-seed baseline knowledge for user
    initial_memories = [
        ("student_name", "Student", 1.0),
        ("college", "Engineering College", 1.0),
        ("academic_stream", "Computer Science & Engineering", 0.9),
        ("target_goal", "Tech Equipment & Emergency Cushion", 0.9),
        ("queries_solved_count", "0", 1.0),
    ]
    for m_key, m_val, conf in initial_memories:
        update_chatbot_memory(user_id, m_key, m_val, conf)


