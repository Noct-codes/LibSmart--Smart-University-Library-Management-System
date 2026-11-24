import os
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from config import Config

def init_and_seed_db():
    print(f"Initializing database at: {Config.DATABASE}")
    
    # Remove existing db file if any to start fresh
    if os.path.exists(Config.DATABASE):
        try:
            os.remove(Config.DATABASE)
            print("Existing database removed.")
        except Exception as e:
            print(f"Note: Could not remove existing db ({e}), overwriting tables.")

    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    
    print("Schema initialized. Seeding sample data...")
    cur = conn.cursor()

    # 1. Seed Users
    # Hashed passwords
    pwd_user = generate_password_hash("password123")
    pwd_admin = generate_password_hash("admin123")
    
    users = [
        # Students
        ('STU001', 'Aarav Sharma', 'aarav.sharma@univ.edu', pwd_user, 'student', 3, 1),
        ('STU002', 'Priya Patel', 'priya.patel@univ.edu', pwd_user, 'student', 3, 1),
        ('STU003', 'Rohan Verma', 'rohan.verma@univ.edu', pwd_user, 'student', 3, 1),
        ('STU004', 'Ananya Iyer', 'ananya.iyer@univ.edu', pwd_user, 'student', 3, 1),
        ('STU005', 'Vikram Singh', 'vikram.singh@univ.edu', pwd_user, 'student', 3, 1),
        # Faculty
        ('FAC001', 'Dr. Rajesh Kumar', 'rajesh.kumar@univ.edu', pwd_user, 'faculty', 6, 1),
        ('FAC002', 'Prof. Meera Nair', 'meera.nair@univ.edu', pwd_user, 'faculty', 6, 1),
        # Librarians
        ('LIB001', 'Sunita Deshmukh', 'sunita.deshmukh@univ.edu', pwd_user, 'librarian', 10, 1),
        ('LIB002', 'Manoj Kulkarni', 'manoj.kulkarni@univ.edu', pwd_user, 'librarian', 10, 1),
        # Administrator
        ('ADM001', 'System Administrator', 'admin@univ.edu', pwd_admin, 'admin', 10, 1),
    ]
    cur.executemany("""
        INSERT INTO users (university_id, name, email, password_hash, role, max_borrow_limit, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, users)
    conn.commit()
    print(f"Seeded {len(users)} users.")

    # 2. Seed Categories
    categories = [
        ('Computer Science & Engineering', 'Software engineering, algorithms, operating systems, networking and programming languages.'),
        ('Artificial Intelligence & Data', 'Machine learning, neural networks, computer vision, NLP, and big data architecture.'),
        ('Mathematics & Statistics', 'Linear algebra, calculus, discrete mathematics, and applied probability.'),
        ('Physics & Applied Sciences', 'Electrodynamics, quantum mechanics, classical physics, and semiconductors.'),
        ('Business & Management', 'Corporate finance, marketing strategy, managerial economics, and entrepreneurship.'),
        ('Humanities & General Reading', 'Cognitive psychology, world history, scientific philosophy, and communication.')
    ]
    cur.executemany("INSERT INTO categories (name, description) VALUES (?, ?)", categories)
    conn.commit()
    print(f"Seeded {len(categories)} categories.")

    # 3. Seed 32 Books
    books_data = [
        # CS
        ("978-0262033848", "Introduction to Algorithms (CLRS)", "Thomas H. Cormen, Charles E. Leiserson", "MIT Press", "3rd", 2009, 1, 
         "A comprehensive textbook on modern algorithm design, analysis, dynamic programming, and graph algorithms.", "Shelf CS-101"),
        ("978-0132350884", "Clean Code: A Handbook of Agile Craftsmanship", "Robert C. Martin", "Prentice Hall", "1st", 2008, 1, 
         "Best practices for writing readable, maintainable, and robust software code with pragmatic examples.", "Shelf CS-102"),
        ("978-0201633610", "Design Patterns: Elements of Reusable Object-Oriented Software", "Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides", "Addison-Wesley", "1st", 1994, 1, 
         "The classic GoF guide to 23 foundational object-oriented design patterns.", "Shelf CS-103"),
        ("978-0131103627", "The C Programming Language", "Brian W. Kernighan, Dennis M. Ritchie", "Prentice Hall", "2nd", 1988, 1, 
         "The definitive reference guide written by the original creators of the C programming language.", "Shelf CS-104"),
        ("978-1491950357", "Designing Data-Intensive Applications", "Martin Kleppmann", "O'Reilly Media", "1st", 2017, 1, 
         "An indispensable guide to distributed databases, streaming architectures, consensus algorithms, and scalability.", "Shelf CS-105"),
        ("978-0133591620", "Operating System Concepts", "Abraham Silberschatz, Peter B. Galvin, Greg Gagne", "Wiley", "10th", 2018, 1, 
         "Comprehensive coverage of threads, concurrency, virtual memory, scheduling, and distributed file systems.", "Shelf CS-106"),
        ("978-0132126953", "Computer Networks", "Andrew S. Tanenbaum, David J. Wetherall", "Pearson", "5th", 2010, 1, 
         "The foundational guide to OSI layers, TCP/IP, wireless networking, and routing protocols.", "Shelf CS-107"),
        ("978-0078022159", "Database System Concepts", "Abraham Silberschatz, Henry F. Korth, S. Sudarshan", "McGraw-Hill", "7th", 2019, 1, 
         "Relational database design, SQL querying, transaction processing, and query optimization.", "Shelf CS-108"),

        # AI & Data
        ("978-0136042594", "Artificial Intelligence: A Modern Approach", "Stuart Russell, Peter Norvig", "Pearson", "4th", 2020, 2, 
         "The premier reference textbook for state-space search, Bayesian reasoning, deep learning, and multi-agent systems.", "Shelf AI-201"),
        ("978-0262035613", "Deep Learning", "Ian Goodfellow, Yoshua Bengio, Aaron Courville", "MIT Press", "1st", 2016, 2, 
         "The definitive theoretical and mathematical foundation of convolutional, recurrent, and generative neural networks.", "Shelf AI-202"),
        ("978-0387310732", "Pattern Recognition and Machine Learning", "Christopher M. Bishop", "Springer", "1st", 2006, 2, 
         "A rigorous probabilistic treatment of statistical machine learning, EM algorithm, and graphical models.", "Shelf AI-203"),
        ("978-1492032649", "Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow", "Aurélien Géron", "O'Reilly Media", "3rd", 2022, 2, 
         "A hands-on, practical engineering guide to training end-to-end machine learning models in Python.", "Shelf AI-204"),
        ("978-0262039291", "Reinforcement Learning: An Introduction", "Richard S. Sutton, Andrew G. Barto", "MIT Press", "2nd", 2018, 2, 
         "Fundamental foundations of MDPs, dynamic programming, temporal difference learning, and policy gradients.", "Shelf AI-205"),
        ("978-1449369415", "Python for Data Analysis", "Wes McKinney", "O'Reilly Media", "3rd", 2022, 2, 
         "Practical guide to data manipulation, exploratory analysis, pandas, NumPy, and time series in Python.", "Shelf AI-206"),

        # Math
        ("978-0980232776", "Linear Algebra and Its Applications", "Gilbert Strang", "Cengage Learning", "5th", 2016, 3, 
         "Intuitive, geometric, and computational foundations of vector spaces, eigenvalues, and SVD.", "Shelf MATH-301"),
        ("978-1285741550", "Calculus: Early Transcendentals", "James Stewart", "Cengage Learning", "8th", 2015, 3, 
         "Mastery of multivariable differentiation, vector fields, Taylor series, and integral theorems.", "Shelf MATH-302"),
        ("978-0073383095", "Discrete Mathematics and Its Applications", "Kenneth H. Rosen", "McGraw-Hill", "8th", 2018, 3, 
         "Formal logic, proof techniques, combinatorics, graph theory, and recurrence relations for computer science.", "Shelf MATH-303"),
        ("978-0134444017", "Introduction to Probability Models", "Sheldon M. Ross", "Academic Press", "12th", 2019, 3, 
         "Stochastic processes, Poisson distributions, Markov chains, and reliability models.", "Shelf MATH-304"),
        ("978-0321796974", "Advanced Engineering Mathematics", "Erwin Kreyszig", "Wiley", "10th", 2011, 3, 
         "Fourier transforms, partial differential equations, and complex analysis for engineering students.", "Shelf MATH-305"),

        # Physics
        ("978-0805387841", "Classical Mechanics", "Herbert Goldstein, Charles P. Poole, John L. Safko", "Addison-Wesley", "3rd", 2001, 4, 
         "Lagrangian dynamics, Hamiltonian formalism, central force problems, and rigid body kinematics.", "Shelf PHYS-401"),
        ("978-0470026786", "Quantum Mechanics: Concepts and Applications", "Nouredine Zettili", "Wiley", "2nd", 2009, 4, 
         "Wave-particle duality, Dirac bra-ket notation, angular momentum algebra, and perturbation theory.", "Shelf PHYS-402"),
        ("978-1108420419", "Introduction to Electrodynamics", "David J. Griffiths", "Cambridge University Press", "4th", 2017, 4, 
         "Electrostatics, magnetostatics, Maxwell's equations, and electromagnetic radiation.", "Shelf PHYS-403"),
        ("978-0073529585", "Semiconductor Physics and Devices", "Donald A. Neamen", "McGraw-Hill", "4th", 2011, 4, 
         "Quantum theory of solids, PN junctions, MOSFETs, and bipolar junction transistors.", "Shelf PHYS-404"),
        ("978-0131495081", "Fundamentals of Thermodynamics", "Claus Borgnakke, Richard E. Sonntag", "Wiley", "8th", 2013, 4, 
         "First and second laws of thermodynamics, entropy generation, heat engines, and cycle efficiency.", "Shelf PHYS-405"),

        # Business
        ("978-1260013900", "Principles of Corporate Finance", "Richard A. Brealey, Stewart C. Myers, Franklin Allen", "McGraw-Hill", "13th", 2019, 5, 
         "Capital budgeting, DCF valuation, cost of capital, dividend policy, and corporate risk management.", "Shelf BUS-501"),
        ("978-0133856460", "Marketing Management", "Philip Kotler, Kevin Lane Keller", "Pearson", "15th", 2015, 5, 
         "Consumer psychology, brand positioning, pricing strategies, and global omnichannel distribution.", "Shelf BUS-502"),
        ("978-0670921607", "The Lean Startup", "Eric Ries", "Crown Business", "1st", 2011, 5, 
         "Continuous innovation, validated learning, MVP iteration cycles, and build-measure-learn feedback loops.", "Shelf BUS-503"),
        ("978-1118128145", "Financial Accounting: An Introduction", "Paul D. Kimmel, Jerry J. Weygandt", "Wiley", "8th", 2016, 5, 
         "Balance sheet analysis, cash flow statements, auditing principles, and managerial reporting.", "Shelf BUS-504"),

        # Humanities
        ("978-0062316097", "Sapiens: A Brief History of Humankind", "Yuval Noah Harari", "Harper", "1st", 2015, 6, 
         "From cognitive revolution to biotechnology, exploring how biology and history define us.", "Shelf HUM-601"),
        ("978-0374533557", "Thinking, Fast and Slow", "Daniel Kahneman", "Farrar, Straus and Giroux", "1st", 2011, 6, 
         "System 1 intuitive thinking versus System 2 deliberate calculation and cognitive biases in decision making.", "Shelf HUM-602"),
        ("978-0199291151", "Academic Writing: A Handbook for International Students", "Stephen Bailey", "Routledge", "5th", 2017, 6, 
         "Guidance on thesis composition, academic references, critical arguments, and literature synthesis.", "Shelf HUM-603"),
        ("978-0143127741", "Grit: The Power of Passion and Perseverance", "Angela Duckworth", "Scribner", "1st", 2016, 6, 
         "Pioneering psychological research showing that sustained effort and passion outperform innate talent.", "Shelf HUM-604")
    ]

    for b in books_data:
        cur.execute("""
            INSERT INTO books (isbn, title, author, publisher, edition, publication_year, category_id, description, shelf_location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, b)
    conn.commit()
    print(f"Seeded {len(books_data)} books.")

    # 4. Seed Physical Copies for all Books
    # Total books = 32. We'll give 2 to 4 copies for popular books, 1 or 2 for others.
    # We will specifically make book_id 10 (Deep Learning) have ALL copies borrowed so STU003 and STU004 can demonstrate the reservation queue!
    cur.execute("SELECT id, title FROM books ORDER BY id")
    all_books = cur.fetchall()
    
    copy_counter = 1000
    copies_to_insert = []
    
    for book in all_books:
        b_id = book['id']
        # Assign number of copies
        if b_id in [1, 2, 9, 10, 15, 25]:  # CLRS, Clean Code, AI Modern Approach, Deep Learning, Linear Algebra
            num_copies = 3
        elif b_id in [3, 5, 8, 12, 29]:
            num_copies = 2
        else:
            num_copies = 2
            
        for c_idx in range(1, num_copies + 1):
            copy_counter += 1
            code = f"LIB-CPY-{copy_counter}"
            status = 'available'
            condition = 'New' if c_idx == 1 else 'Good'
            copies_to_insert.append((b_id, code, status, condition, f"Sec-{b_id}-Tier-{c_idx}"))
    
    cur.executemany("""
        INSERT INTO book_copies (book_id, copy_code, status, condition, shelf_location)
        VALUES (?, ?, ?, ?, ?)
    """, copies_to_insert)
    conn.commit()
    print(f"Seeded {len(copies_to_insert)} physical copies across all 32 titles.")

    # 5. Set Up Specific Real-World Scenarios
    today = datetime.now().date()
    
    # User IDs
    cur.execute("SELECT id, university_id FROM users")
    user_map = {row['university_id']: row['id'] for row in cur.fetchall()}
    
    # Scenario A: STU001 (Aarav Sharma)
    # Copy 1 of Book 1 (CLRS): Active loan, issued 6 days ago, due in 8 days
    cur.execute("SELECT id, book_id FROM book_copies WHERE book_id = 1 LIMIT 1")
    cpy_clrs = cur.fetchone()
    issue_a = today - timedelta(days=6)
    due_a = issue_a + timedelta(days=14)
    cur.execute("""
        INSERT INTO borrowings (user_id, copy_id, book_id, issue_date, due_date, status, renewal_count)
        VALUES (?, ?, ?, ?, ?, 'borrowed', 0)
    """, (user_map['STU001'], cpy_clrs['id'], cpy_clrs['book_id'], issue_a, due_a))
    cur.execute("UPDATE book_copies SET status = 'borrowed' WHERE id = ?", (cpy_clrs['id'],))

    # Copy 1 of Book 2 (Clean Code): Overdue loan! Issued 19 days ago, due 5 days ago (fine: 5 days * 5 = ₹25)
    cur.execute("SELECT id, book_id FROM book_copies WHERE book_id = 2 LIMIT 1")
    cpy_clean = cur.fetchone()
    issue_b = today - timedelta(days=19)
    due_b = issue_b + timedelta(days=14) # 5 days overdue
    cur.execute("""
        INSERT INTO borrowings (user_id, copy_id, book_id, issue_date, due_date, status, renewal_count)
        VALUES (?, ?, ?, ?, ?, 'overdue', 0)
    """, (user_map['STU001'], cpy_clean['id'], cpy_clean['book_id'], issue_b, due_b))
    borrowing_clean_id = cur.lastrowid
    cur.execute("UPDATE book_copies SET status = 'borrowed' WHERE id = ?", (cpy_clean['id'],))
    
    # Overdue fine for STU001: 5 days * 5 = ₹25.0 (Unpaid)
    cur.execute("""
        INSERT INTO fines (borrowing_id, user_id, overdue_days, amount, status)
        VALUES (?, ?, ?, ?, 'unpaid')
    """, (borrowing_clean_id, user_map['STU001'], 5, 25.0))

    # Scenario B: STU002 (Priya Patel)
    # Copy 1 of Book 5 (Designing Data-Intensive Apps): User initiated return request! Status = 'return_pending'
    cur.execute("SELECT id, book_id FROM book_copies WHERE book_id = 5 LIMIT 1")
    cpy_ddia = cur.fetchone()
    issue_c = today - timedelta(days=10)
    due_c = issue_c + timedelta(days=14)
    ret_req_c = today - timedelta(days=1)
    cur.execute("""
        INSERT INTO borrowings (user_id, copy_id, book_id, issue_date, due_date, return_request_date, status, renewal_count)
        VALUES (?, ?, ?, ?, ?, ?, 'return_pending', 0)
    """, (user_map['STU002'], cpy_ddia['id'], cpy_ddia['book_id'], issue_c, due_c, ret_req_c))
    cur.execute("UPDATE book_copies SET status = 'return_pending' WHERE id = ?", (cpy_ddia['id'],))

    # Scenario C: FAC001 (Dr. Rajesh Kumar)
    # Faculty loan: Copy 1 of Book 9 (AI Modern Approach), issued 5 days ago, due in 25 days (30 days limit)
    cur.execute("SELECT id, book_id FROM book_copies WHERE book_id = 9 LIMIT 1")
    cpy_aima = cur.fetchone()
    issue_d = today - timedelta(days=5)
    due_d = issue_d + timedelta(days=30)
    cur.execute("""
        INSERT INTO borrowings (user_id, copy_id, book_id, issue_date, due_date, status, renewal_count)
        VALUES (?, ?, ?, ?, ?, 'borrowed', 0)
    """, (user_map['FAC001'], cpy_aima['id'], cpy_aima['book_id'], issue_d, due_d))
    cur.execute("UPDATE book_copies SET status = 'borrowed' WHERE id = ?", (cpy_aima['id'],))

    # Scenario D: Deep Learning (Book 10) - All 3 copies are currently borrowed!
    # Copy 1: Borrowed by STU002
    # Copy 2: Borrowed by STU005
    # Copy 3: Borrowed by FAC002
    cur.execute("SELECT id FROM book_copies WHERE book_id = 10")
    dl_copies = cur.fetchall()
    
    cur.execute("""
        INSERT INTO borrowings (user_id, copy_id, book_id, issue_date, due_date, status)
        VALUES (?, ?, 10, ?, ?, 'borrowed')
    """, (user_map['STU002'], dl_copies[0]['id'], today - timedelta(days=4), today + timedelta(days=10)))
    cur.execute("UPDATE book_copies SET status = 'borrowed' WHERE id = ?", (dl_copies[0]['id'],))

    cur.execute("""
        INSERT INTO borrowings (user_id, copy_id, book_id, issue_date, due_date, status)
        VALUES (?, ?, 10, ?, ?, 'borrowed')
    """, (user_map['STU005'], dl_copies[1]['id'], today - timedelta(days=8), today + timedelta(days=6)))
    cur.execute("UPDATE book_copies SET status = 'borrowed' WHERE id = ?", (dl_copies[1]['id'],))

    cur.execute("""
        INSERT INTO borrowings (user_id, copy_id, book_id, issue_date, due_date, status)
        VALUES (?, ?, 10, ?, ?, 'borrowed')
    """, (user_map['FAC002'], dl_copies[2]['id'], today - timedelta(days=12), today + timedelta(days=18)))
    cur.execute("UPDATE book_copies SET status = 'borrowed' WHERE id = ?", (dl_copies[2]['id'],))

    # Now Book 10 has 0 available copies!
    # STU003 reserved it (Queue position 1)
    cur.execute("""
        INSERT INTO reservations (user_id, book_id, status, queue_position)
        VALUES (?, 10, 'pending', 1)
    """, (user_map['STU003'],))
    
    # STU004 reserved it (Queue position 2)
    cur.execute("""
        INSERT INTO reservations (user_id, book_id, status, queue_position)
        VALUES (?, 10, 'pending', 2)
    """, (user_map['STU004'],))

    # Scenario E: Returned book with Partial Payment for STU003
    # Borrowed in the past, returned 6 days overdue -> Fine ₹30. User made ₹15 payment. Status: 'partially_paid'
    cur.execute("SELECT id FROM book_copies WHERE book_id = 15 LIMIT 1")
    cpy_la = cur.fetchone()
    old_issue = today - timedelta(days=30)
    old_due = old_issue + timedelta(days=14)
    old_return = old_due + timedelta(days=6) # 6 days overdue
    cur.execute("""
        INSERT INTO borrowings (user_id, copy_id, book_id, issue_date, due_date, return_date, status, renewal_count)
        VALUES (?, ?, 15, ?, ?, ?, 'returned', 1)
    """, (user_map['STU003'], cpy_la['id'], old_issue, old_due, old_return))
    old_borrowing_id = cur.lastrowid
    
    cur.execute("""
        INSERT INTO fines (borrowing_id, user_id, overdue_days, amount, status)
        VALUES (?, ?, 6, 30.0, 'partially_paid')
    """, (old_borrowing_id, user_map['STU003']))
    partial_fine_id = cur.lastrowid

    # Record partial manual payment of ₹15 by Chief Librarian LIB001
    cur.execute("""
        INSERT INTO payments (fine_id, user_id, librarian_id, amount, payment_method, notes)
        VALUES (?, ?, ?, 15.0, 'Cash', 'Student paid ₹15 in cash at main circulation desk. ₹15 remaining.')
    """, (partial_fine_id, user_map['STU003'], user_map['LIB001']))

    # 6. Seed Wishlists
    cur.execute("INSERT INTO wishlists (user_id, book_id) VALUES (?, ?)", (user_map['STU001'], 3))
    cur.execute("INSERT INTO wishlists (user_id, book_id) VALUES (?, ?)", (user_map['STU001'], 10))
    cur.execute("INSERT INTO wishlists (user_id, book_id) VALUES (?, ?)", (user_map['STU002'], 1))
    cur.execute("INSERT INTO wishlists (user_id, book_id) VALUES (?, ?)", (user_map['STU003'], 29))
    cur.execute("INSERT INTO wishlists (user_id, book_id) VALUES (?, ?)", (user_map['FAC001'], 4))

    # 7. Seed Sample Notifications
    notifications = [
        (user_map['STU001'], "Overdue Notice: Clean Code", "Your borrowed book 'Clean Code' was due on " + due_b.strftime('%Y-%m-%d') + ". A fine of ₹5/day is accumulating.", 'overdue', 0),
        (user_map['STU001'], "Borrow Confirmation", "You have successfully borrowed 'Introduction to Algorithms (CLRS)'. Due date: " + due_a.strftime('%Y-%m-%d') + ".", 'borrow', 1),
        (user_map['STU002'], "Return Initiated", "You have requested a return for 'Designing Data-Intensive Applications'. Please hand in the physical copy to the library desk.", 'return', 0),
        (user_map['STU003'], "Reservation Queue Confirmation", "You are at position #1 in queue for 'Deep Learning'. You will be notified as soon as a copy is returned.", 'reservation', 0),
        (user_map['STU003'], "Partial Fine Payment Recorded", "A payment of ₹15.00 was recorded for your overdue return. Remaining balance: ₹15.00.", 'fine', 1),
        (user_map['FAC001'], "Borrow Confirmation", "You have borrowed 'Artificial Intelligence: A Modern Approach'. Faculty due date: " + due_d.strftime('%Y-%m-%d') + ".", 'borrow', 0)
    ]
    cur.executemany("""
        INSERT INTO notifications (user_id, title, message, type, is_read)
        VALUES (?, ?, ?, ?, ?)
    """, notifications)

    conn.commit()
    conn.close()
    print("Database seeding successfully completed!")

if __name__ == '__main__':
    init_and_seed_db()
