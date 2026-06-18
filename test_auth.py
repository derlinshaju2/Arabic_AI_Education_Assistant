#!/usr/bin/env python
import sqlite3
import os
from app import hash_password, verify_password

# Test hash and verify
test_password = "TestPass123!"
hashed = hash_password(test_password)
print(f"Original password: {test_password}")
print(f"Hashed: {hashed}")

# Test if verification works
is_valid = verify_password(test_password, hashed)
print(f"Password verification: {is_valid}")

# Test with wrong password
is_valid_wrong = verify_password("WrongPassword", hashed)
print(f"Wrong password verification: {is_valid_wrong}")

# Check existing user
db_path = os.path.join(os.getcwd(), "users.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT email, password FROM users")
users = c.fetchall()
print(f"\nUsers in database:")
for email, pwd_hash in users:
    print(f"  Email: {email}, Password hash exists: {bool(pwd_hash)}")

# Test verification with the existing user's password
if users:
    email, pwd_hash = users[0]
    print(f"\nTesting verification with stored password for {email}:")
    # Try common passwords
    test_passwords = ["Test123!", "password", "test123", "123456"]
    for test_pwd in test_passwords:
        result = verify_password(test_pwd, pwd_hash)
        print(f"  {test_pwd}: {result}")

conn.close()
