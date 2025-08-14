# Static Site Architecture Plan

## Overview
Transform the TAR Global Strategies web interface into a static site architecture while maintaining backend services for data processing and real-time updates.

## Architecture Components

### 1. Static Frontend (CDN-Ready)
- **HTML/CSS/JS Files**: Pre-built static files served directly
- **No Server-Side Rendering**: All UI rendering happens in the browser
- **API-Driven**: All dynamic data fetched via API calls
- **Benefits**:
  - Faster load times
  - Better caching
  - Can be served from CDN
  - Reduced server load

### 2. API Backend (FastAPI)
- **Pure API Service**: No template rendering
- **RESTful Endpoints**: All data operations via API
- **WebSocket Support**: Real-time updates
- **Authentication**: JWT tokens for API access

### 3. Worker Services (Unchanged)
- **Background Processing**: Polling, monitoring, etc.
- **Database Operations**: All heavy lifting
- **Independent Services**: Can scale separately

## Implementation Steps

### Phase 1: Frontend Separation
1. Convert all templates to static HTML
2. Move all dynamic logic to JavaScript
3. Create API client library
4. Implement client-side routing

### Phase 2: API Optimization
1. Remove template rendering from FastAPI
2. Optimize API endpoints for frontend needs
3. Implement proper CORS handling
4. Add API versioning

### Phase 3: Static Deployment
1. Build process for static assets
2. Configure CDN for static files
3. Separate deployment for API and static files
4. Update nginx/reverse proxy configuration

## File Structure

```
tarc/
├── static-site/              # New static site directory
│   ├── index.html           # Main entry point
│   ├── dashboard.html       # Dashboard page
│   ├── css/
│   │   ├── firm-3d.css     # Firm 3D design system
│   │   └── app.css         # Application styles
│   ├── js/
│   │   ├── api-client.js   # API client library
│   │   ├── app.js          # Main application logic
│   │   └── components/     # UI components
│   └── assets/             # Images, fonts, etc.
├── app/                     # Backend API only
│   ├── main.py             # FastAPI app (API only)
│   ├── routes/             # API routes
│   └── services/           # Backend services
└── workers/                # Background services
```

## API Client Example

```javascript
// api-client.js
class TARApiClient {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
        this.token = localStorage.getItem('access_token');
    }
    
    async authenticatedFetch(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        const response = await fetch(`${this.baseURL}${endpoint}`, {
            ...options,
            headers
        });
        
        if (response.status === 401) {
            // Token expired, redirect to login
            window.location.href = '/login.html';
            return;
        }
        
        return response;
    }
    
    // API methods
    async getInstances() {
        const response = await this.authenticatedFetch('/instances');
        return response.json();
    }
    
    async getDashboardStats() {
        const response = await this.authenticatedFetch('/dashboard/stats');
        return response.json();
    }
    
    // ... more API methods
}
```

## Benefits

1. **Performance**
   - Static files load instantly
   - CDN distribution for global access
   - Reduced server load

2. **Scalability**
   - Frontend scales infinitely via CDN
   - API can be scaled independently
   - Workers scale based on processing needs

3. **Maintenance**
   - Clear separation of concerns
   - Easier to update UI without backend changes
   - Can use modern frontend tooling

4. **Security**
   - No server-side rendering vulnerabilities
   - API-only backend is easier to secure
   - Clear authentication boundaries

## Deployment Options

### Option 1: Fully Static
- Host static files on CDN (CloudFlare, Netlify, etc.)
- API on separate subdomain (api.example.com)
- Workers on cloud services

### Option 2: Hybrid
- Nginx serves static files
- Same domain with /api prefix for backend
- Easier CORS handling

### Option 3: Progressive Enhancement
- Start with current setup
- Gradually move pages to static
- Maintain compatibility during transition

## Next Steps

1. Create build process for static assets
2. Convert one page at a time (start with dashboard)
3. Create comprehensive API documentation
4. Implement client-side state management
5. Add offline support with service workers
