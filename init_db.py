"""
Initializes the cems_db MySQL database: creates all tables (see schema.sql)
and seeds demo branches, users (one per role) and sample operational data
so the app is fully explorable right after setup.

Run once:   python init_db.py
"""
import mysql.connector
from werkzeug.security import generate_password_hash
from datetime import date, timedelta

# ---- MySQL connection (XAMPP defaults: user 'root', blank password) ----
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",   # <-- set your MySQL root password here if not using XAMPP defaults
}

conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()

cursor.execute("CREATE DATABASE IF NOT EXISTS cems_db")
cursor.execute("USE cems_db")

with open("schema.sql", "r") as f:
    sql_script = f.read()

# Strip the CREATE DATABASE / USE statements already handled above, then
# execute each remaining statement individually.
statements = [s.strip() for s in sql_script.split(";") if s.strip()]
for stmt in statements:
    if stmt.upper().startswith(("CREATE DATABASE", "USE ")):
        continue
    cursor.execute(stmt)
conn.commit()

# ---------------------------------------------------------------
# Seed: branches
# ---------------------------------------------------------------
branches = [
    ("Chennai Central Hub", "Anna Salai, Chennai", "044-28451200"),
    ("Coimbatore Depot", "Race Course Road, Coimbatore", "0422-2345678"),
    ("Madurai Terminal", "Alagar Koil Road, Madurai", "0452-2340099"),
]
cursor.executemany(
    "INSERT IGNORE INTO branches (branch_name, location, phone) VALUES (%s, %s, %s)",
    branches,
)
conn.commit()

cursor.execute("SELECT id, branch_name FROM branches ORDER BY id")
branch_ids = {name: bid for bid, name in cursor.fetchall()}

# ---------------------------------------------------------------
# Seed: users (Administrator, Branch Manager, Employees)
# ---------------------------------------------------------------
users = [
    ("admin_user", generate_password_hash("admin123"), "Administrator",
     "Maria Rotric Loran", "admin@cems.com", "9876543210", "System Administrator",
     branch_ids["Chennai Central Hub"], 55000),
    ("branch_mgr", generate_password_hash("manager123"), "Branch Manager",
     "Arjun Kumar", "arjun.mgr@cems.com", "9876500011", "Branch Manager",
     branch_ids["Chennai Central Hub"], 42000),
    ("delivery_agent", generate_password_hash("worker123"), "Employee",
     "Ravi Shankar", "ravi.s@cems.com", "9876500022", "Delivery Executive",
     branch_ids["Chennai Central Hub"], 22000),
    ("priya_k", generate_password_hash("worker123"), "Employee",
     "Priya Krishnan", "priya.k@cems.com", "9876500033", "Delivery Executive",
     branch_ids["Coimbatore Depot"], 21000),
    ("suresh_m", generate_password_hash("worker123"), "Employee",
     "Suresh Murugan", "suresh.m@cems.com", "9876500044", "Warehouse Associate",
     branch_ids["Madurai Terminal"], 19500),
]
cursor.executemany(
    """INSERT IGNORE INTO users
       (username, password, role, full_name, email, phone, designation, branch_id, base_salary)
       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
    users,
)
conn.commit()

cursor.execute("SELECT id, username FROM users")
uid = {name: i for i, name in cursor.fetchall()}

# ---------------------------------------------------------------
# Seed: sample deliveries
# ---------------------------------------------------------------
deliveries = [
    ("CMS100234", "Lakshmi Textiles", "12 Mount Road, Chennai", uid["delivery_agent"],
     branch_ids["Chennai Central Hub"], "In Transit"),
    ("CMS100235", "Anand Traders", "45 RS Puram, Coimbatore", uid["priya_k"],
     branch_ids["Coimbatore Depot"], "Delivered"),
    ("CMS100236", "Sri Ganesh Stores", "8 West Masi Street, Madurai", uid["suresh_m"],
     branch_ids["Madurai Terminal"], "Pending"),
    ("CMS100237", "Kaveri Enterprises", "21 T Nagar, Chennai", uid["delivery_agent"],
     branch_ids["Chennai Central Hub"], "Out for Delivery"),
    ("CMS100238", "Meenakshi Boutique", "3 KK Nagar, Madurai", uid["suresh_m"],
     branch_ids["Madurai Terminal"], "Failed"),
]
cursor.executemany(
    """INSERT IGNORE INTO deliveries
       (tracking_number, customer_name, destination_address, assigned_to, branch_id, status)
       VALUES (%s,%s,%s,%s,%s,%s)""",
    deliveries,
)
conn.commit()

# ---------------------------------------------------------------
# Seed: attendance for the last 5 days for each employee
# ---------------------------------------------------------------
employees = [uid["delivery_agent"], uid["priya_k"], uid["suresh_m"]]
today = date.today()
att_rows = []
for emp in employees:
    for i in range(5):
        d = today - timedelta(days=i)
        att_rows.append((emp, d, "Present", "09:00:00", "18:00:00"))
cursor.executemany(
    """INSERT IGNORE INTO attendance (employee_id, date, status, check_in, check_out)
       VALUES (%s,%s,%s,%s,%s)""",
    att_rows,
)
conn.commit()

# ---------------------------------------------------------------
# Seed: last month's payroll for each employee
# ---------------------------------------------------------------
last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
payroll_rows = []
salaries = {uid["delivery_agent"]: 22000, uid["priya_k"]: 21000, uid["suresh_m"]: 19500}
for emp, base in salaries.items():
    bonus, deductions = 1500, 500
    payroll_rows.append((emp, last_month, base, bonus, deductions, base + bonus - deductions))
cursor.executemany(
    """INSERT IGNORE INTO payroll (employee_id, month, basic_salary, bonus, deductions, net_salary)
       VALUES (%s,%s,%s,%s,%s,%s)""",
    payroll_rows,
)
conn.commit()

cursor.close()
conn.close()

print("Database 'cems_db' created and seeded successfully!")
print("Login credentials:")
print("  Administrator  -> admin_user / admin123")
print("  Branch Manager -> branch_mgr / manager123")
print("  Employee       -> delivery_agent / worker123")
