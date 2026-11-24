/**
 * LibSmart - Smart University Library Management System
 * Frontend Interactions & Browser Notifications
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Initialize Bootstrap Tooltips & Toasts
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    var toastElList = [].slice.call(document.querySelectorAll('.toast'));
    var toastList = toastElList.map(function (toastEl) {
        var toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 5000 });
        toast.show();
        return toast;
    });

    // 2. Sidebar Mobile Toggle
    var sidebarToggle = document.getElementById('sidebarToggle');
    var sidebar = document.querySelector('.sidebar');
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('d-none');
        });
    }

    // 3. Browser Notification API (Section 9 Requirement)
    initBrowserNotifications();

    // 4. Fine Payment Modal Calculator Helper
    setupPaymentModal();
});

/**
 * Browser Notification API implementation
 * Requests permission when user clicks enable or visits notifications,
 * and triggers desktop notifications for high-priority alerts while app is open.
 */
function initBrowserNotifications() {
    var notifBtn = document.getElementById('enableBrowserNotifBtn');
    if (notifBtn) {
        if (!("Notification" in window)) {
            notifBtn.style.display = 'none';
            return;
        }

        if (Notification.permission === "granted") {
            notifBtn.innerHTML = '<i class="bi bi-bell-fill text-success me-1"></i> Browser Alerts Enabled';
            notifBtn.classList.remove('btn-outline-secondary');
            notifBtn.classList.add('btn-light', 'text-success');
            notifBtn.disabled = true;
        } else if (Notification.permission === "denied") {
            notifBtn.innerHTML = '<i class="bi bi-bell-slash text-danger me-1"></i> Alerts Blocked in Browser';
            notifBtn.disabled = true;
        } else {
            notifBtn.addEventListener('click', function () {
                Notification.requestPermission().then(function (permission) {
                    if (permission === "granted") {
                        showBrowserNotification("LibSmart Alerts Activated", "You will receive real-time notifications for upcoming book due dates and pickup alerts.");
                        location.reload();
                    }
                });
            });
        }
    }

    // Check for urgent unread notifications and notify user if permission is granted
    var urgentAlertEl = document.getElementById('urgentNotificationPayload');
    if (urgentAlertEl && Notification.permission === "granted") {
        try {
            var data = JSON.parse(urgentAlertEl.textContent);
            if (data && data.length > 0) {
                data.forEach(function (item) {
                    showBrowserNotification(item.title, item.message);
                });
            }
        } catch (e) {
            console.error("Error parsing urgent notifications:", e);
        }
    }
}

function showBrowserNotification(title, message) {
    if ("Notification" in window && Notification.permission === "granted") {
        var options = {
            body: message,
            icon: '/static/img/libsmart-icon.png' // fallback icon
        };
        try {
            new Notification(title, options);
        } catch (e) {
            console.warn("Could not fire desktop notification: ", e);
        }
    }
}

/**
 * Fine Payment helper: Autofills remaining balance into amount input
 */
function setupPaymentModal() {
    var paymentModal = document.getElementById('recordPaymentModal');
    if (paymentModal) {
        paymentModal.addEventListener('show.bs.modal', function (event) {
            var button = event.relatedTarget;
            if (!button) return;
            var fineId = button.getAttribute('data-fine-id');
            var remaining = button.getAttribute('data-remaining');
            var bookTitle = button.getAttribute('data-book');
            var studentName = button.getAttribute('data-student');

            var inputFineId = paymentModal.querySelector('#modalFineId');
            var inputAmount = paymentModal.querySelector('#modalAmount');
            var labelRemaining = paymentModal.querySelector('#modalRemainingText');
            var labelDetails = paymentModal.querySelector('#modalDetailsText');

            if (inputFineId) inputFineId.value = fineId;
            if (inputAmount) {
                inputAmount.value = parseFloat(remaining).toFixed(2);
                inputAmount.setAttribute('max', remaining);
            }
            if (labelRemaining) labelRemaining.textContent = '₹' + parseFloat(remaining).toFixed(2);
            if (labelDetails) labelDetails.textContent = studentName + ' — ' + bookTitle;
        });
    }
}

/**
 * Quick confirmation helper for return/renew actions
 */
function confirmAction(actionName, itemName) {
    return confirm("Are you sure you want to " + actionName + " for '" + itemName + "'?");
}
