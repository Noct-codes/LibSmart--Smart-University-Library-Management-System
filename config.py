import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'libsmart-secure-university-key-2026-prod')
    DATABASE = os.path.join(BASE_DIR, 'libsmart.db')
    
    # Circulation Policies
    FINE_RATE_PER_DAY = 5.0          # ₹5 per overdue day
    STUDENT_BORROW_LIMIT = 3        # Maximum books for students
    STUDENT_LOAN_DAYS = 14          # Loan duration in days for students
    FACULTY_BORROW_LIMIT = 6        # Maximum books for faculty
    FACULTY_LOAN_DAYS = 30          # Loan duration in days for faculty
    MAX_RENEWALS = 2                # Maximum renewals allowed
    RENEWAL_EXTENSION_DAYS = 14     # Days added on renewal
    RESERVATION_PICKUP_DAYS = 3     # Days allowed for user to pick up reserved book
    DUE_WARNING_DAYS = 2            # Notify user 2 days before due date
