import mysql.connector
from werkzeug.security import generate_password_hash

# 1. Connect to your XAMPP MySQL Database
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",  # XAMPP default is blank
    database="cems_db"
)
cursor = db.cursor()

# 2. Clear the existing users to avoid conflicts
cursor.execute("TRUNCATE TABLE users")

# 3. Generate fresh, compatible hashes using your local environment
users = [
    ('admin_user', generate_password_hash('admin123'), 'Administrator'),
    ('branch_mgr', generate_password_hash('manager123'), 'Branch Manager'),
    ('delivery_agent', generate_password_hash('worker123'), 'Employee')
]

# 4. Insert the new users into the database
cursor.executemany("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", users)
db.commit()

print("Success! Passwords have been freshly hashed and updated.")

cursor.close()
db.close()