import sqlite3
from datetime import datetime, date, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db, query_db, execute_db
from config import Config

# ==============================================================================
# 1. USER & AUTHENTICATION
# ==============================================================================

def get_user_by_id(user_id):
    return query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)

def get_user_by_university_id(university_id):
    return query_db("SELECT * FROM users WHERE university_id = ?", (university_id,), one=True)

def authenticate_user(university_id, password):
    user = get_user_by_university_id(university_id)
    if not user:
        return None, "Invalid University ID or credentials."
    if not user['is_active']:
        return None, "This account has been deactivated. Please contact the administrator."
    if not check_password_hash(user['password_hash'], password):
        return None, "Invalid password. Please check your credentials."
    return user, None

# ==============================================================================
# 2. NOTIFICATIONS & AUTOMATIC DUE REMINDERS
# ==============================================================================

def add_notification(user_id, title, message, notif_type='system'):
    return execute_db("""
        INSERT INTO notifications (user_id, title, message, type, is_read)
        VALUES (?, ?, ?, ?, 0)
    """, (user_id, title, message, notif_type))

def get_user_notifications(user_id, limit=50):
    return query_db("""
        SELECT * FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (user_id, limit))

def get_unread_notification_count(user_id):
    res = query_db("""
        SELECT COUNT(*) as cnt FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (user_id,), one=True)
    return res['cnt'] if res else 0

def mark_notification_read(notification_id, user_id):
    execute_db("""
        UPDATE notifications SET is_read = 1
        WHERE id = ? AND user_id = ?
    """, (notification_id, user_id))

def mark_all_notifications_read(user_id):
    execute_db("""
        UPDATE notifications SET is_read = 1
        WHERE user_id = ?
    """, (user_id,))

def check_and_generate_due_reminders(user_id):
    """
    Called upon user access (e.g. before request).
    Checks upcoming due dates (2 days before, on due date) and overdue items.
    Prevents duplicate notifications for the same event on the same day.
    """
    today = date.today()
    active_loans = query_db("""
        SELECT b.*, bk.title
        FROM borrowings b
        JOIN books bk ON b.book_id = bk.id
        WHERE b.user_id = ? AND b.status IN ('borrowed', 'overdue')
    """, (user_id,))

    for loan in active_loans:
        # due_date can be a date object or string in sqlite
        due_val = loan['due_date']
        if isinstance(due_val, str):
            due_date = datetime.strptime(due_val, '%Y-%m-%d').date()
        else:
            due_date = due_val

        days_remaining = (due_date - today).days

        # 1. Two days before due date
        if days_remaining == 2:
            title = f"Due Soon: '{loan['title']}'"
            # Check if reminder already sent today or for this loan
            existing = query_db("""
                SELECT id FROM notifications
                WHERE user_id = ? AND type = 'due_soon' AND title = ?
                  AND DATE(created_at) = DATE(?)
            """, (user_id, title, today.strftime('%Y-%m-%d')), one=True)
            if not existing:
                msg = f"Reminder: Your borrowed book '{loan['title']}' is due in 2 days on {due_date}. Please return or renew it to avoid overdue fines."
                add_notification(user_id, title, msg, 'due_soon')

        # 2. On the due date
        elif days_remaining == 0:
            title = f"Due Today: '{loan['title']}'"
            existing = query_db("""
                SELECT id FROM notifications
                WHERE user_id = ? AND type = 'due_soon' AND title = ?
                  AND DATE(created_at) = DATE(?)
            """, (user_id, title, today.strftime('%Y-%m-%d')), one=True)
            if not existing:
                msg = f"Alert: '{loan['title']}' is due today ({due_date}). Overdue fines of ₹{Config.FINE_RATE_PER_DAY:.0f}/day will start tomorrow if not returned."
                add_notification(user_id, title, msg, 'due_soon')

        # 3. Overdue (days_remaining < 0)
        elif days_remaining < 0:
            overdue_days = abs(days_remaining)
            # Update borrowing status to 'overdue' if not already
            if loan['status'] != 'overdue':
                execute_db("UPDATE borrowings SET status = 'overdue' WHERE id = ?", (loan['id'],))

            # Maintain fine record
            fine_amount = overdue_days * Config.FINE_RATE_PER_DAY
            existing_fine = query_db("SELECT * FROM fines WHERE borrowing_id = ?", (loan['id'],), one=True)
            if not existing_fine:
                execute_db("""
                    INSERT INTO fines (borrowing_id, user_id, overdue_days, amount, status)
                    VALUES (?, ?, ?, ?, 'unpaid')
                """, (loan['id'], user_id, overdue_days, fine_amount))
            elif existing_fine['status'] != 'paid':
                execute_db("""
                    UPDATE fines SET overdue_days = ?, amount = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (overdue_days, fine_amount, existing_fine['id']))

            # Notify user once per week or if not sent yet
            title = f"Overdue Alert: '{loan['title']}' ({overdue_days} Days)"
            existing_notif = query_db("""
                SELECT id FROM notifications
                WHERE user_id = ? AND type = 'overdue' AND title = ?
            """, (user_id, title), one=True)
            if not existing_notif:
                msg = f"Your borrowed book '{loan['title']}' is now {overdue_days} days overdue. An accumulated fine of ₹{fine_amount:.2f} (₹{Config.FINE_RATE_PER_DAY:.0f}/day) is applied. Please return immediately."
                add_notification(user_id, title, msg, 'overdue')

# ==============================================================================
# 3. CATALOGUE & BOOKS
# ==============================================================================

def get_all_categories():
    return query_db("SELECT * FROM categories ORDER BY name ASC")

def get_books_catalog(search_query='', category_id=None, availability='all', sort_by='title_asc', page=1, per_page=12):
    params = []
    where_clauses = ["1=1"]

    if search_query:
        where_clauses.append("(b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ?)")
        s_term = f"%{search_query.strip()}%"
        params.extend([s_term, s_term, s_term])

    if category_id:
        try:
            cat_id = int(category_id)
            if cat_id > 0:
                where_clauses.append("b.category_id = ?")
                params.append(cat_id)
        except ValueError:
            pass

    order_clause = "b.title ASC"
    if sort_by == 'title_desc':
        order_clause = "b.title DESC"
    elif sort_by == 'year_desc':
        order_clause = "b.publication_year DESC"
    elif sort_by == 'author_asc':
        order_clause = "b.author ASC"
    elif sort_by == 'newest':
        order_clause = "b.id DESC"

    where_sql = " AND ".join(where_clauses)

    query = f"""
        SELECT b.*, c.name as category_name,
            (SELECT COUNT(*) FROM book_copies bc WHERE bc.book_id = b.id) as total_copies,
            (SELECT COUNT(*) FROM book_copies bc WHERE bc.book_id = b.id AND bc.status = 'available') as available_copies,
            (SELECT COUNT(*) FROM reservations r WHERE r.book_id = b.id AND r.status IN ('pending', 'ready_for_pickup')) as waiting_reservations
        FROM books b
        JOIN categories c ON b.category_id = c.id
        WHERE {where_sql}
        ORDER BY {order_clause}
    """
    all_results = query_db(query, params)

    # Filter by availability in memory if requested
    filtered = []
    for row in all_results:
        if availability == 'available' and row['available_copies'] <= 0:
            continue
        elif availability == 'unavailable' and row['available_copies'] > 0:
            continue
        filtered.append(row)

    total_count = len(filtered)
    offset = (page - 1) * per_page
    paginated = filtered[offset:offset + per_page]

    return paginated, total_count

def get_book_details(book_id):
    book = query_db("""
        SELECT b.*, c.name as category_name,
            (SELECT COUNT(*) FROM book_copies bc WHERE bc.book_id = b.id) as total_copies,
            (SELECT COUNT(*) FROM book_copies bc WHERE bc.book_id = b.id AND bc.status = 'available') as available_copies
        FROM books b
        JOIN categories c ON b.category_id = c.id
        WHERE b.id = ?
    """, (book_id,), one=True)
    return book

def get_book_copies(book_id):
    return query_db("""
        SELECT bc.*, 
            (SELECT u.name FROM borrowings b JOIN users u ON b.user_id = u.id 
             WHERE b.copy_id = bc.id AND b.status IN ('borrowed', 'return_pending', 'overdue') LIMIT 1) as current_borrower,
            (SELECT b.due_date FROM borrowings b 
             WHERE b.copy_id = bc.id AND b.status IN ('borrowed', 'return_pending', 'overdue') LIMIT 1) as due_date
        FROM book_copies bc
        WHERE bc.book_id = ?
        ORDER BY bc.id ASC
    """, (book_id,))

# ==============================================================================
# 4. CIRCULATION: SELF-SERVICE BORROWING
# ==============================================================================

def borrow_book(user_id, book_id):
    """
    Self-service borrowing with database transaction consistency.
    Validates limits, eligibility, allocates 1 available physical copy,
    generates issue & due dates, updates inventory, and creates confirmation notification.
    """
    db = get_db()
    today = date.today()

    # 1. Verify user eligibility
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not user or not user['is_active']:
        return False, "User account is not active or invalid."

    # 2. Check active loans against borrow limit
    active_count_res = query_db("""
        SELECT COUNT(*) as count FROM borrowings
        WHERE user_id = ? AND status IN ('borrowed', 'return_pending', 'overdue')
    """, (user_id,), one=True)
    current_active = active_count_res['count'] if active_count_res else 0

    max_limit = user['max_borrow_limit']
    if current_active >= max_limit:
        return False, f"Borrowing limit reached ({current_active}/{max_limit} books). Please return a book before issuing a new one."

    # 3. Check if user has already borrowed this specific book
    already_borrowed = query_db("""
        SELECT id FROM borrowings
        WHERE user_id = ? AND book_id = ? AND status IN ('borrowed', 'return_pending', 'overdue')
    """, (user_id, book_id), one=True)
    if already_borrowed:
        return False, "You already have an active loan for this book title."

    # 4. Check if user has a 'ready_for_pickup' reservation for this book
    res_ready = query_db("""
        SELECT * FROM reservations
        WHERE user_id = ? AND book_id = ? AND status = 'ready_for_pickup'
    """, (user_id, book_id), one=True)

    allocated_copy = None
    if res_ready and res_ready['copy_id']:
        # User is picking up their reserved copy
        allocated_copy = query_db("""
            SELECT * FROM book_copies WHERE id = ? AND status = 'reserved'
        """, (res_ready['copy_id'],), one=True)
    
    if not allocated_copy:
        # Check standard available copies
        allocated_copy = query_db("""
            SELECT * FROM book_copies
            WHERE book_id = ? AND status = 'available'
            ORDER BY id ASC
            LIMIT 1
        """, (book_id,), one=True)

    if not allocated_copy:
        return False, "No physical copies are currently available for this title. You may reserve it to join the waiting queue."

    # 5. Loan duration based on user role
    loan_days = Config.FACULTY_LOAN_DAYS if user['role'] == 'faculty' else Config.STUDENT_LOAN_DAYS
    due_date = today + timedelta(days=loan_days)

    try:
        # Atomic Transaction
        db.execute("BEGIN TRANSACTION")

        # Update copy status to borrowed
        db.execute("UPDATE book_copies SET status = 'borrowed' WHERE id = ?", (allocated_copy['id'],))

        # Insert borrowing record
        cur = db.execute("""
            INSERT INTO borrowings (user_id, copy_id, book_id, issue_date, due_date, status, renewal_count)
            VALUES (?, ?, ?, ?, ?, 'borrowed', 0)
        """, (user_id, allocated_copy['id'], book_id, today, due_date))
        borrowing_id = cur.lastrowid

        # If user had a ready reservation, mark it fulfilled
        if res_ready:
            db.execute("UPDATE reservations SET status = 'fulfilled' WHERE id = ?", (res_ready['id'],))

        # Get book title for notification
        book = query_db("SELECT title FROM books WHERE id = ?", (book_id,), one=True)
        title = book['title'] if book else 'Book'

        # Generate confirmation notification
        db.execute("""
            INSERT INTO notifications (user_id, title, message, type, is_read)
            VALUES (?, ?, ?, 'borrow', 0)
        """, (user_id, f"Book Issued: {title}", 
              f"You have borrowed '{title}' (Copy: {allocated_copy['copy_code']}). Due date is {due_date.strftime('%d %B %Y')}."))

        db.commit()
        return True, f"Successfully borrowed '{title}'. Due date: {due_date.strftime('%d %B %Y')} (Copy code: {allocated_copy['copy_code']})."

    except Exception as e:
        db.rollback()
        return False, f"Failed to issue book: {str(e)}"

# ==============================================================================
# 5. RESERVATION QUEUE SYSTEM
# ==============================================================================

def reserve_book(user_id, book_id):
    """
    Queue-based reservation system:
    Allowed only when all physical copies are unavailable.
    Prevents duplicate active reservations. Assigns queue position.
    """
    db = get_db()

    # 1. Check if copies are available
    available_copies = query_db("""
        SELECT COUNT(*) as cnt FROM book_copies
        WHERE book_id = ? AND status = 'available'
    """, (book_id,), one=True)
    if available_copies and available_copies['cnt'] > 0:
        return False, "This book has copies physically available right now. Please borrow directly instead of reserving."

    # 2. Check if user already has an active reservation
    existing_res = query_db("""
        SELECT * FROM reservations
        WHERE user_id = ? AND book_id = ? AND status IN ('pending', 'ready_for_pickup')
    """, (user_id, book_id), one=True)
    if existing_res:
        return False, f"You already have an active reservation for this book (Status: {existing_res['status'].replace('_', ' ').title()})."

    # 3. Check if user is currently borrowing this book
    currently_borrowing = query_db("""
        SELECT id FROM borrowings
        WHERE user_id = ? AND book_id = ? AND status IN ('borrowed', 'return_pending', 'overdue')
    """, (user_id, book_id), one=True)
    if currently_borrowing:
        return False, "You currently have this book issued. You cannot reserve a book you already hold."

    # 4. Calculate next queue position
    pos_res = query_db("""
        SELECT COALESCE(MAX(queue_position), 0) + 1 as next_pos
        FROM reservations
        WHERE book_id = ? AND status = 'pending'
    """, (book_id,), one=True)
    next_pos = pos_res['next_pos'] if pos_res else 1

    try:
        cur = db.execute("""
            INSERT INTO reservations (user_id, book_id, status, queue_position)
            VALUES (?, ?, 'pending', ?)
        """, (user_id, book_id, next_pos))
        res_id = cur.lastrowid

        book = query_db("SELECT title FROM books WHERE id = ?", (book_id,), one=True)
        title = book['title'] if book else 'Book'

        db.execute("""
            INSERT INTO notifications (user_id, title, message, type, is_read)
            VALUES (?, ?, ?, 'reservation', 0)
        """, (user_id, f"Reservation Placed: {title}",
              f"You have joined the reservation queue for '{title}' at Queue Position #{next_pos}. You will be notified when a copy is ready."))

        db.commit()
        return True, f"Reservation confirmed! You are at Position #{next_pos} in the waiting queue for '{title}'."
    except Exception as e:
        db.rollback()
        return False, f"Error placing reservation: {str(e)}"

def cancel_reservation(reservation_id, user_id=None):
    """
    Cancels a reservation. If user_id is provided, checks ownership.
    Re-indexes queue positions. If the reservation was 'ready_for_pickup',
    reallocates the copy to the next queued user or marks copy available.
    """
    db = get_db()
    query = "SELECT * FROM reservations WHERE id = ?"
    args = [reservation_id]
    if user_id:
        query += " AND user_id = ?"
        args.append(user_id)

    res = query_db(query, args, one=True)
    if not res:
        return False, "Reservation not found or access unauthorized."

    if res['status'] not in ('pending', 'ready_for_pickup'):
        return False, f"Cannot cancel reservation with status '{res['status']}'."

    book_id = res['book_id']
    allocated_copy_id = res['copy_id']
    was_ready = (res['status'] == 'ready_for_pickup')

    try:
        db.execute("BEGIN TRANSACTION")

        # Mark cancelled
        db.execute("UPDATE reservations SET status = 'cancelled' WHERE id = ?", (reservation_id,))

        # Re-index remaining pending queue positions
        remaining = query_db("""
            SELECT id FROM reservations
            WHERE book_id = ? AND status = 'pending'
            ORDER BY queue_position ASC
        """, (book_id,))
        for idx, item in enumerate(remaining, start=1):
            db.execute("UPDATE reservations SET queue_position = ? WHERE id = ?", (idx, item['id']))

        # If copy was allocated for pickup, reassign it
        if was_ready and allocated_copy_id:
            next_user_res = query_db("""
                SELECT * FROM reservations
                WHERE book_id = ? AND status = 'pending'
                ORDER BY queue_position ASC LIMIT 1
            """, (book_id,), one=True)

            if next_user_res:
                deadline = date.today() + timedelta(days=Config.RESERVATION_PICKUP_DAYS)
                db.execute("""
                    UPDATE reservations
                    SET status = 'ready_for_pickup', copy_id = ?, pickup_deadline = ?, queue_position = 0
                    WHERE id = ?
                """, (allocated_copy_id, deadline, next_user_res['id']))

                # Notify next user
                book = query_db("SELECT title FROM books WHERE id = ?", (book_id,), one=True)
                title = book['title'] if book else 'Book'
                db.execute("""
                    INSERT INTO notifications (user_id, title, message, type, is_read)
                    VALUES (?, ?, ?, 'available', 0)
                """, (next_user_res['user_id'], f"Reserved Book Ready: {title}",
                      f"Great news! '{title}' is now ready for pickup at the library desk. Please collect it before {deadline.strftime('%d %B %Y')}."))
            else:
                # No more reservations waiting; return copy to inventory
                db.execute("UPDATE book_copies SET status = 'available' WHERE id = ?", (allocated_copy_id,))

        db.commit()
        return True, "Reservation successfully cancelled."
    except Exception as e:
        db.rollback()
        return False, f"Failed to cancel reservation: {str(e)}"

# ==============================================================================
# 6. RENEWALS & RETURN REQUESTS
# ==============================================================================

def renew_book(user_id, borrowing_id):
    """
    Renew book:
    - Max 2 renewals.
    - Blocked if another user is waiting in reservation queue.
    - Updates due date by 14 days.
    """
    db = get_db()
    today = date.today()

    loan = query_db("""
        SELECT b.*, bk.title, bk.id as book_id
        FROM borrowings b
        JOIN books bk ON b.book_id = bk.id
        WHERE b.id = ? AND b.user_id = ?
    """, (borrowing_id, user_id), one=True)

    if not loan:
        return False, "Borrowing record not found or access unauthorized."

    if loan['status'] not in ('borrowed', 'overdue'):
        return False, f"Cannot renew a book with status '{loan['status']}'."

    if loan['renewal_count'] >= Config.MAX_RENEWALS:
        return False, f"Renewal limit reached ({loan['renewal_count']}/{Config.MAX_RENEWALS}). You must return this book."

    # Check if another user is waiting in reservation queue
    reservations_waiting = query_db("""
        SELECT COUNT(*) as cnt FROM reservations
        WHERE book_id = ? AND status = 'pending'
    """, (loan['book_id'],), one=True)

    if reservations_waiting and reservations_waiting['cnt'] > 0:
        return False, "Renewal blocked: Another student or faculty member is waiting in the reservation queue for this book."

    # Parse current due date
    due_val = loan['due_date']
    if isinstance(due_val, str):
        current_due = datetime.strptime(due_val, '%Y-%m-%d').date()
    else:
        current_due = due_val

    # If overdue, renew from today, else extend from current due date
    base_date = max(current_due, today)
    new_due = base_date + timedelta(days=Config.RENEWAL_EXTENSION_DAYS)
    new_count = loan['renewal_count'] + 1

    try:
        db.execute("""
            UPDATE borrowings
            SET due_date = ?, renewal_count = ?, status = 'borrowed'
            WHERE id = ?
        """, (new_due, new_count, borrowing_id))

        db.execute("""
            INSERT INTO notifications (user_id, title, message, type, is_read)
            VALUES (?, ?, ?, 'renewal', 0)
        """, (user_id, f"Renewal Confirmed: {loan['title']}",
              f"'{loan['title']}' has been renewed. New due date is {new_due.strftime('%d %B %Y')} (Renewal {new_count}/{Config.MAX_RENEWALS})."))

        db.commit()
        return True, f"Successfully renewed '{loan['title']}'! New due date: {new_due.strftime('%d %B %Y')}."
    except Exception as e:
        db.rollback()
        return False, f"Error renewing book: {str(e)}"

def request_return(user_id, borrowing_id):
    """
    Student/Faculty initiates a return request.
    Copy status and borrowing status become 'return_pending'.
    Book is NEVER marked available until librarian confirms physical receipt!
    """
    db = get_db()
    today = date.today()

    loan = query_db("""
        SELECT b.*, bk.title
        FROM borrowings b
        JOIN books bk ON b.book_id = bk.id
        WHERE b.id = ? AND b.user_id = ?
    """, (borrowing_id, user_id), one=True)

    if not loan:
        return False, "Borrowing record not found."

    if loan['status'] in ('returned', 'return_pending'):
        return False, f"This book return is already {loan['status'].replace('_', ' ')}."

    try:
        db.execute("BEGIN TRANSACTION")

        db.execute("""
            UPDATE borrowings
            SET status = 'return_pending', return_request_date = ?
            WHERE id = ?
        """, (today, borrowing_id))

        db.execute("UPDATE book_copies SET status = 'return_pending' WHERE id = ?", (loan['copy_id'],))

        db.execute("""
            INSERT INTO notifications (user_id, title, message, type, is_read)
            VALUES (?, ?, ?, 'return', 0)
        """, (user_id, f"Return Initiated: {loan['title']}",
              f"You have submitted a return request for '{loan['title']}'. Please drop off the book at the library circulation desk for librarian verification."))

        db.commit()
        return True, f"Return initiated for '{loan['title']}'. Please hand the physical book to the library desk for confirmation."
    except Exception as e:
        db.rollback()
        return False, f"Failed to initiate return: {str(e)}"

def confirm_physical_return(borrowing_id, librarian_id, condition='Good'):
    """
    Librarian verifies and confirms physical receipt of the book:
    1. Updates borrowing to 'returned' with return_date = today.
    2. Calculates final fine: ₹5 per day overdue.
    3. Processes reservation queue: allocates copy to next waiting user if any,
       otherwise marks copy available.
    """
    db = get_db()
    today = date.today()

    loan = query_db("""
        SELECT b.*, bk.title, bk.id as book_id, u.name as user_name
        FROM borrowings b
        JOIN books bk ON b.book_id = bk.id
        JOIN users u ON b.user_id = u.id
        WHERE b.id = ?
    """, (borrowing_id,), one=True)

    if not loan:
        return False, "Borrowing record not found."

    if loan['status'] == 'returned':
        return False, "This book has already been marked as returned."

    copy_id = loan['copy_id']
    book_id = loan['book_id']
    user_id = loan['user_id']

    # Parse due_date
    due_val = loan['due_date']
    if isinstance(due_val, str):
        due_date = datetime.strptime(due_val, '%Y-%m-%d').date()
    else:
        due_date = due_val

    # Fine calculation: ₹5 per day overdue
    overdue_days = max(0, (today - due_date).days)
    fine_amount = overdue_days * Config.FINE_RATE_PER_DAY

    try:
        db.execute("BEGIN TRANSACTION")

        # 1. Update borrowing record
        db.execute("""
            UPDATE borrowings
            SET status = 'returned', return_date = ?
            WHERE id = ?
        """, (today, borrowing_id))

        # 2. Update physical copy condition
        db.execute("UPDATE book_copies SET condition = ? WHERE id = ?", (condition, copy_id))

        # 3. Fine calculation and record
        if fine_amount > 0:
            existing_fine = query_db("SELECT * FROM fines WHERE borrowing_id = ?", (borrowing_id,), one=True)
            if existing_fine:
                db.execute("""
                    UPDATE fines
                    SET overdue_days = ?, amount = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (overdue_days, fine_amount, existing_fine['id']))
            else:
                db.execute("""
                    INSERT INTO fines (borrowing_id, user_id, overdue_days, amount, status)
                    VALUES (?, ?, ?, ?, 'unpaid')
                """, (borrowing_id, user_id, overdue_days, fine_amount))

            db.execute("""
                INSERT INTO notifications (user_id, title, message, type, is_read)
                VALUES (?, ?, ?, 'fine', 0)
            """, (user_id, f"Overdue Fine Generated: {loan['title']}",
                  f"Physical return confirmed. Since the book was {overdue_days} days overdue, a fine of ₹{fine_amount:.2f} has been added to your account."))

        # 4. Process Reservation Queue
        next_reservation = query_db("""
            SELECT * FROM reservations
            WHERE book_id = ? AND status = 'pending'
            ORDER BY queue_position ASC LIMIT 1
        """, (book_id,), one=True)

        if next_reservation:
            # Allocate copy to next in queue
            pickup_deadline = today + timedelta(days=Config.RESERVATION_PICKUP_DAYS)
            db.execute("""
                UPDATE reservations
                SET status = 'ready_for_pickup', copy_id = ?, pickup_deadline = ?, queue_position = 0
                WHERE id = ?
            """, (copy_id, pickup_deadline, next_reservation['id']))

            db.execute("UPDATE book_copies SET status = 'reserved' WHERE id = ?", (copy_id,))

            # Re-index remaining reservations
            remaining = query_db("""
                SELECT id FROM reservations
                WHERE book_id = ? AND status = 'pending'
                ORDER BY queue_position ASC
            """, (book_id,))
            for idx, item in enumerate(remaining, start=1):
                db.execute("UPDATE reservations SET queue_position = ? WHERE id = ?", (idx, item['id']))

            # Notify the reservation holder
            db.execute("""
                INSERT INTO notifications (user_id, title, message, type, is_read)
                VALUES (?, ?, ?, 'available', 0)
            """, (next_reservation['user_id'], f"Reserved Book Ready: {loan['title']}",
                  f"Your reserved title '{loan['title']}' has been returned and is reserved for you at the library desk. Please collect it before {pickup_deadline.strftime('%d %B %Y')}."))
        else:
            # No waiting reservations -> mark copy available
            db.execute("UPDATE book_copies SET status = 'available' WHERE id = ?", (copy_id,))

        # Notify returning user
        db.execute("""
            INSERT INTO notifications (user_id, title, message, type, is_read)
            VALUES (?, ?, ?, 'return', 0)
        """, (user_id, f"Return Verified: {loan['title']}",
              f"The library has verified and processed your physical return of '{loan['title']}'. Thank you!"))

        db.commit()
        return True, f"Return verified for '{loan['title']}' (Borrower: {loan['user_name']}). Fine: ₹{fine_amount:.2f}."
    except Exception as e:
        db.rollback()
        return False, f"Failed to confirm return: {str(e)}"

# ==============================================================================
# 7. FINE ENGINE & MANUAL PAYMENT RECORDING
# ==============================================================================

def get_user_fines(user_id):
    """Fetches all fines and their payment history for a user."""
    fines = query_db("""
        SELECT f.*, bk.title as book_title, b.issue_date, b.due_date, b.return_date,
            (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE fine_id = f.id) as total_paid,
            (f.amount - (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE fine_id = f.id)) as remaining_balance
        FROM fines f
        JOIN borrowings b ON f.borrowing_id = b.id
        JOIN books bk ON b.book_id = bk.id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC
    """, (user_id,))
    return fines

def get_all_fines():
    """Fetches all fines in the library for librarians."""
    return query_db("""
        SELECT f.*, u.name as user_name, u.university_id, bk.title as book_title,
            (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE fine_id = f.id) as total_paid,
            (f.amount - (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE fine_id = f.id)) as remaining_balance
        FROM fines f
        JOIN users u ON f.user_id = u.id
        JOIN borrowings b ON f.borrowing_id = b.id
        JOIN books bk ON b.book_id = bk.id
        ORDER BY f.created_at DESC
    """)

def record_manual_payment(fine_id, librarian_id, amount, payment_method, notes=''):
    """
    Librarian records a manual fine payment:
    Supports partial payments, validates payment doesn't exceed outstanding fine,
    updates status to 'paid' or 'partially_paid'.
    """
    db = get_db()
    try:
        amount = float(amount)
        if amount <= 0:
            return False, "Payment amount must be greater than zero."
    except ValueError:
        return False, "Invalid payment amount entered."

    fine = query_db("SELECT * FROM fines WHERE id = ?", (fine_id,), one=True)
    if not fine:
        return False, "Fine record not found."

    paid_so_far_res = query_db("""
        SELECT COALESCE(SUM(amount), 0) as total_paid FROM payments WHERE fine_id = ?
    """, (fine_id,), one=True)
    paid_so_far = paid_so_far_res['total_paid'] if paid_so_far_res else 0.0
    remaining_balance = fine['amount'] - paid_so_far

    if amount > remaining_balance + 0.001:  # slight floating point tolerance
        return False, f"Payment amount (₹{amount:.2f}) cannot exceed the remaining balance of ₹{remaining_balance:.2f}."

    try:
        db.execute("BEGIN TRANSACTION")

        # Insert payment record
        db.execute("""
            INSERT INTO payments (fine_id, user_id, librarian_id, amount, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fine_id, fine['user_id'], librarian_id, amount, payment_method, notes))

        new_total_paid = paid_so_far + amount
        if new_total_paid >= fine['amount'] - 0.001:
            new_status = 'paid'
        else:
            new_status = 'partially_paid'

        db.execute("""
            UPDATE fines SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (new_status, fine_id))

        # Notify student
        db.execute("""
            INSERT INTO notifications (user_id, title, message, type, is_read)
            VALUES (?, ?, ?, 'fine', 0)
        """, (fine['user_id'], f"Fine Payment Recorded (₹{amount:.2f})",
              f"The library recorded your payment of ₹{amount:.2f} via {payment_method}. Remaining fine balance: ₹{max(0.0, fine['amount'] - new_total_paid):.2f}."))

        db.commit()
        return True, f"Successfully recorded payment of ₹{amount:.2f} via {payment_method}. Fine status is now '{new_status.replace('_', ' ').title()}'."
    except Exception as e:
        db.rollback()
        return False, f"Error recording payment: {str(e)}"

# ==============================================================================
# 8. WISHLIST
# ==============================================================================

def add_to_wishlist(user_id, book_id):
    try:
        execute_db("INSERT INTO wishlists (user_id, book_id) VALUES (?, ?)", (user_id, book_id))
        return True, "Book added to your wishlist."
    except sqlite3.IntegrityError:
        return False, "This book is already in your wishlist."
    except Exception as e:
        return False, str(e)

def remove_from_wishlist(user_id, book_id):
    execute_db("DELETE FROM wishlists WHERE user_id = ? AND book_id = ?", (user_id, book_id))
    return True, "Removed from wishlist."

def get_user_wishlist(user_id):
    return query_db("""
        SELECT w.id as wishlist_id, w.created_at as added_on, bk.*, c.name as category_name,
            (SELECT COUNT(*) FROM book_copies bc WHERE bc.book_id = bk.id) as total_copies,
            (SELECT COUNT(*) FROM book_copies bc WHERE bc.book_id = bk.id AND bc.status = 'available') as available_copies
        FROM wishlists w
        JOIN books bk ON w.book_id = bk.id
        JOIN categories c ON bk.category_id = c.id
        WHERE w.user_id = ?
        ORDER BY w.created_at DESC
    """, (user_id,))

# ==============================================================================
# 9. DASHBOARD STATS
# ==============================================================================

def get_student_dashboard_data(user_id):
    today = date.today()

    # Active borrowings
    active_loans = query_db("""
        SELECT b.*, bk.title, bk.author, bk.isbn, bc.copy_code,
            CASE 
                WHEN b.due_date < DATE('now') THEN 1 
                ELSE 0 
            END as is_overdue,
            CAST(julianday('now') - julianday(b.due_date) AS INTEGER) as days_overdue
        FROM borrowings b
        JOIN books bk ON b.book_id = bk.id
        JOIN book_copies bc ON b.copy_id = bc.id
        WHERE b.user_id = ? AND b.status IN ('borrowed', 'return_pending', 'overdue')
        ORDER BY b.due_date ASC
    """, (user_id,))

    # Active reservations
    reservations = query_db("""
        SELECT r.*, bk.title, bk.author, bk.shelf_location,
            (SELECT COUNT(*) FROM book_copies bc WHERE bc.book_id = bk.id AND bc.status = 'available') as available_copies
        FROM reservations r
        JOIN books bk ON r.book_id = bk.id
        WHERE r.user_id = ? AND r.status IN ('pending', 'ready_for_pickup')
        ORDER BY r.created_at DESC
    """, (user_id,))

    # Upcoming due in <= 2 days
    upcoming_dues = [l for l in active_loans if l['status'] == 'borrowed' and 0 <= (datetime.strptime(str(l['due_date']), '%Y-%m-%d').date() - today).days <= 2]

    # Outstanding fines
    fines = query_db("""
        SELECT COALESCE(SUM(f.amount - (SELECT COALESCE(SUM(p.amount), 0) FROM payments p WHERE p.fine_id = f.id)), 0) as balance
        FROM fines f
        WHERE f.user_id = ? AND f.status IN ('unpaid', 'partially_paid')
    """, (user_id,), one=True)
    outstanding_fines = fines['balance'] if fines else 0.0

    # Recently added books
    recent_books = query_db("""
        SELECT b.*, c.name as category_name,
            (SELECT COUNT(*) FROM book_copies bc WHERE bc.book_id = b.id AND bc.status = 'available') as available_copies
        FROM books b
        JOIN categories c ON b.category_id = c.id
        ORDER BY b.id DESC LIMIT 4
    """)

    # Wishlist count
    wishlist_count_res = query_db("SELECT COUNT(*) as cnt FROM wishlists WHERE user_id = ?", (user_id,), one=True)
    wishlist_count = wishlist_count_res['cnt'] if wishlist_count_res else 0

    return {
        'active_loans': active_loans,
        'reservations': reservations,
        'upcoming_dues': upcoming_dues,
        'outstanding_fines': outstanding_fines,
        'recent_books': recent_books,
        'wishlist_count': wishlist_count
    }

def get_librarian_dashboard_data():
    today = date.today()

    titles_cnt = query_db("SELECT COUNT(*) as cnt FROM books", one=True)['cnt']
    copies_cnt = query_db("SELECT COUNT(*) as cnt FROM book_copies", one=True)['cnt']
    avail_cnt = query_db("SELECT COUNT(*) as cnt FROM book_copies WHERE status = 'available'", one=True)['cnt']
    borrowed_cnt = query_db("SELECT COUNT(*) as cnt FROM book_copies WHERE status = 'borrowed'", one=True)['cnt']
    pending_ret_cnt = query_db("SELECT COUNT(*) as cnt FROM borrowings WHERE status = 'return_pending'", one=True)['cnt']
    res_cnt = query_db("SELECT COUNT(*) as cnt FROM reservations WHERE status IN ('pending', 'ready_for_pickup')", one=True)['cnt']
    overdue_cnt = query_db("SELECT COUNT(*) as cnt FROM borrowings WHERE status = 'overdue' OR (status = 'borrowed' AND due_date < DATE('now'))", one=True)['cnt']

    fines_res = query_db("""
        SELECT COALESCE(SUM(f.amount - (SELECT COALESCE(SUM(p.amount), 0) FROM payments p WHERE p.fine_id = f.id)), 0) as balance
        FROM fines f
        WHERE f.status IN ('unpaid', 'partially_paid')
    """, one=True)
    outstanding_fines = fines_res['balance'] if fines_res else 0.0

    # Pending returns list for fast action
    pending_returns = query_db("""
        SELECT b.*, u.name as user_name, u.university_id, bk.title as book_title, bc.copy_code
        FROM borrowings b
        JOIN users u ON b.user_id = u.id
        JOIN books bk ON b.book_id = bk.id
        JOIN book_copies bc ON b.copy_id = bc.id
        WHERE b.status = 'return_pending'
        ORDER BY b.return_request_date ASC
    """)

    # Overdue list
    overdue_loans = query_db("""
        SELECT b.*, u.name as user_name, u.university_id, bk.title as book_title, bc.copy_code,
            CAST(julianday('now') - julianday(b.due_date) AS INTEGER) as days_overdue
        FROM borrowings b
        JOIN users u ON b.user_id = u.id
        JOIN books bk ON b.book_id = bk.id
        JOIN book_copies bc ON b.copy_id = bc.id
        WHERE b.status IN ('borrowed', 'overdue') AND b.due_date < DATE('now')
        ORDER BY b.due_date ASC LIMIT 8
    """)

    return {
        'titles_cnt': titles_cnt,
        'copies_cnt': copies_cnt,
        'avail_cnt': avail_cnt,
        'borrowed_cnt': borrowed_cnt,
        'pending_ret_cnt': pending_ret_cnt,
        'res_cnt': res_cnt,
        'overdue_cnt': overdue_cnt,
        'outstanding_fines': outstanding_fines,
        'pending_returns': pending_returns,
        'overdue_loans': overdue_loans
    }

def get_admin_dashboard_data():
    total_users = query_db("SELECT COUNT(*) as cnt FROM users", one=True)['cnt']
    students_cnt = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'student'", one=True)['cnt']
    faculty_cnt = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'faculty'", one=True)['cnt']
    librarians_cnt = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'librarian'", one=True)['cnt']
    admins_cnt = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'admin'", one=True)['cnt']
    active_cnt = query_db("SELECT COUNT(*) as cnt FROM users WHERE is_active = 1", one=True)['cnt']
    inactive_cnt = query_db("SELECT COUNT(*) as cnt FROM users WHERE is_active = 0", one=True)['cnt']

    recent_users = query_db("SELECT * FROM users ORDER BY id DESC LIMIT 10")

    return {
        'total_users': total_users,
        'students_cnt': students_cnt,
        'faculty_cnt': faculty_cnt,
        'librarians_cnt': librarians_cnt,
        'admins_cnt': admins_cnt,
        'active_cnt': active_cnt,
        'inactive_cnt': inactive_cnt,
        'recent_users': recent_users
    }
