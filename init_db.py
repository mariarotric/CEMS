import mysql.connector
from werkzeug.security import generate_password_hash

# Connect to MySQL Server (Update 'user' and 'password' with your MySQL credentials)
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="yourpassword" 
)

cursor = db.cursor()

# Create the database defined for the CEMS project
cursor.execute("CREATE DATABASE IF NOT EXISTS cems_db")
cursor.execute("USE cems_db")

# Create the users table with an ENUM for strict role assignment
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('Administrator', 'Branch Manager', 'Employee') NOT NULL
)
""")

# Define test users based on the SRS functional roles
test_users = [
    ('admin_user', generate_password_hash('admin123'), 'Administrator'),
    ('branch_mgr', generate_password_hash('manager123'), 'Branch Manager'),
    ('delivery_agent', generate_password_hash('worker123'), 'Employee')
]

# Insert users into the database
cursor.executemany("INSERT IGNORE INTO users (username, password, role) VALUES (%s, %s, %s)", test_users)
db.commit()

print("Database 'cems_db' and test users configured successfully!")