import hashlib
import secrets
import string
from decimal import Decimal, InvalidOperation

import mysql.connector
from mysql.connector import Error

# Update these values if your MySQL credentials are different.
DB_HOST = "localhost"
DB_USER = "Vedya7320"
DB_PASSWORD = "NewStrongPassword123!"
DB_NAME = "Company"


def hash_pin(pin):
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def read_amount(prompt):
    while True:
        try:
            amount = Decimal(input(prompt).strip()).quantize(Decimal("0.01"))
            if amount <= 0:
                print("Enter an amount greater than 0.")
                continue
            return amount
        except (InvalidOperation, ValueError):
            print("Enter a valid amount, for example 500 or 250.50.")


class BankSystem:
    def __init__(self):
        self.conn = None
        self.cursor = None

    def connect(self):
        self.conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connection_timeout=10,
            autocommit=False,
        )
        self.cursor = self.conn.cursor()
        self.create_tables()
        print("Database connected successfully!")

    def create_tables(self):
        statements = [
            """
            CREATE TABLE IF NOT EXISTS bank_accounts (
                account_number VARCHAR(20) PRIMARY KEY,
                customer_name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                pin_hash CHAR(64) NOT NULL,
                balance DECIMAL(12,2) NOT NULL DEFAULT 1000.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bank_transactions (
                transaction_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                account_number VARCHAR(20) NOT NULL,
                transaction_type VARCHAR(20) NOT NULL,
                amount DECIMAL(12,2) NOT NULL,
                note VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_bank_tx_account (account_number)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bank_loans (
                loan_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                account_number VARCHAR(20) NOT NULL,
                amount DECIMAL(12,2) NOT NULL,
                purpose VARCHAR(255) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_bank_loan_account (account_number)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bank_support (
                ticket_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                account_number VARCHAR(20),
                message TEXT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'Open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ]
        for statement in statements:
            self.cursor.execute(statement)
        self.conn.commit()

    def close(self):
        try:
            if self.cursor is not None:
                self.cursor.close()
        finally:
            if self.conn is not None and self.conn.is_connected():
                self.conn.close()

    def generate_account_number(self):
        while True:
            number = "SB" + "".join(secrets.choice(string.digits) for _ in range(10))
            self.cursor.execute(
                "SELECT account_number FROM bank_accounts WHERE account_number=%s",
                (number,),
            )
            if self.cursor.fetchone() is None:
                return number

    def create_account(self):
        print("\n--- Create Bank Account ---")
        name = input("Customer name: ").strip()
        phone = input("Phone number: ").strip()
        if not name or not phone:
            print("Name and phone number are required.")
            return

        pin = input("Create a 4-digit PIN: ").strip()
        if len(pin) != 4 or not pin.isdigit():
            print("PIN must be exactly 4 digits.")
            return

        account_number = self.generate_account_number()
        try:
            self.cursor.execute(
                """
                INSERT INTO bank_accounts
                    (account_number, customer_name, phone, pin_hash, balance)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (account_number, name, phone, hash_pin(pin), Decimal("1000.00")),
            )
            self.cursor.execute(
                """
                INSERT INTO bank_transactions
                    (account_number, transaction_type, amount, note)
                VALUES (%s, %s, %s, %s)
                """,
                (account_number, "OPENING", Decimal("1000.00"), "Opening balance"),
            )
            self.conn.commit()
            print("\nAccount created successfully!")
            print("Account number:", account_number)
            print("Opening balance: ₹1000.00")
            print("Keep your account number and PIN safe.")
        except Error:
            self.conn.rollback()
            raise

    def login(self):
        print("\n--- Customer Login ---")
        account_number = input("Account number: ").strip().upper()
        pin = input("4-digit PIN: ").strip()
        self.cursor.execute(
            """
            SELECT account_number, customer_name
            FROM bank_accounts
            WHERE account_number=%s AND pin_hash=%s
            """,
            (account_number, hash_pin(pin)),
        )
        account = self.cursor.fetchone()
        if not account:
            print("Invalid account number or PIN.")
            return
        self.customer_menu(account[0], account[1])

    def show_balance(self, account_number):
        self.cursor.execute(
            "SELECT balance FROM bank_accounts WHERE account_number=%s",
            (account_number,),
        )
        row = self.cursor.fetchone()
        if row:
            print(f"Available balance: ₹{Decimal(row[0]):,.2f}")
        else:
            print("Account not found.")

    def record_transaction(self, account_number, transaction_type, amount, note):
        self.cursor.execute(
            """
            INSERT INTO bank_transactions
                (account_number, transaction_type, amount, note)
            VALUES (%s, %s, %s, %s)
            """,
            (account_number, transaction_type, amount, note),
        )

    def deposit(self, account_number):
        amount = read_amount("Amount to deposit (₹): ")
        try:
            self.cursor.execute(
                "UPDATE bank_accounts SET balance=balance+%s WHERE account_number=%s",
                (amount, account_number),
            )
            if self.cursor.rowcount != 1:
                self.conn.rollback()
                print("Account not found.")
                return
            self.record_transaction(account_number, "CREDIT", amount, "Cash deposit")
            self.conn.commit()
            print(f"Deposit successful. ₹{amount:,.2f} credited.")
            self.show_balance(account_number)
        except Error:
            self.conn.rollback()
            raise

    def withdraw(self, account_number):
        amount = read_amount("Amount to withdraw (₹): ")
        try:
            self.cursor.execute(
                "SELECT balance FROM bank_accounts WHERE account_number=%s FOR UPDATE",
                (account_number,),
            )
            row = self.cursor.fetchone()
            if not row:
                self.conn.rollback()
                print("Account not found.")
                return
            balance = Decimal(row[0])
            if balance - amount < Decimal("1000.00"):
                self.conn.rollback()
                print("Transaction declined. Minimum balance of ₹1000.00 must be maintained.")
                return
            self.cursor.execute(
                "UPDATE bank_accounts SET balance=balance-%s WHERE account_number=%s",
                (amount, account_number),
            )
            self.record_transaction(account_number, "DEBIT", amount, "Cash withdrawal")
            self.conn.commit()
            print(f"Withdrawal successful. ₹{amount:,.2f} debited.")
            self.show_balance(account_number)
        except Error:
            self.conn.rollback()
            raise

    def transaction_history(self, account_number):
        self.cursor.execute(
            """
            SELECT transaction_id, transaction_type, amount, note, created_at
            FROM bank_transactions
            WHERE account_number=%s
            ORDER BY transaction_id DESC LIMIT 20
            """,
            (account_number,),
        )
        rows = self.cursor.fetchall()
        print("\n--- Recent Transactions ---")
        if not rows:
            print("No transactions found.")
            return
        for tx in rows:
            print(
                f"#{tx[0]} | {tx[1]} | ₹{Decimal(tx[2]):,.2f} | "
                f"{tx[3] or '-'} | {tx[4]}"
            )

    def apply_for_loan(self, account_number):
        print("\n--- Loan Application ---")
        amount = read_amount("Loan amount requested (₹): ")
        purpose = input("Loan purpose: ").strip()
        if not purpose:
            print("Please enter the loan purpose.")
            return
        self.cursor.execute(
            """
            INSERT INTO bank_loans (account_number, amount, purpose)
            VALUES (%s, %s, %s)
            """,
            (account_number, amount, purpose),
        )
        self.conn.commit()
        print("Loan application submitted. Status: Pending.")

    def loan_status(self, account_number):
        self.cursor.execute(
            """
            SELECT loan_id, amount, purpose, status, created_at
            FROM bank_loans
            WHERE account_number=%s
            ORDER BY loan_id DESC
            """,
            (account_number,),
        )
        rows = self.cursor.fetchall()
        print("\n--- Your Loan Applications ---")
        if not rows:
            print("No loan applications found.")
            return
        for loan in rows:
            print(
                f"Loan #{loan[0]} | ₹{Decimal(loan[1]):,.2f} | "
                f"{loan[2]} | {loan[3]} | {loan[4]}"
            )

    def customer_service(self, account_number=None):
        print("\n--- Customer Service ---")
        message = input("Describe your issue: ").strip()
        if not message:
            print("Please enter a message.")
            return
        self.cursor.execute(
            "INSERT INTO bank_support (account_number, message) VALUES (%s, %s)",
            (account_number, message),
        )
        self.conn.commit()
        print("Support request submitted.")

    def change_pin(self, account_number):
        old_pin = input("Current 4-digit PIN: ").strip()
        new_pin = input("New 4-digit PIN: ").strip()
        if len(new_pin) != 4 or not new_pin.isdigit():
            print("New PIN must be exactly 4 digits.")
            return
        self.cursor.execute(
            """
            SELECT account_number FROM bank_accounts
            WHERE account_number=%s AND pin_hash=%s
            """,
            (account_number, hash_pin(old_pin)),
        )
        if not self.cursor.fetchone():
            print("Current PIN is incorrect.")
            return
        self.cursor.execute(
            "UPDATE bank_accounts SET pin_hash=%s WHERE account_number=%s",
            (hash_pin(new_pin), account_number),
        )
        self.conn.commit()
        print("PIN changed successfully.")

    def customer_menu(self, account_number, customer_name):
        while True:
            print(f"\n===== Welcome, {customer_name} =====")
            print("1. Check Balance")
            print("2. Credit / Deposit")
            print("3. Debit / Withdraw")
            print("4. Transaction History")
            print("5. Apply for Loan")
            print("6. View Loan Status")
            print("7. Customer Service")
            print("8. Change PIN")
            print("9. Logout")
            choice = input("Choose an option (1-9): ").strip()

            try:
                if choice == "1":
                    self.show_balance(account_number)
                elif choice == "2":
                    self.deposit(account_number)
                elif choice == "3":
                    self.withdraw(account_number)
                elif choice == "4":
                    self.transaction_history(account_number)
                elif choice == "5":
                    self.apply_for_loan(account_number)
                elif choice == "6":
                    self.loan_status(account_number)
                elif choice == "7":
                    self.customer_service(account_number)
                elif choice == "8":
                    self.change_pin(account_number)
                elif choice == "9":
                    print("Logged out successfully.")
                    break
                else:
                    print("Invalid option. Please choose 1-9.")
            except Error as err:
                self.conn.rollback()
                print("Database error:", err)

    def run(self):
        while True:
            print("\n===== SMART BANKING SYSTEM =====")
            print("1. Create Account")
            print("2. Customer Login")
            print("3. Customer Service")
            print("4. Exit")
            choice = input("Enter your choice (1-4): ").strip()

            try:
                if choice == "1":
                    self.create_account()
                elif choice == "2":
                    self.login()
                elif choice == "3":
                    self.customer_service()
                elif choice == "4":
                    print("Thank you for using Smart Banking System!")
                    break
                else:
                    print("Invalid choice. Please select 1-4.")
            except Error as err:
                self.conn.rollback()
                print("Database error:", err)


def main():
    bank = BankSystem()
    try:
        bank.connect()
        bank.run()
    except Error as err:
        print("MySQL error:", err)
    except Exception as err:
        print("Unexpected error:", err)
    finally:
        bank.close()


if __name__ == "__main__":
    main()
