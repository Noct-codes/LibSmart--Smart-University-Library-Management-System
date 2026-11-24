import unittest
import os
import sqlite3
from datetime import date, timedelta
from werkzeug.security import generate_password_hash
from app import app
from config import Config
import models

class LibSmartSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

    def setUp(self):
        # We test against the seeded database
        pass

    # 1. Login and Logout
    def test_01_login_logout(self):
        # Successful student login
        resp = self.client.post('/login', data={'university_id': 'STU001', 'password': 'password123'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Welcome back, Aarav Sharma', resp.data)

        # Logout
        resp_logout = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(resp_logout.status_code, 200)
        self.assertIn(b'signed out', resp_logout.data)

        # Invalid credentials test
        resp_bad = self.client.post('/login', data={'university_id': 'STU001', 'password': 'wrongpassword'}, follow_redirects=True)
        self.assertIn(b'Invalid password', resp_bad.data)

    # 2. Role-Based Access Control
    def test_02_role_based_access(self):
        # Student attempting to access librarian returns desk
        self.client.post('/login', data={'university_id': 'STU001', 'password': 'password123'}, follow_redirects=True)
        resp = self.client.get('/librarian/returns', follow_redirects=True)
        self.assertIn(b'Access denied', resp.data)
        self.client.get('/logout')

        # Librarian can access
        self.client.post('/login', data={'university_id': 'LIB001', 'password': 'password123'}, follow_redirects=True)
        resp_lib = self.client.get('/librarian/returns', follow_redirects=True)
        self.assertEqual(resp_lib.status_code, 200)
        self.assertIn(b'Physical Returns Verification', resp_lib.data)
        self.client.get('/logout')

    # 3. Book Search and Filter
    def test_03_book_search_and_filter(self):
        # Search by Title
        resp = self.client.get('/catalogue?q=Algorithms')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Introduction to Algorithms', resp.data)

        # Search by ISBN
        resp_isbn = self.client.get('/catalogue?q=978-0132350884')
        self.assertIn(b'Clean Code', resp_isbn.data)

        # Availability filter
        resp_avail = self.client.get('/catalogue?availability=available')
        self.assertEqual(resp_avail.status_code, 200)

    # 4. Book Borrowing
    def test_04_self_service_borrowing(self):
        # Login as student STU004 (has 0 active borrowings initially)
        self.client.post('/login', data={'university_id': 'STU004', 'password': 'password123'}, follow_redirects=True)

        # Borrow book id 3 (Design Patterns)
        resp = self.client.post('/borrow/3', follow_redirects=True)
        self.assertIn(b'Successfully borrowed', resp.data)

        # Verify borrowing recorded in db
        with app.app_context():
            user = models.get_user_by_university_id('STU004')
            loans = models.query_db("SELECT * FROM borrowings WHERE user_id = ? AND book_id = 3 AND status = 'borrowed'", (user['id'],))
            self.assertGreater(len(loans), 0)

        self.client.get('/logout')

    # 5. Borrowing Limit Validation
    def test_05_borrowing_limit_validation(self):
        # Login as STU004
        self.client.post('/login', data={'university_id': 'STU004', 'password': 'password123'}, follow_redirects=True)

        # STU004 has 1 loan now. Borrow 2 more books (books 6 and 7)
        self.client.post('/borrow/6', follow_redirects=True)
        self.client.post('/borrow/7', follow_redirects=True)

        # Now STU004 has 3 books. Attempting to borrow a 4th (book 8) should fail!
        resp_limit = self.client.post('/borrow/8', follow_redirects=True)
        self.assertIn(b'Borrowing limit reached', resp_limit.data)

        self.client.get('/logout')

    # 6. Duplicate Reservation Prevention
    def test_06_duplicate_reservation_prevention(self):
        # Login as STU003 (already reserved book 10 in seed)
        self.client.post('/login', data={'university_id': 'STU003', 'password': 'password123'}, follow_redirects=True)

        # Try reserving book 10 again
        resp = self.client.post('/reserve/10', follow_redirects=True)
        self.assertIn(b'already have an active reservation', resp.data)

        self.client.get('/logout')

    # 7. Reservation Queue Processing
    def test_07_reservation_queue_processing(self):
        # Book 10 (Deep Learning) has all copies out.
        # STU003 is at Queue position #1.
        # One copy is borrowed by STU002. Let's find STU002's borrowing for book 10.
        with app.app_context():
            user_stu2 = models.get_user_by_university_id('STU002')
            loan_dl = models.query_db("SELECT * FROM borrowings WHERE user_id = ? AND book_id = 10 AND status = 'borrowed'", (user_stu2['id'],), one=True)
            self.assertIsNotNone(loan_dl)
            loan_dl_id = loan_dl['id']

        # Librarian confirms physical return of that copy
        self.client.post('/login', data={'university_id': 'LIB001', 'password': 'password123'}, follow_redirects=True)
        resp_ret = self.client.post(f'/librarian/return/{loan_dl_id}/confirm', data={'condition': 'Good'}, follow_redirects=True)
        self.assertEqual(resp_ret.status_code, 200)

        # Check that STU003's reservation status changed to 'ready_for_pickup'!
        with app.app_context():
            user_stu3 = models.get_user_by_university_id('STU003')
            res_stu3 = models.query_db("SELECT * FROM reservations WHERE user_id = ? AND book_id = 10", (user_stu3['id'],), one=True)
            self.assertEqual(res_stu3['status'], 'ready_for_pickup')
            self.assertIsNotNone(res_stu3['pickup_deadline'])

        self.client.get('/logout')

    # 8. Book Renewal Restrictions
    def test_08_book_renewal_restrictions(self):
        with app.app_context():
            user_fac = models.get_user_by_university_id('FAC001')
            loan_fac = models.query_db("SELECT * FROM borrowings WHERE user_id = ? AND status = 'borrowed'", (user_fac['id'],), one=True)
            self.assertIsNotNone(loan_fac)
            loan_fac_id = loan_fac['id']

        # Login as FAC001
        self.client.post('/login', data={'university_id': 'FAC001', 'password': 'password123'}, follow_redirects=True)

        # 1st renewal: Should succeed
        resp_renew1 = self.client.post(f'/renew/{loan_fac_id}', follow_redirects=True)
        self.assertIn(b'Successfully renewed', resp_renew1.data)

        # 2nd renewal: Should succeed
        resp_renew2 = self.client.post(f'/renew/{loan_fac_id}', follow_redirects=True)
        self.assertIn(b'Successfully renewed', resp_renew2.data)

        # 3rd renewal: Must be blocked (max 2 renewals)
        resp_renew3 = self.client.post(f'/renew/{loan_fac_id}', follow_redirects=True)
        self.assertIn(b'Renewal limit reached', resp_renew3.data)

        self.client.get('/logout')

    # 9. Return Request and Confirmation
    def test_09_return_request_and_confirmation(self):
        # Login as student STU001
        self.client.post('/login', data={'university_id': 'STU001', 'password': 'password123'}, follow_redirects=True)

        with app.app_context():
            user = models.get_user_by_university_id('STU001')
            loan = models.query_db("SELECT * FROM borrowings WHERE user_id = ? AND status = 'borrowed'", (user['id'],), one=True)
            self.assertIsNotNone(loan)
            loan_id = loan['id']

        # Student initiates return request
        resp_req = self.client.post(f'/return/{loan_id}', follow_redirects=True)
        self.assertIn(b'Return initiated', resp_req.data)

        # Verify status became 'return_pending'
        with app.app_context():
            updated_loan = models.query_db("SELECT status FROM borrowings WHERE id = ?", (loan_id,), one=True)
            self.assertEqual(updated_loan['status'], 'return_pending')

        self.client.get('/logout')

        # Librarian confirms physical receipt
        self.client.post('/login', data={'university_id': 'LIB001', 'password': 'password123'}, follow_redirects=True)
        resp_conf = self.client.post(f'/librarian/return/{loan_id}/confirm', data={'condition': 'Good'}, follow_redirects=True)
        self.assertIn(b'Return verified', resp_conf.data)

        with app.app_context():
            final_loan = models.query_db("SELECT status FROM borrowings WHERE id = ?", (loan_id,), one=True)
            self.assertEqual(final_loan['status'], 'returned')

        self.client.get('/logout')

    # 10. Fine Calculation (₹5/day)
    def test_10_fine_calculation(self):
        # STU001 has overdue loan for Book 2 (Clean Code) seeded 5 days overdue -> Fine ₹25
        with app.app_context():
            user = models.get_user_by_university_id('STU001')
            fine = models.query_db("SELECT * FROM fines WHERE user_id = ? AND status = 'unpaid'", (user['id'],), one=True)
            self.assertIsNotNone(fine)
            self.assertEqual(fine['overdue_days'], 5)
            self.assertEqual(fine['amount'], 25.0)

    # 11. Partial and Full Fine Payments
    def test_11_fine_payments(self):
        with app.app_context():
            user = models.get_user_by_university_id('STU001')
            fine = models.query_db("SELECT * FROM fines WHERE user_id = ? AND status = 'unpaid'", (user['id'],), one=True)
            fine_id = fine['id']
            lib = models.get_user_by_university_id('LIB001')

        # Login as Librarian
        self.client.post('/login', data={'university_id': 'LIB001', 'password': 'password123'}, follow_redirects=True)

        # 1. Partial payment of ₹10 (out of ₹25)
        resp_part = self.client.post('/librarian/payment/record', data={
            'fine_id': fine_id,
            'amount': '10.0',
            'payment_method': 'Cash',
            'notes': 'Partial cash payment at desk'
        }, follow_redirects=True)
        self.assertIn(b'Partially Paid', resp_part.data)

        # 2. Exceeding payment validation (remaining is ₹15, try paying ₹20)
        resp_over = self.client.post('/librarian/payment/record', data={
            'fine_id': fine_id,
            'amount': '20.0',
            'payment_method': 'Cash',
            'notes': 'Overpayment attempt'
        }, follow_redirects=True)
        self.assertIn(b'cannot exceed the remaining balance', resp_over.data)

        # 3. Pay remaining balance of ₹15 -> Status becomes 'Paid'
        resp_full = self.client.post('/librarian/payment/record', data={
            'fine_id': fine_id,
            'amount': '15.0',
            'payment_method': 'UPI (Manual Entry)',
            'notes': 'Full settlement'
        }, follow_redirects=True)
        self.assertIn(b'Paid', resp_full.data)

        self.client.get('/logout')

    # 12. Wishlist Management
    def test_12_wishlist(self):
        self.client.post('/login', data={'university_id': 'STU005', 'password': 'password123'}, follow_redirects=True)

        # Add book 1 to wishlist
        resp_add = self.client.post('/wishlist/toggle/1', follow_redirects=True)
        self.assertIn(b'added to your wishlist', resp_add.data)

        # Toggle again removes it
        resp_rem = self.client.post('/wishlist/toggle/1', follow_redirects=True)
        self.assertIn(b'removed from your wishlist', resp_rem.data)

        self.client.get('/logout')

    # 13. Due-Date Notifications
    def test_13_due_date_notifications(self):
        # Accessing as STU001 triggers automatic due reminder evaluation
        self.client.post('/login', data={'university_id': 'STU001', 'password': 'password123'}, follow_redirects=True)
        resp_notif = self.client.get('/notifications')
        self.assertEqual(resp_notif.status_code, 200)
        self.assertIn(b'Overdue Alert', resp_notif.data)
        self.client.get('/logout')

    # 14. Book Availability Notifications
    def test_14_availability_notification(self):
        with app.app_context():
            user_stu3 = models.get_user_by_university_id('STU003')
            notifs = models.query_db("SELECT * FROM notifications WHERE user_id = ? AND type = 'available'", (user_stu3['id'],))
            self.assertGreater(len(notifs), 0)

    # 15. Dashboard Statistics
    def test_15_dashboard_statistics(self):
        with app.app_context():
            lib_data = models.get_librarian_dashboard_data()
            self.assertGreater(lib_data['titles_cnt'], 30)
            self.assertGreater(lib_data['copies_cnt'], 60)
            self.assertGreaterEqual(lib_data['avail_cnt'], 0)

            admin_data = models.get_admin_dashboard_data()
            self.assertGreaterEqual(admin_data['total_users'], 10)
            self.assertGreaterEqual(admin_data['students_cnt'], 5)

if __name__ == '__main__':
    unittest.main()
