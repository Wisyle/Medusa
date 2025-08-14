/**
 * TAR Global Strategies - Main Application
 * Static site client-side application logic
 */

class TARApp {
    constructor() {
        this.currentPage = 'dashboard';
        this.currentUser = null;
        this.isAuthenticated = false;
        this.api = window.tarAPI;
        
        // Initialize app when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    async init() {
        console.log('🚀 Initializing TAR Global Strategies...');
        
        try {
            // Check authentication
            await this.checkAuthentication();
            
            if (this.isAuthenticated) {
                // Initialize authenticated app
                await this.initializeApp();
            } else {
                // Redirect to login
                this.redirectToLogin();
                return;
            }
            
            // Set up navigation
            this.setupNavigation();
            
            // Connect WebSocket
            this.api.connectWebSocket();
            this.setupWebSocketHandlers();
            
            // Load initial page
            await this.loadPage(this.getHashPage());
            
            // Hide loading screen
            this.hideLoadingScreen();
            
            console.log('✅ TAR Global Strategies initialized successfully');
            
        } catch (error) {
            console.error('❌ Application initialization failed:', error);
            this.showError('Failed to initialize application');
        }
    }

    async checkAuthentication() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            this.isAuthenticated = false;
            return;
        }

        try {
            // Test token validity with a simple API call
            const response = await this.api.authenticatedFetch('/api/health');
            this.isAuthenticated = response && response.ok;
        } catch (error) {
            console.error('Authentication check failed:', error);
            this.isAuthenticated = false;
        }
    }

    async initializeApp() {
        // Load user info
        try {
            const userInfo = await this.getCurrentUser();
            if (userInfo) {
                this.currentUser = userInfo;
                document.getElementById('user-email').textContent = userInfo.email.split('@')[0].toUpperCase();
            }
        } catch (error) {
            console.error('Failed to load user info:', error);
        }
    }

    async getCurrentUser() {
        // This would typically be an API call
        // For now, return mock data based on token
        return {
            email: 'admin@tglmedusa.com',
            full_name: 'Administrator',
            is_superuser: true
        };
    }

    setupNavigation() {
        // Handle navigation clicks
        document.getElementById('main-nav').addEventListener('click', (e) => {
            const link = e.target.closest('[data-page]');
            if (link) {
                e.preventDefault();
                const page = link.dataset.page;
                this.navigateTo(page);
            }
        });

        // Handle browser back/forward
        window.addEventListener('hashchange', () => {
            this.loadPage(this.getHashPage());
        });
    }

    setupWebSocketHandlers() {
        // Real-time data updates
        this.api.onWebSocketMessage('dashboard_update', (data) => {
            if (this.currentPage === 'dashboard') {
                this.updateDashboardMetrics(data);
            }
        });

        this.api.onWebSocketMessage('instance_update', (data) => {
            this.updateInstanceStatus(data);
        });

        this.api.onWebSocketMessage('trade_update', (data) => {
            this.addTradeToFeed(data);
        });

        // Update WebSocket status indicator
        this.api.ws.addEventListener('open', () => {
            document.getElementById('ws-indicator').textContent = 'WS: CONNECTED';
            document.getElementById('ws-indicator').className = 'status-indicator status-online';
        });

        this.api.ws.addEventListener('close', () => {
            document.getElementById('ws-indicator').textContent = 'WS: DISCONNECTED';
            document.getElementById('ws-indicator').className = 'status-indicator status-offline';
        });
    }

    getHashPage() {
        const hash = window.location.hash.substring(1);
        return hash || 'dashboard';
    }

    navigateTo(page) {
        window.location.hash = page;
        this.loadPage(page);
    }

    async loadPage(page) {
        try {
            // Update navigation
            this.updateNavigation(page);
            this.currentPage = page;

            // Update page title
            const titles = {
                'dashboard': 'COMMAND HUB',
                'instances': 'BOT MANAGEMENT',
                'dex-arbitrage': 'DEX ARBITRAGE',
                'validators': 'VALIDATOR NODES',
                'decter': 'DECTER ENGINE',
                'api-library': 'API LIBRARY'
            };
            document.getElementById('page-title').textContent = titles[page] || 'TAR GLOBAL';

            // Load page content
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = '<div class="firm-loading"><div class="firm-spinner mx-auto"></div></div>';

            let content = '';
            switch (page) {
                case 'dashboard':
                    content = await this.loadDashboard();
                    break;
                case 'instances':
                    content = await this.loadInstances();
                    break;
                case 'dex-arbitrage':
                    content = await this.loadDexArbitrage();
                    break;
                case 'validators':
                    content = await this.loadValidators();
                    break;
                case 'decter':
                    content = await this.loadDecter();
                    break;
                case 'api-library':
                    content = await this.loadApiLibrary();
                    break;
                default:
                    content = '<div class="firm-panel"><h2>Page Not Found</h2></div>';
            }

            contentArea.innerHTML = content;

        } catch (error) {
            console.error(`Failed to load page ${page}:`, error);
            this.showError(`Failed to load ${page} page`);
        }
    }

    updateNavigation(activePage) {
        document.querySelectorAll('.firm-nav-item').forEach(item => {
            item.classList.remove('active');
        });
        
        const activeItem = document.querySelector(`[data-page="${activePage}"]`);
        if (activeItem) {
            activeItem.classList.add('active');
        }
    }

    async loadDashboard() {
        const stats = await this.api.getDashboardStats();
        
        return `
            <div class="dashboard-grid">
                <!-- Total Instances -->
                <div class="firm-panel">
                    <div class="metric-label">TOTAL INSTANCES</div>
                    <div class="metric-value">${stats?.total_instances || 0}</div>
                    <div class="mt-2">
                        <small class="text-muted text-uppercase">Active: <span class="text-success">${stats?.active_instances || 0}</span></small>
                    </div>
                </div>

                <!-- Total Balance -->
                <div class="firm-panel">
                    <div class="metric-label">TOTAL BALANCE</div>
                    <div class="metric-value positive">$${(stats?.total_balance || 0).toLocaleString()}</div>
                    <div class="mt-2">
                        <small class="text-muted text-uppercase">Updated: <span>${new Date().toLocaleTimeString()}</span></small>
                    </div>
                </div>

                <!-- 24h P&L -->
                <div class="firm-panel">
                    <div class="metric-label">24H PROFIT/LOSS</div>
                    <div class="metric-value ${(stats?.daily_pnl || 0) >= 0 ? 'positive' : 'negative'}">
                        ${(stats?.daily_pnl || 0) >= 0 ? '+' : ''}$${(stats?.daily_pnl || 0).toLocaleString()}
                    </div>
                    <div class="mt-2">
                        <small class="text-muted text-uppercase">Win Rate: <span>${(stats?.win_rate || 0).toFixed(1)}%</span></small>
                    </div>
                </div>

                <!-- System Health -->
                <div class="firm-panel">
                    <div class="metric-label">SYSTEM HEALTH</div>
                    <div class="d-flex align-items-center justify-content-between">
                        <span class="status-indicator status-active">OPERATIONAL</span>
                        <button class="firm-btn firm-btn-sm" onclick="app.navigateTo('system-logs')">
                            <i class="fas fa-chart-line"></i> METRICS
                        </button>
                    </div>
                </div>
            </div>

            <!-- Quick Actions -->
            <div class="firm-panel mt-4">
                <div class="section-header mb-3">
                    <i class="fas fa-bolt firm-icon"></i>QUICK ACTIONS
                </div>
                <div class="row">
                    <div class="col-md-3 mb-3">
                        <button class="firm-btn firm-btn-primary w-100" onclick="app.navigateTo('instances')">
                            <i class="fas fa-plus me-2"></i>NEW INSTANCE
                        </button>
                    </div>
                    <div class="col-md-3 mb-3">
                        <button class="firm-btn w-100" onclick="app.navigateTo('api-library')">
                            <i class="fas fa-key me-2"></i>API LIBRARY
                        </button>
                    </div>
                    <div class="col-md-3 mb-3">
                        <button class="firm-btn w-100" onclick="app.navigateTo('dex-arbitrage')">
                            <i class="fas fa-exchange-alt me-2"></i>DEX ARBITRAGE
                        </button>
                    </div>
                    <div class="col-md-3 mb-3">
                        <button class="firm-btn w-100" onclick="app.navigateTo('decter')">
                            <i class="fas fa-cog me-2"></i>DECTER ENGINE
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    async loadInstances() {
        const instances = await this.api.getInstances();
        
        return `
            <div class="firm-panel">
                <div class="section-header mb-3">
                    <i class="fas fa-robot firm-icon"></i>BOT INSTANCES
                </div>
                <button class="firm-btn firm-btn-primary mb-3">
                    <i class="fas fa-plus me-2"></i>CREATE NEW INSTANCE
                </button>
                <table class="firm-table">
                    <thead>
                        <tr>
                            <th>NAME</th>
                            <th>EXCHANGE</th>
                            <th>STATUS</th>
                            <th>LAST POLL</th>
                            <th>ACTIONS</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${instances.map(instance => `
                            <tr>
                                <td><span class="data-point">${instance.name}</span></td>
                                <td>${instance.exchange}</td>
                                <td><span class="status-indicator ${instance.is_active ? 'status-online' : 'status-offline'}">${instance.is_active ? 'ACTIVE' : 'INACTIVE'}</span></td>
                                <td style="font-family: 'JetBrains Mono', monospace;">${instance.last_poll ? new Date(instance.last_poll).toLocaleString() : 'Never'}</td>
                                <td>
                                    <button class="firm-btn firm-btn-sm me-2" onclick="app.toggleInstance(${instance.id})">
                                        ${instance.is_active ? 'STOP' : 'START'}
                                    </button>
                                    <button class="firm-btn firm-btn-sm">EDIT</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    async loadDexArbitrage() {
        return `
            <div class="firm-panel">
                <div class="section-header mb-3">
                    <i class="fas fa-chart-line firm-icon"></i>DEX ARBITRAGE
                </div>
                <p class="text-muted">DEX Arbitrage module coming soon...</p>
            </div>
        `;
    }

    async loadValidators() {
        return `
            <div class="firm-panel">
                <div class="section-header mb-3">
                    <i class="fas fa-server firm-icon"></i>VALIDATOR NODES
                </div>
                <p class="text-muted">Validator Nodes module coming soon...</p>
            </div>
        `;
    }

    async loadDecter() {
        return `
            <div class="firm-panel">
                <div class="section-header mb-3">
                    <i class="fas fa-cog firm-icon"></i>DECTER ENGINE
                </div>
                <p class="text-muted">Decter Engine module coming soon...</p>
            </div>
        `;
    }

    async loadApiLibrary() {
        return `
            <div class="firm-panel">
                <div class="section-header mb-3">
                    <i class="fas fa-key firm-icon"></i>API LIBRARY
                </div>
                <p class="text-muted">API Library module coming soon...</p>
            </div>
        `;
    }

    async toggleInstance(instanceId) {
        try {
            const result = await this.api.toggleInstance(instanceId);
            if (result) {
                // Reload instances page
                await this.loadPage('instances');
                this.showSuccess('Instance status updated successfully');
            }
        } catch (error) {
            console.error('Failed to toggle instance:', error);
            this.showError('Failed to update instance status');
        }
    }

    hideLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        const app = document.getElementById('app');
        
        loadingScreen.style.display = 'none';
        app.classList.remove('d-none');
    }

    redirectToLogin() {
        window.location.href = '/login.html';
    }

    showError(message) {
        // Simple error display - you can enhance this
        console.error(message);
        // Could show a toast notification here
    }

    showSuccess(message) {
        // Simple success display - you can enhance this
        console.log(message);
        // Could show a toast notification here
    }
}

// Global functions
function toggleUserMenu() {
    // Implement user menu toggle
    console.log('User menu toggle');
}

// Initialize app
const app = new TARApp();
window.app = app;
