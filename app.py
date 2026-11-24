import math
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash
from config import Config
from database import close_db, get_db, query_db, execute_db
import models

app = Flask(__name__)
app.config.from_object(Config)

# Register teardown
app.teardown_appcontext(close_db)

# ==============================================================================
# AUTHENTICATION & ACCESS CONTROL HELPERS
# ==============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access the library portal.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please sign in to proceed.", "warning")
                return redirect(url_for('login'))
            user_role = session.get('role')
            if user_role not in allowed_roles:
                flash(f"Access denied. This section is restricted to {', '.join(allowed_roles)} accounts.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.before_request
def load_user_and_reminders():
    """Runs on every request: loads active user and refreshes due-date alerts."""
    g.user = None
    if 'user_id' in session:
        user = models.get_user_by_id(session['user_id'])
        if user and user['is_active']:
            g.user = user
            # Trigger due-date reminder checks upon user access (Section 9 Requirement)
            models.check_and_generate_due_reminders(user['id'])
        else:
            session.clear()

@app.context_processor
def inject_global_data():
    """Injects unread notification counts and user role into all templates."""
    unread_count = 0
    if g.user:
        unread_count = models.get_unread_notification_count(g.user['id'])
    return {
        'unread_notification_count': unread_count,
        'current_user': g.user
    }

# ==============================================================================
# AUTHENTICATION ROUTES
# ==============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        university_id = request.form.get('university_id', '').strip()
        password = request.form.get('password', '')

        user, err = models.authenticate_user(university_id, password)
        if err:
            flash(err, 'danger')
            return render_template('login.html')

        # Set session
        session['user_id'] = user['id']
        session['university_id'] = user['university_id']
        session['name'] = user['name']
        session['role'] = user['role']

        flash(f"Welcome back, {user['name']}!", 'success')
        next_url = request.args.get('next')
        return redirect(next_url or url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('login'))

# ==============================================================================
# DASHBOARD ROUTER
# ==============================================================================

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')

    if role in ('student', 'faculty'):
        data = models.get_student_dashboard_data(session['user_id'])
        return render_template('dashboard_student.html', user=g.user, data=data)

    elif role == 'librarian':
        data = models.get_librarian_dashboard_data()
        return render_template('dashboard_librarian.html', data=data)

    elif role == 'admin':
        data = models.get_admin_dashboard_data()
        return render_template('dashboard_admin.html', data=data)

    return redirect(url_for('catalogue'))

# ==============================================================================
# BOOK CATALOGUE & DETAILS
# ==============================================================================

@app.route('/catalogue')
def catalogue():
    search_query = request.args.get('q', '').strip()
    category_id = request.args.get('category', '')
    availability = request.args.get('availability', 'all')
    sort_by = request.args.get('sort', 'title_asc')
    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1
    per_page = 12

    books, total_count = models.get_books_catalog(
        search_query=search_query,
        category_id=category_id,
        availability=availability,
        sort_by=sort_by,
        page=page,
        per_page=per_page
    )

    categories = models.get_all_categories()
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1

    return render_template('catalogue.html',
                           books=books,
                           categories=categories,
                           search_query=search_query,
                           selected_category=category_id,
                           selected_availability=availability,
                           selected_sort=sort_by,
                           current_page=page,
                           total_pages=total_pages,
                           total_count=total_count)

@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = models.get_book_details(book_id)
    if not book:
        flash("The requested book title does not exist in the catalogue.", "danger")
        return redirect(url_for('catalogue'))

    copies = models.get_book_copies(book_id)
    return render_template('book_detail.html', book=book, copies=copies)

# ==============================================================================
# STUDENT / FACULTY CIRCULATION ACTIONS
# ==============================================================================

@app.route('/borrow/<int:book_id>', methods=['POST'])
@login_required
@role_required('student', 'faculty')
def self_borrow(book_id):
    success, msg = models.borrow_book(session['user_id'], book_id)
    flash(msg, 'success' if success else 'danger')
    return redirect(request.referrer or url_for('book_detail', book_id=book_id))

@app.route('/reserve/<int:book_id>', methods=['POST'])
@login_required
@role_required('student', 'faculty')
def place_reservation(book_id):
    success, msg = models.reserve_book(session['user_id'], book_id)
    flash(msg, 'success' if success else 'warning')
    return redirect(request.referrer or url_for('book_detail', book_id=book_id))

@app.route('/reservation/<int:res_id>/cancel', methods=['POST'])
@login_required
def user_cancel_reservation(res_id):
    # Only cancel if user owns this reservation or is librarian
    user_id = None if session.get('role') == 'librarian' else session['user_id']
    success, msg = models.cancel_reservation(res_id, user_id=user_id)
    flash(msg, 'success' if success else 'danger')
    return redirect(request.referrer or url_for('my_reservations'))

@app.route('/renew/<int:loan_id>', methods=['POST'])
@login_required
@role_required('student', 'faculty')
def renew_loan(loan_id):
    success, msg = models.renew_book(session['user_id'], loan_id)
    flash(msg, 'success' if success else 'danger')
    return redirect(request.referrer or url_for('my_borrowings'))

@app.route('/return/<int:loan_id>', methods=['POST'])
@login_required
@role_required('student', 'faculty')
def initiate_return(loan_id):
    success, msg = models.request_return(session['user_id'], loan_id)
    flash(msg, 'success' if success else 'danger')
    return redirect(request.referrer or url_for('my_borrowings'))

@app.route('/my-borrowings')
@login_required
@role_required('student', 'faculty')
def my_borrowings():
    user_id = session['user_id']

    # Active loans
    active_loans = query_db("""
        SELECT b.*, bk.title, bk.author, bk.shelf_location, bc.copy_code,
            CASE WHEN b.due_date < DATE('now') THEN 1 ELSE 0 END as is_overdue,
            CAST(julianday('now') - julianday(b.due_date) AS INTEGER) as days_overdue,
            CAST(julianday(b.due_date) - julianday('now') AS INTEGER) as days_remaining
        FROM borrowings b
        JOIN books bk ON b.book_id = bk.id
        JOIN book_copies bc ON b.copy_id = bc.id
        WHERE b.user_id = ? AND b.status IN ('borrowed', 'return_pending', 'overdue')
        ORDER BY b.due_date ASC
    """, (user_id,))

    # Past returned history
    past_loans = query_db("""
        SELECT b.*, bk.title, bc.copy_code,
            (SELECT amount FROM fines WHERE borrowing_id = b.id) as fine_amount,
            (SELECT status FROM fines WHERE borrowing_id = b.id) as fine_status
        FROM borrowings b
        JOIN books bk ON b.book_id = bk.id
        JOIN book_copies bc ON b.copy_id = bc.id
        WHERE b.user_id = ? AND b.status = 'returned'
        ORDER BY b.return_date DESC
    """, (user_id,))

    return render_template('my_borrowings.html', active_loans=active_loans, past_loans=past_loans)

@app.route('/my-reservations')
@login_required
@role_required('student', 'faculty')
def my_reservations():
    user_id = session['user_id']
    reservations = query_db("""
        SELECT r.*, bk.title, bk.author, bk.shelf_location,
            (SELECT copy_code FROM book_copies WHERE id = r.copy_id) as copy_code
        FROM reservations r
        JOIN books bk ON r.book_id = bk.id
        WHERE r.user_id = ? AND r.status IN ('pending', 'ready_for_pickup')
        ORDER BY r.created_at DESC
    """, (user_id,))
    return render_template('my_reservations.html', reservations=reservations)

@app.route('/my-wishlist')
@login_required
@role_required('student', 'faculty')
def my_wishlist():
    items = models.get_user_wishlist(session['user_id'])
    return render_template('my_wishlist.html', wishlist_items=items)

@app.route('/wishlist/toggle/<int:book_id>', methods=['POST'])
@login_required
@role_required('student', 'faculty')
def toggle_wishlist(book_id):
    user_id = session['user_id']
    exists = query_db("SELECT id FROM wishlists WHERE user_id = ? AND book_id = ?", (user_id, book_id), one=True)
    if exists:
        models.remove_from_wishlist(user_id, book_id)
        flash("Book removed from your wishlist.", "info")
    else:
        success, msg = models.add_to_wishlist(user_id, book_id)
        flash(msg, "success" if success else "warning")
    return redirect(request.referrer or url_for('my_wishlist'))

@app.route('/my-fines')
@login_required
@role_required('student', 'faculty')
def my_fines():
    user_id = session['user_id']
    fines = models.get_user_fines(user_id)

    total_outstanding = sum(f['remaining_balance'] for f in fines if f['remaining_balance'] > 0)
    total_paid_all = sum(f['total_paid'] for f in fines)

    return render_template('my_fines.html', fines=fines, total_outstanding=total_outstanding, total_paid_all=total_paid_all)

# ==============================================================================
# NOTIFICATIONS CENTER
# ==============================================================================

@app.route('/notifications')
@login_required
def notifications():
    user_id = session['user_id']
    notifs = models.get_user_notifications(user_id)
    return render_template('notifications.html', notifications=notifs)

@app.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_single_read(notif_id):
    models.mark_notification_read(notif_id, session['user_id'])
    return redirect(request.referrer or url_for('notifications'))

@app.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    models.mark_all_notifications_read(session['user_id'])
    flash("All notifications marked as read.", "success")
    return redirect(url_for('notifications'))

# ==============================================================================
# LIBRARIAN OPERATIONS & CIRCULATION DESK
# ==============================================================================

@app.route('/librarian/returns')
@login_required
@role_required('librarian')
def librarian_returns():
    pending = query_db("""
        SELECT b.*, u.name as user_name, u.university_id, u.role as user_role,
               bk.title as book_title, bk.isbn, bc.copy_code,
               CASE WHEN b.due_date < DATE('now') THEN 1 ELSE 0 END as is_overdue,
               CAST(julianday('now') - julianday(b.due_date) AS INTEGER) as days_overdue
        FROM borrowings b
        JOIN users u ON b.user_id = u.id
        JOIN books bk ON b.book_id = bk.id
        JOIN book_copies bc ON b.copy_id = bc.id
        WHERE b.status = 'return_pending'
        ORDER BY b.return_request_date ASC
    """)
    return render_template('librarian/returns.html', pending_returns=pending)

@app.route('/librarian/return/<int:borrowing_id>/confirm', methods=['POST'])
@login_required
@role_required('librarian')
def librarian_confirm_return(borrowing_id):
    condition = request.form.get('condition', 'Good')
    success, msg = models.confirm_physical_return(borrowing_id, session['user_id'], condition=condition)
    flash(msg, 'success' if success else 'danger')
    return redirect(request.referrer or url_for('librarian_returns'))

@app.route('/librarian/circulation')
@login_required
@role_required('librarian')
def librarian_circulation():
    f_type = request.args.get('filter', 'all')
    q_search = request.args.get('q', '').strip()

    where_clauses = ["1=1"]
    params = []

    if f_type == 'active':
        where_clauses.append("b.status IN ('borrowed', 'return_pending', 'overdue')")
    elif f_type == 'overdue':
        where_clauses.append("(b.status = 'overdue' OR (b.status = 'borrowed' AND b.due_date < DATE('now')))")
    elif f_type == 'return_pending':
        where_clauses.append("b.status = 'return_pending'")
    elif f_type == 'returned':
        where_clauses.append("b.status = 'returned'")

    if q_search:
        where_clauses.append("(u.name LIKE ? OR u.university_id LIKE ? OR bk.title LIKE ? OR bc.copy_code LIKE ?)")
        s_term = f"%{q_search}%"
        params.extend([s_term, s_term, s_term, s_term])

    where_sql = " AND ".join(where_clauses)
    borrowings = query_db(f"""
        SELECT b.*, u.name as user_name, u.university_id, u.role as user_role,
               bk.title as book_title, bc.copy_code,
               CASE WHEN b.due_date < DATE('now') AND b.return_date IS NULL THEN 1 ELSE 0 END as is_overdue,
               CAST(julianday('now') - julianday(b.due_date) AS INTEGER) as days_overdue
        FROM borrowings b
        JOIN users u ON b.user_id = u.id
        JOIN books bk ON b.book_id = bk.id
        JOIN book_copies bc ON b.copy_id = bc.id
        WHERE {where_sql}
        ORDER BY b.id DESC
    """, params)

    return render_template('librarian/circulation.html', borrowings=borrowings, current_filter=f_type, search_query=q_search)

@app.route('/librarian/books')
@login_required
@role_required('librarian', 'admin')
def librarian_books():
    search_query = request.args.get('q', '').strip()
    books, _ = models.get_books_catalog(search_query=search_query, per_page=100)
    return render_template('librarian/books.html', books=books, search_query=search_query)

@app.route('/librarian/book/add', methods=['GET', 'POST'])
@login_required
@role_required('librarian')
def librarian_add_book():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        isbn = request.form.get('isbn', '').strip()
        author = request.form.get('author', '').strip()
        category_id = request.form.get('category_id')
        publisher = request.form.get('publisher', '').strip()
        edition = request.form.get('edition', '').strip()
        shelf_location = request.form.get('shelf_location', '').strip()
        description = request.form.get('description', '').strip()

        try:
            publication_year = int(request.form.get('publication_year', 2023))
        except (ValueError, TypeError):
            publication_year = 2023

        try:
            initial_copies = int(request.form.get('initial_copies', 2))
            if initial_copies < 1:
                initial_copies = 1
        except (ValueError, TypeError):
            initial_copies = 2

        try:
            db = get_db()
            cur = db.execute("""
                INSERT INTO books (isbn, title, author, publisher, edition, publication_year, category_id, description, shelf_location)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (isbn, title, author, publisher, edition, publication_year, category_id, description, shelf_location))
            book_id = cur.lastrowid

            # Create physical copies
            copy_base = f"LIB-CPY-{book_id * 100}"
            for c_idx in range(1, initial_copies + 1):
                code = f"{copy_base}-{c_idx}"
                db.execute("""
                    INSERT INTO book_copies (book_id, copy_code, status, condition, shelf_location)
                    VALUES (?, ?, 'available', 'New', ?)
                """, (book_id, code, shelf_location))

            db.commit()
            flash(f"Book '{title}' successfully added to catalogue with {initial_copies} physical copies.", "success")
            return redirect(url_for('librarian_books'))
        except Exception as e:
            flash(f"Error adding book: {str(e)}", "danger")

    categories = models.get_all_categories()
    return render_template('librarian/book_form.html', book=None, categories=categories)

@app.route('/librarian/book/<int:book_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('librarian')
def librarian_edit_book(book_id):
    book = models.get_book_details(book_id)
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for('librarian_books'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        isbn = request.form.get('isbn', '').strip()
        author = request.form.get('author', '').strip()
        category_id = request.form.get('category_id')
        publisher = request.form.get('publisher', '').strip()
        edition = request.form.get('edition', '').strip()
        shelf_location = request.form.get('shelf_location', '').strip()
        description = request.form.get('description', '').strip()

        try:
            publication_year = int(request.form.get('publication_year', 2023))
        except (ValueError, TypeError):
            publication_year = 2023

        try:
            execute_db("""
                UPDATE books
                SET isbn = ?, title = ?, author = ?, publisher = ?, edition = ?, 
                    publication_year = ?, category_id = ?, description = ?, shelf_location = ?
                WHERE id = ?
            """, (isbn, title, author, publisher, edition, publication_year, category_id, description, shelf_location, book_id))
            flash(f"Book details for '{title}' updated successfully.", "success")
            return redirect(url_for('librarian_books'))
        except Exception as e:
            flash(f"Error updating book: {str(e)}", "danger")

    categories = models.get_all_categories()
    return render_template('librarian/book_form.html', book=book, categories=categories)

@app.route('/librarian/book/<int:book_id>/delete', methods=['POST'])
@login_required
@role_required('librarian')
def librarian_delete_book(book_id):
    # Check if any active borrowings exist
    active_loans = query_db("""
        SELECT COUNT(*) as cnt FROM borrowings
        WHERE book_id = ? AND status IN ('borrowed', 'return_pending', 'overdue')
    """, (book_id,), one=True)

    if active_loans and active_loans['cnt'] > 0:
        flash("Cannot delete book: Copies of this title are currently issued to patrons.", "danger")
        return redirect(url_for('librarian_books'))

    execute_db("DELETE FROM books WHERE id = ?", (book_id,))
    flash("Book and associated copy records removed from the catalogue.", "success")
    return redirect(url_for('librarian_books'))

@app.route('/librarian/book/<int:book_id>/copies')
@login_required
@role_required('librarian')
def librarian_book_copies(book_id):
    book = models.get_book_details(book_id)
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for('librarian_books'))

    copies = models.get_book_copies(book_id)
    suggested_code = f"LIB-CPY-{book_id * 100}-{len(copies) + 1}"
    return render_template('librarian/book_copies.html', book=book, copies=copies, suggested_code=suggested_code)

@app.route('/librarian/book/<int:book_id>/copies/add', methods=['POST'])
@login_required
@role_required('librarian')
def librarian_add_copy(book_id):
    copy_code = request.form.get('copy_code', '').strip()
    condition = request.form.get('condition', 'Good')
    shelf_location = request.form.get('shelf_location', '').strip()

    try:
        execute_db("""
            INSERT INTO book_copies (book_id, copy_code, status, condition, shelf_location)
            VALUES (?, ?, 'available', ?, ?)
        """, (book_id, copy_code, condition, shelf_location))
        flash(f"Physical copy '{copy_code}' added to inventory.", "success")
    except Exception as e:
        flash(f"Error adding copy: {str(e)}", "danger")

    return redirect(url_for('librarian_book_copies', book_id=book_id))

@app.route('/librarian/copy/<int:copy_id>/delete', methods=['POST'])
@login_required
@role_required('librarian')
def librarian_delete_copy(copy_id):
    copy = query_db("SELECT * FROM book_copies WHERE id = ?", (copy_id,), one=True)
    if not copy:
        flash("Copy record not found.", "danger")
        return redirect(url_for('librarian_books'))

    if copy['status'] not in ('available', 'maintenance'):
        flash("Cannot delete copy: It is currently issued or held for a patron.", "danger")
        return redirect(url_for('librarian_book_copies', book_id=copy['book_id']))

    execute_db("DELETE FROM book_copies WHERE id = ?", (copy_id,))
    flash(f"Copy {copy['copy_code']} removed from inventory.", "success")
    return redirect(url_for('librarian_book_copies', book_id=copy['book_id']))

@app.route('/librarian/reservations')
@login_required
@role_required('librarian')
def librarian_reservations():
    reservations = query_db("""
        SELECT r.*, u.name as user_name, u.university_id, u.role as user_role,
               bk.title as book_title, bc.copy_code
        FROM reservations r
        JOIN users u ON r.user_id = u.id
        JOIN books bk ON r.book_id = bk.id
        LEFT JOIN book_copies bc ON r.copy_id = bc.id
        WHERE r.status IN ('pending', 'ready_for_pickup')
        ORDER BY r.book_id, r.queue_position ASC
    """)
    return render_template('librarian/reservations.html', reservations=reservations)

@app.route('/librarian/reservation/<int:res_id>/cancel', methods=['POST'])
@login_required
@role_required('librarian')
def librarian_cancel_reservation(res_id):
    success, msg = models.cancel_reservation(res_id)
    flash(msg, 'success' if success else 'danger')
    return redirect(url_for('librarian_reservations'))

@app.route('/librarian/fines')
@login_required
@role_required('librarian')
def librarian_fines():
    fines = models.get_all_fines()
    return render_template('librarian/fines.html', fines=fines)

@app.route('/librarian/payment/record', methods=['POST'])
@login_required
@role_required('librarian')
def librarian_record_payment():
    fine_id = request.form.get('fine_id')
    amount = request.form.get('amount')
    payment_method = request.form.get('payment_method')
    notes = request.form.get('notes', '')

    success, msg = models.record_manual_payment(fine_id, session['user_id'], amount, payment_method, notes)
    flash(msg, 'success' if success else 'danger')
    return redirect(url_for('librarian_fines'))

@app.route('/librarian/student-records')
@login_required
@role_required('librarian')
def librarian_student_records():
    search_query = request.args.get('q', '').strip()
    where_sql = "role IN ('student', 'faculty')"
    params = []

    if search_query:
        where_sql += " AND (name LIKE ? OR university_id LIKE ? OR email LIKE ?)"
        s = f"%{search_query}%"
        params.extend([s, s, s])

    patrons = query_db(f"""
        SELECT u.*,
            (SELECT COUNT(*) FROM borrowings WHERE user_id = u.id AND status IN ('borrowed', 'return_pending', 'overdue')) as active_loans_count,
            (SELECT COUNT(*) FROM reservations WHERE user_id = u.id AND status IN ('pending', 'ready_for_pickup')) as reservations_count,
            (SELECT COALESCE(SUM(f.amount - (SELECT COALESCE(SUM(p.amount), 0) FROM payments p WHERE p.fine_id = f.id)), 0)
             FROM fines f WHERE f.user_id = u.id AND f.status IN ('unpaid', 'partially_paid')) as unpaid_fines
        FROM users u
        WHERE {where_sql}
        ORDER BY u.name ASC
    """, params)

    return render_template('librarian/student_records.html', patrons=patrons, search_query=search_query)

# ==============================================================================
# ADMINISTRATOR ACCOUNT & ROLE MANAGEMENT
# ==============================================================================

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    search_query = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '')

    where_clauses = ["1=1"]
    params = []

    if search_query:
        where_clauses.append("(name LIKE ? OR university_id LIKE ? OR email LIKE ?)")
        s = f"%{search_query}%"
        params.extend([s, s, s])

    if role_filter:
        where_clauses.append("role = ?")
        params.append(role_filter)

    where_sql = " AND ".join(where_clauses)
    users = query_db(f"SELECT * FROM users WHERE {where_sql} ORDER BY id DESC", params)

    return render_template('admin/users.html', users=users, search_query=search_query, selected_role=role_filter)

@app.route('/admin/user/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_create_user():
    if request.method == 'POST':
        uid = request.form.get('university_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        pwd = request.form.get('password', '')
        role = request.form.get('role', 'student')
        is_active = 1 if request.form.get('is_active') else 0

        try:
            limit = int(request.form.get('max_borrow_limit', 3))
            if limit < 1:
                limit = 3
        except (ValueError, TypeError):
            limit = 3

        pwd_hash = generate_password_hash(pwd)

        try:
            execute_db("""
                INSERT INTO users (university_id, name, email, password_hash, role, max_borrow_limit, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (uid, name, email, pwd_hash, role, limit, is_active))
            flash(f"User '{name}' ({uid}) successfully registered.", "success")
            return redirect(url_for('admin_users'))
        except Exception as e:
            flash(f"Error creating user: {str(e)}", "danger")

    return render_template('admin/user_form.html', edit_user=None)

@app.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_user(user_id):
    user = models.get_user_by_id(user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('admin_users'))

    if request.method == 'POST':
        uid = request.form.get('university_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        pwd = request.form.get('password', '')
        role = request.form.get('role', 'student')
        is_active = 1 if request.form.get('is_active') else 0

        try:
            limit = int(request.form.get('max_borrow_limit', 3))
            if limit < 1:
                limit = 3
        except (ValueError, TypeError):
            limit = 3

        try:
            if pwd:
                pwd_hash = generate_password_hash(pwd)
                execute_db("""
                    UPDATE users
                    SET university_id = ?, name = ?, email = ?, password_hash = ?, 
                        role = ?, max_borrow_limit = ?, is_active = ?
                    WHERE id = ?
                """, (uid, name, email, pwd_hash, role, limit, is_active, user_id))
            else:
                execute_db("""
                    UPDATE users
                    SET university_id = ?, name = ?, email = ?, role = ?, 
                        max_borrow_limit = ?, is_active = ?
                    WHERE id = ?
                """, (uid, name, email, role, limit, is_active, user_id))

            flash(f"Account for '{name}' updated successfully.", "success")
            return redirect(url_for('admin_users'))
        except Exception as e:
            flash(f"Error updating user: {str(e)}", "danger")

    return render_template('admin/user_form.html', edit_user=user)

@app.route('/admin/user/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@role_required('admin')
def admin_toggle_user_status(user_id):
    user = models.get_user_by_id(user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('admin_users'))

    new_status = 0 if user['is_active'] else 1
    execute_db("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    action_str = "activated" if new_status else "deactivated"
    flash(f"User account for '{user['name']}' has been {action_str}.", "info")
    return redirect(url_for('admin_users'))

# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
