# Courier Employee Management System (CEMS)

A complete Flask + MySQL implementation of the SRS: employee records, branch
management, courier assignment, delivery tracking, attendance, payroll and
reports — with a role-based Tailwind CSS interface (Administrator / Branch
Manager / Employee).

## 1. Requirements

- Python 3.10+
- MySQL Server (XAMPP works out of the box — the app assumes `root` with a
  blank password on `localhost`, matching the original project setup)

## 2. Setup

```bash
# from the CEMS/ folder
pip install -r requirements.txt

# Start MySQL (e.g. via XAMPP control panel), then create + seed the database:
python init_db.py
```

`init_db.py` creates the `cems_db` database, every table in `schema.sql`,
and seeds three branches, five users and sample deliveries / attendance /
payroll so the app is fully explorable immediately.

If your MySQL root user has a password, set it in **both**
`init_db.py` (`DB_CONFIG`) and `app.py` (`db_config`) before running.

## 3. Run

```bash
python app.py
```

Visit **http://127.0.0.1:5000** and sign in with one of the demo accounts:

| Role            | Username         | Password    |
|-----------------|------------------|-------------|
| Administrator   | `admin_user`     | `admin123`  |
| Branch Manager  | `branch_mgr`     | `manager123`|
| Employee        | `delivery_agent` | `worker123` |

## 4. What's included

| SRS requirement                 | Where it lives                                   |
|----------------------------------|---------------------------------------------------|
| Admin / Employee login           | `/login` (role read from `users.role`)             |
| Add / Edit / Delete employees    | `/employees`, `/employees/add`, `/employees/edit/<id>` |
| Branch management                | `/branches`                                        |
| Assign couriers / deliveries     | `/deliveries`, `/deliveries/assign`                |
| Employee: view assignments       | `/my-deliveries`                                   |
| Employee: update delivery status | inline on `/my-deliveries`                         |
| Attendance                       | `/attendance` (admin/manager), `/my-attendance` (self check-in/out) |
| Payroll / salary records         | `/payroll`, `/my-payroll`                          |
| Reports                          | `/reports`                                         |
| Backup                           | use `mysqldump cems_db > backup.sql` (standard MySQL backup) |

## 5. Project structure

```
CEMS/
├── app.py              # Flask routes & business logic
├── schema.sql           # Full MySQL schema
├── init_db.py            # Creates + seeds the database
├── requirements.txt
├── static/
│   └── style.css         # Signature "waybill" design details (Tailwind via CDN handles the rest)
└── templates/
    ├── base.html          # Sidebar shell, topbar, flash messages
    ├── login.html
    ├── dashboard.html      # Role-aware overview
    ├── employees_list.html / employee_form.html
    ├── branches.html
    ├── deliveries_list.html / delivery_form.html
    ├── my_deliveries.html
    ├── attendance_admin.html / my_attendance.html
    ├── payroll.html / my_payroll.html
    └── reports.html
```

## 6. Notes

- Passwords are hashed with Werkzeug's `generate_password_hash` /
  `check_password_hash` — never stored in plain text.
- All state-changing routes are protected by role-based decorators
  (`@login_required`, `@roles_required(...)`) mirroring the SRS's
  Administrator / Employee permission split (Branch Manager kept as an
  additional operational role for courier assignment & payroll).
- The frontend uses the Tailwind CDN build — no Node/build step required.
