from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = "super_secure_secret_key" # Required for session management

# MySQL Configuration
# MySQL Configuration for XAMPP
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '', # LEAVE THIS BLANK for XAMPP
    'database': 'cems_db'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/')
def home():
    if 'loggedin' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        account = cursor.fetchone()
        cursor.close()
        conn.close()
        
        # Verify user exists and the password matches the hash
        if account and check_password_hash(account['password'], password):
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['role'] = account['role']
            return redirect(url_for('dashboard'))
        else:
            flash("Incorrect username or password!")
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    # Protect route from unauthenticated access
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    return render_template('dashboard.html', 
                           username=session['username'], 
                           role=session['role'])

@app.route('/logout')
def logout():
    session.clear() # Destroy the session
    return redirect(url_for('login'))

@app.route('/my-deliveries')
def my_deliveries():
    # Security check: Only let logged-in Employees access this page
    if 'loggedin' not in session or session['role'] != 'Employee':
        flash("Unauthorized access!")
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch deliveries assigned specifically to the logged-in user
    cursor.execute("SELECT * FROM deliveries WHERE assigned_to = %s", (session['id'],))
    deliveries = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Send the database results to a new HTML template
    return render_template('my_deliveries.html', 
                           username=session['username'], 
                           role=session['role'], 
                           deliveries=deliveries)

@app.route('/manage-branches', methods=['GET', 'POST'])
def manage_branches():
    if 'loggedin' not in session or session['role'] != 'Administrator':
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        branch_name = request.form['branch_name']
        location = request.form['location']
        cursor.execute("INSERT INTO branches (branch_name, location) VALUES (%s, %s)", (branch_name, location))
        conn.commit()
        flash("Branch added successfully!")
        
    cursor.execute("SELECT * FROM branches")
    branches = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('generic_form.html', title="Manage Branches", data=branches)

# ==========================================
# BRANCH MANAGER MODULES[cite: 1, 2]
# ==========================================
@app.route('/assign-delivery', methods=['GET', 'POST'])
def assign_delivery():
    if 'loggedin' not in session or session['role'] != 'Branch Manager':
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        tracking_number = request.form['tracking_number']
        assigned_to = request.form['assigned_to']
        destination = request.form['destination_address']
        
        cursor.execute("INSERT INTO deliveries (tracking_number, assigned_to, destination_address, status) VALUES (%s, %s, %s, 'Pending')", 
                       (tracking_number, assigned_to, destination))
        conn.commit()
        flash("Delivery assigned successfully!")
        
    cursor.execute("SELECT * FROM users WHERE role = 'Employee'")
    employees = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('assign_delivery.html', employees=employees)

@app.route('/manage-payroll', methods=['GET', 'POST'])
def manage_payroll():
    if 'loggedin' not in session or session['role'] != 'Branch Manager':
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Logic to calculate and insert payroll would go here
    cursor.execute("SELECT p.*, u.username FROM payroll p JOIN users u ON p.employee_id = u.id")
    payroll_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('generic_form.html', title="Payroll Management", data=payroll_data)

# ==========================================
# EMPLOYEE MODULES[cite: 1, 2]
# ==========================================
@app.route('/update-status/<int:delivery_id>', methods=['POST'])
def update_status(delivery_id):
    if 'loggedin' not in session or session['role'] != 'Employee':
        return redirect(url_for('dashboard'))
        
    new_status = request.form['status']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE deliveries SET status = %s WHERE id = %s AND assigned_to = %s", 
                   (new_status, delivery_id, session['id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Delivery status updated!")
    return redirect(url_for('my_deliveries'))


if __name__ == '__main__':
    # Run application in debug mode for development
    app.run(debug=True)