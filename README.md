# LibSmart — Smart University Library Management System (MVP)

LibSmart is a complete, production-grade MVP of a Smart University Library Management System engineered using Python Flask, SQLite, and vanilla Bootstrap 5 with responsive academic UI design.

---

## 1. System Architecture & Tech Stack

- **Backend**: Python 3 (Flask 3.x, Werkzeug)
- **Database**: SQLite3 with foreign keys (`PRAGMA foreign_keys = ON;`)
- **Frontend**: HTML5, CSS3, JavaScript (ES6), Bootstrap 5.3, Bootstrap Icons 1.11
- **Design System / Palette**:
  - Forest Green: `#153D32`
  - Sage: `#E9F0E9`
  - Canvas Background: `#F5F7F5`
  - Accent / Gold: `#D69A42`
  - Card & Surface White: `#FFFFFF`

---

## 2. Demo User Accounts & Credentials

All demo user accounts are pre-seeded with password `password123` (Administrator uses `admin123`). The login page also features **1-Click Demo Buttons** to automatically fill credentials.

| Role | University ID | Full Name | Email | Password | Pre-configured Scenarios |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Student** | `STU001` | Aarav Sharma | `aarav.sharma@univ.edu` | `password123` | Active loan due in 8 days + Overdue loan (₹25 fine) |
| **Student** | `STU002` | Priya Patel | `priya.patel@univ.edu` | `password123` | Active loan with **Return Pending** verification |
| **Student** | `STU003` | Rohan Verma | `rohan.verma@univ.edu` | `password123` | **#1 in Reservation Queue** + Partially paid fine (₹15 paid, ₹15 balance) |
| **Student** | `STU004` | Ananya Iyer | `ananya.iyer@univ.edu` | `password123` | **#2 in Reservation Queue** for Deep Learning |
| **Student** | `STU005` | Vikram Singh | `vikram.singh@univ.edu` | `password123` | Active borrower with clean record |
| **Faculty** | `FAC001` | Dr. Rajesh Kumar | `rajesh.kumar@univ.edu` | `password123` | Higher limit (6 books), 30-day loans |
| **Faculty** | `FAC002` | Prof. Meera Nair | `meera.nair@univ.edu` | `password123` | Active research loans |
| **Librarian** | `LIB001` | Sunita Deshmukh | `sunita.deshmukh@univ.edu` | `password123` | Chief Librarian (Returns, Fines, Catalogue) |
| **Librarian** | `LIB002` | Manoj Kulkarni | `manoj.kulkarni@univ.edu` | `password123` | Assistant Librarian (Circulation Desk) |
| **Admin** | `ADM001` | System Admin | `admin@univ.edu` | `admin123` | User account & role administration |

---

## 3. Installation & Running Instructions

### Prerequisites
- Python 3.10+ installed
- `pip` package manager

### Step 1: Install Dependencies
Open PowerShell or Command Prompt in the project directory:
```bash
pip install -r requirements.txt
```

### Step 2: (Optional) Re-seed the Database
The project comes with a pre-seeded `libsmart.db`. To reset to the pristine demo dataset at any time, run:
```bash
python seed.py
```

### Step 3: Start the Flask Application
```bash
python app.py
```
The server will start at:
```
http://127.0.0.1:5000/
```

### Step 4: Run the Complete Test Suite
To run all 15 automated workflow tests:
```bash
python -m unittest test_app.py -v
```

---

## 4. Key Workflows & Business Rules

### A. Self-Service Borrowing
1. Patrons navigate the Catalogue and click **Borrow**.
2. The system checks account status and borrow limits (Student: 3, Faculty: 6).
3. Allocates 1 physical copy with `status = 'available'`.
4. Computes due date: 14 days for students, 30 days for faculty.
5. Performs atomic database transaction and generates an in-app confirmation notification.

### B. Queue-Based Reservations
1. When all physical copies of a title are out on loan, the **Reserve** button is enabled.
2. Patrons join a priority queue (FIFO).
3. Duplicate reservations for the same title are strictly blocked.
4. When a librarian verifies a returned copy, the system automatically allocates the copy to the patron at Queue Position #1, sets status to `ready_for_pickup`, applies a 3-day pickup deadline, and sends an availability alert.

### C. Renewals & Returns
- **Renewals**: Patrons may renew eligible books up to 2 times (+14 days). Renewals are blocked if another patron is waiting in the reservation queue.
- **Returns**: Patrons initiate return requests $\rightarrow$ loan status changes to `return_pending`. The book copy remains physically unavailable until the librarian inspects and confirms the return.

### D. Overdue Fines & Manual Payments
- **Fine Policy**: ₹5.00 per overdue day, starting the day after the due date with no grace period.
- Stops accumulating on the date of confirmed physical return.
- Librarians can record manual over-the-counter payments (Cash, Card, Bank Transfer, or UPI manual reference entry).
- Partial payments are supported; payments exceeding the outstanding balance are prevented.

### E. Notification System & Browser Notification API
- In-app notification center tracks due warnings (2 days before and on due date), overdue alerts, and reservation pickup readiness.
- Desktop browser notification permission toggle is supported via the HTML5 Browser Notification API.

---

## 5. Database Schema (10 SQLite Tables)

1. `users` — Authentication, University ID, roles, max borrow limits, and activation status.
2. `categories` — Academic disciplines.
3. `books` — Bibliographic metadata (ISBN, title, author, publisher, shelf coordinate).
4. `book_copies` — Physical inventory tracking individual barcodes, conditions, and availability.
5. `borrowings` — Circulation transactions, issue dates, due dates, return dates, and renewal counts.
6. `reservations` — Waiting queue positions, pickup deadlines, and hold statuses.
7. `wishlists` — Private user book bookmarks.
8. `fines` — Overdue day counts, fine amounts, and statuses (`unpaid`, `partially_paid`, `paid`).
9. `payments` — Manual audit logs for librarian-recorded payments.
10. `notifications` — In-app alerts, read states, and alert timestamps.

# LibSmart--Smart-University-Library-Management-System