/**
 * TAR Global Strategies API Client
 * Handles all API communication for the static site
 */

class TARApiClient {
    constructor(config = {}) {
        // Use environment variable for API URL, fallback to relative path
        const apiBase = window.VITE_API_URL || window.__API_URL__ || '';
        this.baseURL = config.baseURL || (apiBase ? `${apiBase}/api` : '/api');
        this.wsURL = config.wsURL || this._getWebSocketURL();
        this.token = localStorage.getItem('access_token');
        this.refreshToken = localStorage.getItem('refresh_token');
        this.ws = null;
        this.wsReconnectInterval = 5000;
        this.wsMessageHandlers = new Map();
    }

    // Utility method to get WebSocket URL
    _getWebSocketURL() {
        const apiBase = window.VITE_API_URL || window.__API_URL__ || '';
        if (apiBase) {
            const protocol = apiBase.startsWith('https:') ? 'wss:' : 'ws:';
            const host = apiBase.replace(/^https?:\/\//, '');
            return `${protocol}//${host}/ws`;
        } else {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            return `${protocol}//${window.location.host}/ws`;
        }
    }

    // Main fetch method with authentication
    async authenticatedFetch(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                ...options,
                headers
            });

            // Handle token expiration
            if (response.status === 401 && this.refreshToken) {
                const refreshed = await this.refreshAccessToken();
                if (refreshed) {
                    // Retry the request with new token
                    headers['Authorization'] = `Bearer ${this.token}`;
                    return fetch(`${this.baseURL}${endpoint}`, {
                        ...options,
                        headers
                    });
                } else {
                    // Refresh failed, redirect to login
                    this.logout();
                    return response;
                }
            }

            return response;
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    // Authentication methods
    async login(email, password, totpCode = null, privateKey = null, passphrase = null) {
        const response = await fetch(`${this.baseURL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email,
                password,
                totp_code: totpCode,
                private_key: privateKey,
                passphrase: passphrase
            })
        });

        if (response.ok) {
            const data = await response.json();
            this.token = data.access_token;
            this.refreshToken = data.refresh_token;
            localStorage.setItem('access_token', this.token);
            localStorage.setItem('refresh_token', this.refreshToken);
            return { success: true, data };
        } else {
            const error = await response.json();
            return { success: false, error };
        }
    }

    async refreshAccessToken() {
        try {
            const response = await fetch(`${this.baseURL}/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: this.refreshToken })
            });

            if (response.ok) {
                const data = await response.json();
                this.token = data.access_token;
                localStorage.setItem('access_token', this.token);
                return true;
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
        }
        return false;
    }

    logout() {
        this.token = null;
        this.refreshToken = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        if (this.ws) {
            this.ws.close();
        }
        window.location.href = '/login';
    }

    // Dashboard API
    async getDashboardStats() {
        const response = await this.authenticatedFetch('/dashboard/stats');
        return response.ok ? response.json() : null;
    }

    // Instance Management API
    async getInstances() {
        const response = await this.authenticatedFetch('/instances');
        return response.ok ? response.json() : [];
    }

    async getInstance(id) {
        const response = await this.authenticatedFetch(`/instances/${id}`);
        return response.ok ? response.json() : null;
    }

    async createInstance(data) {
        const response = await this.authenticatedFetch('/instances', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        return response.ok ? response.json() : null;
    }

    async updateInstance(id, data) {
        const response = await this.authenticatedFetch(`/instances/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
        return response.ok ? response.json() : null;
    }

    async deleteInstance(id) {
        const response = await this.authenticatedFetch(`/instances/${id}`, {
            method: 'DELETE'
        });
        return response.ok;
    }

    async toggleInstance(id) {
        const response = await this.authenticatedFetch(`/instances/${id}/toggle`, {
            method: 'POST'
        });
        return response.ok ? response.json() : null;
    }

    // API Library
    async getApiCredentials() {
        const response = await this.authenticatedFetch('/api-library/credentials');
        return response.ok ? response.json() : [];
    }

    async createApiCredential(data) {
        const response = await this.authenticatedFetch('/api-library/credentials', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        return response.ok ? response.json() : null;
    }

    async testApiCredential(id) {
        const response = await this.authenticatedFetch(`/api-library/credentials/${id}/test`, {
            method: 'POST'
        });
        return response.ok ? response.json() : null;
    }

    // DEX Arbitrage API
    async getDexInstances() {
        const response = await this.authenticatedFetch('/dex-arbitrage/instances');
        return response.ok ? response.json() : [];
    }

    async getDexOpportunities() {
        const response = await this.authenticatedFetch('/dex-arbitrage/opportunities');
        return response.ok ? response.json() : [];
    }

    // Decter Engine API
    async getDecterStatus() {
        const response = await this.authenticatedFetch('/decter/status');
        return response.ok ? response.json() : null;
    }

    async controlDecter(action) {
        const response = await this.authenticatedFetch(`/decter/${action}`, {
            method: 'POST'
        });
        return response.ok ? response.json() : null;
    }

    async getDecterConfig() {
        const response = await this.authenticatedFetch('/decter/config');
        return response.ok ? response.json() : null;
    }

    async updateDecterConfig(config) {
        const response = await this.authenticatedFetch('/decter/config', {
            method: 'POST',
            body: JSON.stringify(config)
        });
        return response.ok ? response.json() : null;
    }

    // Strategy Monitor API
    async getStrategyMonitors() {
        const response = await this.authenticatedFetch('/strategy-monitors');
        return response.ok ? response.json() : [];
    }

    async getStrategyReport(monitorId) {
        const response = await this.authenticatedFetch(`/strategy-monitors/${monitorId}/report`);
        return response.ok ? response.json() : null;
    }

    // System API
    async getSystemHealth() {
        const response = await this.authenticatedFetch('/health');
        return response.ok ? response.json() : null;
    }

    async getSystemLogs(filters = {}) {
        const params = new URLSearchParams(filters);
        const response = await this.authenticatedFetch(`/system/logs?${params}`);
        return response.ok ? response.json() : [];
    }

    // WebSocket Management
    connectWebSocket() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return; // Already connected
        }

        this.ws = new WebSocket(this.wsURL);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            // Send authentication
            if (this.token) {
                this.ws.send(JSON.stringify({
                    type: 'auth',
                    token: this.token
                }));
            }
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this._handleWebSocketMessage(data);
            } catch (error) {
                console.error('WebSocket message parse error:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            // Attempt to reconnect after interval
            setTimeout(() => this.connectWebSocket(), this.wsReconnectInterval);
        };
    }

    // WebSocket message handling
    _handleWebSocketMessage(data) {
        // Notify all registered handlers for this message type
        const handlers = this.wsMessageHandlers.get(data.type) || [];
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error('WebSocket message handler error:', error);
            }
        });
    }

    // Register WebSocket message handler
    onWebSocketMessage(type, handler) {
        if (!this.wsMessageHandlers.has(type)) {
            this.wsMessageHandlers.set(type, []);
        }
        this.wsMessageHandlers.get(type).push(handler);
    }

    // Send WebSocket message
    sendWebSocketMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not connected');
        }
    }

    // Utility methods
    async downloadFile(endpoint, filename) {
        const response = await this.authenticatedFetch(endpoint);
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }
    }

    // Upload file
    async uploadFile(endpoint, file, additionalData = {}) {
        const formData = new FormData();
        formData.append('file', file);
        
        // Add additional data to form
        Object.entries(additionalData).forEach(([key, value]) => {
            formData.append(key, value);
        });

        const response = await this.authenticatedFetch(endpoint, {
            method: 'POST',
            body: formData,
            headers: {
                // Don't set Content-Type, let browser set it with boundary
            }
        });
        
        return response.ok ? response.json() : null;
    }
}

// Create global instance
window.tarAPI = new TARApiClient();
