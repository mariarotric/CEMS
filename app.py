from functools import wraps
from datetime import date, datetime

import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "super_secure_secret_key"  # Required for session management

# ---------------------------------------------------------------
# MySQL Configuration (XAMPP defaults: user 'root', blank password)
# ---------------------------------------------------------------
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "cems_db",
}


def get_db_connection():
    return mysql.connector.connect(**db_config)


def query(sql, params=None, fetchone=False, commit=False):
    """Small helper to cut down on connect/cursor boilerplate."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql, params or ())
    result = None
    if commit:
        conn.commit()
        result = cursor.lastrowid
    else:
        result = cursor.fetchone() if fetchone else cursor.fetchall()
    cursor.close()
    conn.close()
    return result


# ---------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "loggedin" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "loggedin" not in session:
                return redirect(url_for("login"))
            if session["role"] not in allowed_roles:
                flash("You don't have permission to access that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_user():
    return dict(
        current_role=session.get("role"),
        current_username=session.get("username"),
        current_fullname=session.get("full_name"),
    )


# ---------------------------------------------------------------
# Home / Auth
# ---------------------------------------------------------------
@app.route("/")
def home():
    if "loggedin" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        account = query("SELECT * FROM users WHERE username = %s", (username,), fetchone=True)

        if account and check_password_hash(account["password"], password):
            if account["status"] == "Inactive":
                flash("This account has been deactivated. Contact your administrator.", "error")
                return render_template("login.html")
            session["loggedin"] = True
            session["id"] = account["id"]
            session["username"] = account["username"]
            session["role"] = account["role"]
            session["full_name"] = account["full_name"]
            return redirect(url_for("dashboard"))
        else:
            flash("Incorrect username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    role = session["role"]
    stats = {}

    if role == "Administrator":
        stats["employees"] = query("SELECT COUNT(*) c FROM users WHERE role != 'Administrator'", fetchone=True)["c"]
        stats["branches"] = query("SELECT COUNT(*) c FROM branches", fetchone=True)["c"]
        stats["deliveries"] = query("SELECT COUNT(*) c FROM deliveries", fetchone=True)["c"]
        stats["delivered"] = query("SELECT COUNT(*) c FROM deliveries WHERE status='Delivered'", fetchone=True)["c"]
        stats["pending"] = query("SELECT COUNT(*) c FROM deliveries WHERE status NOT IN ('Delivered','Failed')", fetchone=True)["c"]
        stats["failed"] = query("SELECT COUNT(*) c FROM deliveries WHERE status='Failed'", fetchone=True)["c"]
        recent_deliveries = query(
            """SELECT d.*, u.full_name AS agent_name FROM deliveries d
               LEFT JOIN users u ON d.assigned_to = u.id
               ORDER BY d.created_at DESC LIMIT 6"""
        )
        status_breakdown = query(
            "SELECT status, COUNT(*) count FROM deliveries GROUP BY status"
        )
        return render_template("dashboard.html", stats=stats, recent_deliveries=recent_deliveries,
                                status_breakdown=status_breakdown)

    if role == "Branch Manager":
        stats["deliveries"] = query("SELECT COUNT(*) c FROM deliveries", fetchone=True)["c"]
        stats["pending"] = query("SELECT COUNT(*) c FROM deliveries WHERE status='Pending'", fetchone=True)["c"]
        stats["employees"] = query("SELECT COUNT(*) c FROM users WHERE role='Employee'", fetchone=True)["c"]
        recent_deliveries = query(
            """SELECT d.*, u.full_name AS agent_name FROM deliveries d
               LEFT JOIN users u ON d.assigned_to = u.id
               ORDER BY d.created_at DESC LIMIT 6"""
        )
        return render_template("dashboard.html", stats=stats, recent_deliveries=recent_deliveries,
                                status_breakdown=[])

    # Employee dashboard
    stats["assigned"] = query(
        "SELECT COUNT(*) c FROM deliveries WHERE assigned_to=%s", (session["id"],), fetchone=True
    )["c"]
    stats["delivered"] = query(
        "SELECT COUNT(*) c FROM deliveries WHERE assigned_to=%s AND status='Delivered'",
        (session["id"],), fetchone=True
    )["c"]
    stats["pending"] = query(
        "SELECT COUNT(*) c FROM deliveries WHERE assigned_to=%s AND status NOT IN ('Delivered','Failed')",
        (session["id"],), fetchone=True
    )["c"]
    today_att = query(
        "SELECT * FROM attendance WHERE employee_id=%s AND date=%s", (session["id"], date.today()), fetchone=True
    )
    recent_deliveries = query(
        "SELECT * FROM deliveries WHERE assigned_to=%s ORDER BY updated_at DESC LIMIT 6", (session["id"],)
    )
    return render_template("dashboard.html", stats=stats, today_att=today_att,
                            recent_deliveries=recent_deliveries, status_breakdown=[])


# ---------------------------------------------------------------
# Employee Management (Administrator)
# ---------------------------------------------------------------
@app.route("/employees")
@roles_required("Administrator")
def employees_list():
    employees = query(
        """SELECT u.*, b.branch_name FROM users u
           LEFT JOIN branches b ON u.branch_id = b.id
           ORDER BY u.created_at DESC"""
    )
    return render_template("employees_list.html", employees=employees)


@app.route("/employees/add", methods=["GET", "POST"])
@roles_required("Administrator")
def employee_add():
    branches = query("SELECT * FROM branches ORDER BY branch_name")
    if request.method == "POST":
        f = request.form
        existing = query("SELECT id FROM users WHERE username=%s", (f["username"],), fetchone=True)
        if existing:
            flash("That username is already taken.", "error")
            return render_template("employee_form.html", branches=branches, employee=f, mode="add")

        query(
            """INSERT INTO users (username, password, role, full_name, email, phone,
                                   designation, branch_id, base_salary, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (f["username"], generate_password_hash(f["password"]), f["role"], f["full_name"],
             f.get("email"), f.get("phone"), f.get("designation"), f.get("branch_id") or None,
             f.get("base_salary") or 0, f.get("status", "Active")),
            commit=True,
        )
        flash(f'Employee "{f["full_name"]}" added successfully.', "success")
        return redirect(url_for("employees_list"))

    return render_template("employee_form.html", branches=branches, employee=None, mode="add")


@app.route("/employees/edit/<int:user_id>", methods=["GET", "POST"])
@roles_required("Administrator")
def employee_edit(user_id):
    branches = query("SELECT * FROM branches ORDER BY branch_name")
    employee = query("SELECT * FROM users WHERE id=%s", (user_id,), fetchone=True)
    if not employee:
        flash("Employee not found.", "error")
        return redirect(url_for("employees_list"))

    if request.method == "POST":
        f = request.form
        if f.get("password"):
            query(
                """UPDATE users SET full_name=%s, email=%s, phone=%s, designation=%s,
                       role=%s, branch_id=%s, base_salary=%s, status=%s, password=%s
                   WHERE id=%s""",
                (f["full_name"], f.get("email"), f.get("phone"), f.get("designation"), f["role"],
                 f.get("branch_id") or None, f.get("base_salary") or 0, f.get("status", "Active"),
                 generate_password_hash(f["password"]), user_id),
                commit=True,
            )
        else:
            query(
                """UPDATE users SET full_name=%s, email=%s, phone=%s, designation=%s,
                       role=%s, branch_id=%s, base_salary=%s, status=%s
                   WHERE id=%s""",
                (f["full_name"], f.get("email"), f.get("phone"), f.get("designation"), f["role"],
                 f.get("branch_id") or None, f.get("base_salary") or 0, f.get("status", "Active"),
                 user_id),
                commit=True,
            )
        flash("Employee record updated.", "success")
        return redirect(url_for("employees_list"))

    return render_template("employee_form.html", branches=branches, employee=employee, mode="edit")


@app.route("/employees/delete/<int:user_id>", methods=["POST"])
@roles_required("Administrator")
def employee_delete(user_id):
    if user_id == session["id"]:
        flash("You cannot delete your own account while logged in.", "error")
        return redirect(url_for("employees_list"))
    query("DELETE FROM users WHERE id=%s", (user_id,), commit=True)
    flash("Employee record deleted.", "success")
    return redirect(url_for("employees_list"))


# ---------------------------------------------------------------
# Branch Management (Administrator)
# ---------------------------------------------------------------
@app.route("/branches", methods=["GET", "POST"])
@roles_required("Administrator")
def manage_branches():
    if request.method == "POST":
        query(
            "INSERT INTO branches (branch_name, location, phone) VALUES (%s,%s,%s)",
            (request.form["branch_name"], request.form["location"], request.form.get("phone")),
            commit=True,
        )
        flash("Branch added successfully.", "success")
        return redirect(url_for("manage_branches"))

    branches = query(
        """SELECT b.*, COUNT(u.id) staff_count FROM branches b
           LEFT JOIN users u ON u.branch_id = b.id
           GROUP BY b.id ORDER BY b.branch_name"""
    )
    return render_template("branches.html", branches=branches)


@app.route("/branches/delete/<int:branch_id>", methods=["POST"])
@roles_required("Administrator")
def branch_delete(branch_id):
    query("DELETE FROM branches WHERE id=%s", (branch_id,), commit=True)
    flash("Branch removed.", "success")
    return redirect(url_for("manage_branches"))


# ---------------------------------------------------------------
# Courier Assignment / Delivery Tracking
# ---------------------------------------------------------------
@app.route("/deliveries")
@roles_required("Administrator", "Branch Manager")
def deliveries_list():
    status_filter = request.args.get("status", "")
    sql = """SELECT d.*, u.full_name AS agent_name, b.branch_name FROM deliveries d
              LEFT JOIN users u ON d.assigned_to = u.id
              LEFT JOIN branches b ON d.branch_id = b.id"""
    params = ()
    if status_filter:
        sql += " WHERE d.status = %s"
        params = (status_filter,)
    sql += " ORDER BY d.created_at DESC"
    deliveries = query(sql, params)
    return render_template("deliveries_list.html", deliveries=deliveries, status_filter=status_filter)


@app.route("/deliveries/assign", methods=["GET", "POST"])
@roles_required("Administrator", "Branch Manager")
def assign_delivery():
    employees = query("SELECT * FROM users WHERE role='Employee' AND status='Active' ORDER BY full_name")
    branches = query("SELECT * FROM branches ORDER BY branch_name")

    if request.method == "POST":
        f = request.form
        existing = query("SELECT id FROM deliveries WHERE tracking_number=%s", (f["tracking_number"],), fetchone=True)
        if existing:
            flash("That tracking number already exists.", "error")
        else:
            query(
                """INSERT INTO deliveries (tracking_number, customer_name, destination_address,
                                            assigned_to, branch_id, status)
                   VALUES (%s,%s,%s,%s,%s,'Pending')""",
                (f["tracking_number"], f["customer_name"], f["destination_address"],
                 f.get("assigned_to") or None, f.get("branch_id") or None),
                commit=True,
            )
            flash("Delivery assigned successfully.", "success")
            return redirect(url_for("deliveries_list"))

    return render_template("delivery_form.html", employees=employees, branches=branches)


@app.route("/deliveries/reassign/<int:delivery_id>", methods=["POST"])
@roles_required("Administrator", "Branch Manager")
def reassign_delivery(delivery_id):
    query(
        "UPDATE deliveries SET assigned_to=%s, status=%s WHERE id=%s",
        (request.form.get("assigned_to") or None, request.form["status"], delivery_id),
        commit=True,
    )
    flash("Delivery updated.", "success")
    return redirect(url_for("deliveries_list"))


# ---------------------------------------------------------------
# Employee: My Deliveries
# ---------------------------------------------------------------
@app.route("/my-deliveries")
@roles_required("Employee")
def my_deliveries():
    deliveries = query(
        "SELECT * FROM deliveries WHERE assigned_to = %s ORDER BY created_at DESC", (session["id"],)
    )
    return render_template("my_deliveries.html", deliveries=deliveries)


@app.route("/update-status/<int:delivery_id>", methods=["POST"])
@roles_required("Employee")
def update_status(delivery_id):
    new_status = request.form["status"]
    query(
        "UPDATE deliveries SET status=%s WHERE id=%s AND assigned_to=%s",
        (new_status, delivery_id, session["id"]),
        commit=True,
    )
    flash("Delivery status updated.", "success")
    return redirect(url_for("my_deliveries"))


# ---------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------
@app.route("/attendance")
@roles_required("Administrator", "Branch Manager")
def attendance_admin():
    selected_date = request.args.get("date") or date.today().isoformat()
    records = query(
        """SELECT a.*, u.full_name, u.designation FROM attendance a
           JOIN users u ON a.employee_id = u.id
           WHERE a.date = %s ORDER BY u.full_name""",
        (selected_date,),
    )
    employees = query("SELECT id, full_name FROM users WHERE role='Employee' AND status='Active'")
    marked_ids = {r["employee_id"] for r in records}
    unmarked = [e for e in employees if e["id"] not in marked_ids]
    return render_template("attendance_admin.html", records=records, unmarked=unmarked, selected_date=selected_date)


@app.route("/attendance/mark", methods=["POST"])
@roles_required("Administrator", "Branch Manager")
def attendance_mark_admin():
    query(
        """INSERT INTO attendance (employee_id, date, status, check_in, check_out)
           VALUES (%s,%s,%s,%s,%s)
           ON DUPLICATE KEY UPDATE status=VALUES(status), check_in=VALUES(check_in), check_out=VALUES(check_out)""",
        (request.form["employee_id"], request.form["date"], request.form["status"],
         request.form.get("check_in") or None, request.form.get("check_out") or None),
        commit=True,
    )
    flash("Attendance recorded.", "success")
    return redirect(url_for("attendance_admin", date=request.form["date"]))


@app.route("/my-attendance")
@roles_required("Employee")
def my_attendance():
    records = query(
        "SELECT * FROM attendance WHERE employee_id=%s ORDER BY date DESC LIMIT 31", (session["id"],)
    )
    today_att = query(
        "SELECT * FROM attendance WHERE employee_id=%s AND date=%s", (session["id"], date.today()), fetchone=True
    )
    return render_template("my_attendance.html", records=records, today_att=today_att)


@app.route("/my-attendance/checkin", methods=["POST"])
@roles_required("Employee")
def checkin():
    now = datetime.now().strftime("%H:%M:%S")
    query(
        """INSERT INTO attendance (employee_id, date, status, check_in)
           VALUES (%s,%s,'Present',%s)
           ON DUPLICATE KEY UPDATE check_in=VALUES(check_in), status='Present'""",
        (session["id"], date.today(), now),
        commit=True,
    )
    flash("Checked in for today.", "success")
    return redirect(url_for("my_attendance"))


@app.route("/my-attendance/checkout", methods=["POST"])
@roles_required("Employee")
def checkout():
    now = datetime.now().strftime("%H:%M:%S")
    query(
        "UPDATE attendance SET check_out=%s WHERE employee_id=%s AND date=%s",
        (now, session["id"], date.today()),
        commit=True,
    )
    flash("Checked out for today.", "success")
    return redirect(url_for("my_attendance"))


# ---------------------------------------------------------------
# Payroll / Salary Records
# ---------------------------------------------------------------
@app.route("/payroll", methods=["GET", "POST"])
@roles_required("Administrator", "Branch Manager")
def manage_payroll():
    if request.method == "POST":
        f = request.form
        basic = float(f.get("basic_salary") or 0)
        bonus = float(f.get("bonus") or 0)
        deductions = float(f.get("deductions") or 0)
        net = basic + bonus - deductions
        query(
            """INSERT INTO payroll (employee_id, month, basic_salary, bonus, deductions, net_salary)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE basic_salary=VALUES(basic_salary), bonus=VALUES(bonus),
                   deductions=VALUES(deductions), net_salary=VALUES(net_salary)""",
            (f["employee_id"], f["month"], basic, bonus, deductions, net),
            commit=True,
        )
        flash("Payroll record saved.", "success")
        return redirect(url_for("manage_payroll"))

    payroll_data = query(
        """SELECT p.*, u.full_name, u.designation FROM payroll p
           JOIN users u ON p.employee_id = u.id
           ORDER BY p.month DESC, u.full_name"""
    )
    employees = query("SELECT id, full_name, base_salary FROM users WHERE role='Employee' ORDER BY full_name")
    return render_template("payroll.html", payroll_data=payroll_data, employees=employees)


@app.route("/my-payroll")
@roles_required("Employee")
def my_payroll():
    records = query(
        "SELECT * FROM payroll WHERE employee_id=%s ORDER BY month DESC", (session["id"],)
    )
    return render_template("my_payroll.html", records=records)


# ---------------------------------------------------------------
# Reports (Administrator)
# ---------------------------------------------------------------
@app.route("/reports")
@roles_required("Administrator")
def reports():
    delivery_status = query("SELECT status, COUNT(*) count FROM deliveries GROUP BY status")
    branch_performance = query(
        """SELECT b.branch_name,
                  COUNT(d.id) total,
                  SUM(CASE WHEN d.status='Delivered' THEN 1 ELSE 0 END) delivered,
                  SUM(CASE WHEN d.status='Failed' THEN 1 ELSE 0 END) failed
           FROM branches b LEFT JOIN deliveries d ON d.branch_id = b.id
           GROUP BY b.id, b.branch_name"""
    )
    top_agents = query(
        """SELECT u.full_name, COUNT(d.id) total_deliveries,
                  SUM(CASE WHEN d.status='Delivered' THEN 1 ELSE 0 END) delivered
           FROM users u JOIN deliveries d ON d.assigned_to = u.id
           WHERE u.role='Employee'
           GROUP BY u.id, u.full_name
           ORDER BY delivered DESC LIMIT 5"""
    )
    payroll_total = query(
        "SELECT COALESCE(SUM(net_salary),0) total FROM payroll", fetchone=True
    )["total"]
    attendance_today = query(
        "SELECT COUNT(*) c FROM attendance WHERE date=%s AND status='Present'", (date.today(),), fetchone=True
    )["c"]

    return render_template(
        "reports.html",
        delivery_status=delivery_status,
        branch_performance=branch_performance,
        top_agents=top_agents,
        payroll_total=payroll_total,
        attendance_today=attendance_today,
    )


if __name__ == "__main__":
    app.run(debug=True)
