// Clean Modal System - No Bootstrap Required
class ModalManager {
    constructor() {
        this.activeModals = [];
        this.init();
    }

    init() {
        // Handle escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModals.length > 0) {
                const topModal = this.activeModals[this.activeModals.length - 1];
                this.close(topModal);
            }
        });
    }

    open(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error(`Modal ${modalId} not found`);
            return;
        }

        // Prevent duplicate opens
        if (this.activeModals.includes(modalId)) {
            return;
        }

        // Create backdrop if it doesn't exist
        let backdrop = document.getElementById(`${modalId}-backdrop`);
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.id = `${modalId}-backdrop`;
            backdrop.className = 'modal-backdrop';
            backdrop.onclick = () => this.close(modalId);
            document.body.appendChild(backdrop);
        }

        // Show modal and backdrop
        requestAnimationFrame(() => {
            modal.style.display = 'block';
            backdrop.style.display = 'block';
            
            requestAnimationFrame(() => {
                modal.classList.add('show');
                backdrop.classList.add('show');
                document.body.classList.add('modal-open');
            });
        });

        // Track active modal
        this.activeModals.push(modalId);

        // Focus first input or button
        setTimeout(() => {
            const focusable = modal.querySelector('input, button, select, textarea');
            if (focusable) focusable.focus();
        }, 100);

        // Setup focus trap
        this.trapFocus(modal);
    }

    close(modalId) {
        const modal = document.getElementById(modalId);
        const backdrop = document.getElementById(`${modalId}-backdrop`);
        
        if (!modal) return;

        // Remove show classes
        modal.classList.remove('show');
        if (backdrop) backdrop.classList.remove('show');

        // Hide after transition
        setTimeout(() => {
            modal.style.display = 'none';
            if (backdrop) {
                backdrop.style.display = 'none';
            }

            // Remove from active modals
            this.activeModals = this.activeModals.filter(id => id !== modalId);

            // Remove body class if no active modals
            if (this.activeModals.length === 0) {
                document.body.classList.remove('modal-open');
            }

            // Clear any form data
            const forms = modal.querySelectorAll('form');
            forms.forEach(form => form.reset());
        }, 300);
    }

    trapFocus(modal) {
        const focusableElements = modal.querySelectorAll(
            'a[href], button, textarea, input, select, [tabindex]:not([tabindex="-1"])'
        );
        
        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        modal.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;

            if (e.shiftKey) {
                if (document.activeElement === firstElement) {
                    e.preventDefault();
                    lastElement.focus();
                }
            } else {
                if (document.activeElement === lastElement) {
                    e.preventDefault();
                    firstElement.focus();
                }
            }
        });
    }
}

// Initialize modal manager
const modalManager = new ModalManager();

// Global functions for compatibility
window.openCredentialsModal = function() {
    // Check 2FA status first
    fetch('/api/auth/2fa/status', {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`
        }
    })
    .then(response => response.json())
    .then(data => {
        if (!data.enabled) {
            // Show 2FA required modal instead
            modalManager.open('twoFARequiredModal');
        } else {
            // Show OTP verification first
            modalManager.open('otpVerificationModal');
        }
    })
    .catch(error => {
        console.error('Error checking 2FA status:', error);
        // Show credentials modal anyway if API fails
        modalManager.open('credentialsModal');
    });
};

window.closeCredentialsModal = function() {
    modalManager.close('credentialsModal');
};

window.closeTwoFAModal = function() {
    modalManager.close('twofaModal');
};

window.openOTPModal = function(callback) {
    window.otpCallback = callback;
    modalManager.open('otpVerificationModal');
};

window.verifyOTP = function() {
    const otpInput = document.getElementById('otpCode');
    const otp = otpInput.value;
    
    if (!otp || otp.length !== 6) {
        showNotification('Please enter a valid 6-digit code', 'warning');
        return;
    }
    
    fetch('/api/auth/2fa/verify', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`
        },
        body: JSON.stringify({ otp: otp })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            modalManager.close('otpVerificationModal');
            otpInput.value = '';
            
            // Open credentials modal after successful OTP
            modalManager.open('credentialsModal');
            
            // Call callback if exists
            if (window.otpCallback) {
                window.otpCallback();
                window.otpCallback = null;
            }
        } else {
            showNotification('Invalid OTP code', 'error');
        }
    })
    .catch(error => {
        console.error('Error verifying OTP:', error);
        showNotification('Error verifying OTP', 'error');
    });
};

window.setupTwoFA = function() {
    modalManager.close('twoFARequiredModal');
    window.location.href = '/setup-2fa';
};

// Helper function for notifications
window.showNotification = function(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.notification-toast');
    existingNotifications.forEach(n => n.remove());
    
    const notification = document.createElement('div');
    notification.className = `notification-toast notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="notification-close">&times;</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
};