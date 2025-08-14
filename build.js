#!/usr/bin/env node
/**
 * Build script for TAR Global Strategies Static Site
 * Minifies CSS, JS, and HTML files for production deployment
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Check if we have the required dependencies
try {
    require('uglify-js');
    require('clean-css');
    require('htmlmin');
} catch (e) {
    console.log('Installing build dependencies...');
    execSync('npm install', { stdio: 'inherit' });
}

const UglifyJS = require('uglify-js');
const CleanCSS = require('clean-css');
const htmlmin = require('htmlmin');

const sourceDir = 'static';
const distDir = 'dist';

console.log('🏗️  Building TAR Global Strategies Static Site...');

// Clean dist directory
if (fs.existsSync(distDir)) {
    fs.rmSync(distDir, { recursive: true });
}
fs.mkdirSync(distDir, { recursive: true });

// Copy directory structure
function copyDir(src, dest) {
    if (!fs.existsSync(dest)) {
        fs.mkdirSync(dest, { recursive: true });
    }
    
    const entries = fs.readdirSync(src, { withFileTypes: true });
    
    for (const entry of entries) {
        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);
        
        if (entry.isDirectory()) {
            copyDir(srcPath, destPath);
        } else {
            const ext = path.extname(entry.name).toLowerCase();
            
            if (ext === '.js') {
                // Minify JavaScript
                console.log(`📦 Minifying JS: ${entry.name}`);
                const code = fs.readFileSync(srcPath, 'utf8');
                const result = UglifyJS.minify(code, {
                    compress: {
                        dead_code: true,
                        drop_console: process.env.NODE_ENV === 'production'
                    },
                    mangle: process.env.NODE_ENV === 'production'
                });
                
                if (result.error) {
                    console.error(`❌ Error minifying ${entry.name}:`, result.error);
                    fs.copyFileSync(srcPath, destPath);
                } else {
                    fs.writeFileSync(destPath, result.code);
                }
            } else if (ext === '.css') {
                // Minify CSS
                console.log(`🎨 Minifying CSS: ${entry.name}`);
                const css = fs.readFileSync(srcPath, 'utf8');
                const result = new CleanCSS({
                    level: 2,
                    returnPromise: false
                }).minify(css);
                
                if (result.errors.length > 0) {
                    console.error(`❌ Error minifying ${entry.name}:`, result.errors);
                    fs.copyFileSync(srcPath, destPath);
                } else {
                    fs.writeFileSync(destPath, result.styles);
                }
            } else if (ext === '.html') {
                // Minify HTML
                console.log(`📄 Minifying HTML: ${entry.name}`);
                const html = fs.readFileSync(srcPath, 'utf8');
                try {
                    const minified = htmlmin(html);
                    fs.writeFileSync(destPath, minified);
                } catch (error) {
                    console.error(`❌ Error minifying ${entry.name}:`, error);
                    fs.copyFileSync(srcPath, destPath);
                }
            } else {
                // Copy other files as-is
                fs.copyFileSync(srcPath, destPath);
            }
        }
    }
}

// Build the static site
console.log('📁 Copying and processing files...');
copyDir(sourceDir, distDir);

// Create version file for cache busting
const version = {
    buildTime: new Date().toISOString(),
    version: require('./package.json').version,
    gitCommit: process.env.GIT_COMMIT || 'unknown',
    environment: process.env.NODE_ENV || 'development'
};

fs.writeFileSync(
    path.join(distDir, 'version.json'),
    JSON.stringify(version, null, 2)
);

// Create service worker for PWA
const serviceWorkerContent = `
// TAR Global Strategies Service Worker
const CACHE_NAME = 'tar-strategies-v${version.version}-${Date.now()}';
const STATIC_RESOURCES = [
    '/',
    '/dashboard.html',
    '/login.html',
    '/css/firm-3d.css',
    '/js/api-client.js',
    '/js/app.js'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(STATIC_RESOURCES))
    );
});

self.addEventListener('fetch', (event) => {
    // Only cache GET requests
    if (event.request.method !== 'GET') return;
    
    // Skip API requests (handle them differently)
    if (event.request.url.includes('/api/')) return;
    
    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                // Return cached version or fetch from network
                return response || fetch(event.request);
            })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});
`;

fs.writeFileSync(path.join(distDir, 'sw.js'), serviceWorkerContent);

// Create .htaccess for Apache (if needed)
const htaccessContent = `
# TAR Global Strategies - Apache Configuration
RewriteEngine On

# Handle client-side routing
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(?!api/|static/).*$ index.html [L]

# API proxy (if serving static and API from same domain)
RewriteRule ^api/(.*)$ http://localhost:8000/api/$1 [P,L]

# Security headers
Header always set X-Content-Type-Options nosniff
Header always set X-Frame-Options DENY
Header always set X-XSS-Protection "1; mode=block"
Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"

# Cache static assets
<FilesMatch "\\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$">
    ExpiresActive On
    ExpiresDefault "access plus 1 year"
    Header set Cache-Control "public, immutable"
</FilesMatch>

# Cache HTML with shorter expiry
<FilesMatch "\\.html$">
    ExpiresActive On
    ExpiresDefault "access plus 1 day"
    Header set Cache-Control "public, must-revalidate"
</FilesMatch>

# Compress text files
<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/plain
    AddOutputFilterByType DEFLATE text/html
    AddOutputFilterByType DEFLATE text/xml
    AddOutputFilterByType DEFLATE text/css
    AddOutputFilterByType DEFLATE application/xml
    AddOutputFilterByType DEFLATE application/xhtml+xml
    AddOutputFilterByType DEFLATE application/rss+xml
    AddOutputFilterByType DEFLATE application/javascript
    AddOutputFilterByType DEFLATE application/x-javascript
</IfModule>
`;

fs.writeFileSync(path.join(distDir, '.htaccess'), htaccessContent);

// Create nginx.conf for Nginx
const nginxConfig = `
# TAR Global Strategies - Nginx Configuration

server {
    listen 80;
    server_name your-domain.com;
    root /path/to/dist;
    index index.html;

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # Serve static files
    location / {
        try_files $uri $uri/ /index.html;
        
        # Cache static assets
        location ~* \\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
        
        # Cache HTML with shorter expiry
        location ~* \\.html$ {
            expires 1d;
            add_header Cache-Control "public, must-revalidate";
        }
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
}
`;

fs.writeFileSync(path.join(distDir, 'nginx.conf'), nginxConfig);

// Generate build report
const buildReport = {
    buildTime: new Date().toISOString(),
    version: version.version,
    files: {
        total: 0,
        html: 0,
        css: 0,
        js: 0,
        assets: 0
    },
    sizes: {
        original: 0,
        compressed: 0,
        savings: 0
    }
};

// Calculate file statistics
function calculateStats(dir, prefix = '') {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    
    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        
        if (entry.isDirectory()) {
            calculateStats(fullPath, path.join(prefix, entry.name));
        } else {
            const ext = path.extname(entry.name).toLowerCase();
            const stats = fs.statSync(fullPath);
            
            buildReport.files.total++;
            buildReport.sizes.compressed += stats.size;
            
            if (ext === '.html') buildReport.files.html++;
            else if (ext === '.css') buildReport.files.css++;
            else if (ext === '.js') buildReport.files.js++;
            else buildReport.files.assets++;
        }
    }
}

calculateStats(distDir);

// Calculate original size for comparison
if (fs.existsSync(sourceDir)) {
    function calculateOriginalSize(dir) {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        let size = 0;
        
        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            
            if (entry.isDirectory()) {
                size += calculateOriginalSize(fullPath);
            } else {
                const stats = fs.statSync(fullPath);
                size += stats.size;
            }
        }
        
        return size;
    }
    
    buildReport.sizes.original = calculateOriginalSize(sourceDir);
    buildReport.sizes.savings = buildReport.sizes.original - buildReport.sizes.compressed;
}

console.log('\n📊 Build Report:');
console.log(`✅ Files processed: ${buildReport.files.total}`);
console.log(`   📄 HTML: ${buildReport.files.html}`);
console.log(`   🎨 CSS: ${buildReport.files.css}`);
console.log(`   📦 JS: ${buildReport.files.js}`);
console.log(`   🖼️  Assets: ${buildReport.files.assets}`);

if (buildReport.sizes.original > 0) {
    const savingsPercent = ((buildReport.sizes.savings / buildReport.sizes.original) * 100).toFixed(1);
    console.log(`💾 Size: ${(buildReport.sizes.compressed / 1024).toFixed(1)}KB (${savingsPercent}% smaller)`);
}

fs.writeFileSync(
    path.join(distDir, 'build-report.json'),
    JSON.stringify(buildReport, null, 2)
);

console.log(`\n🚀 Build complete! Files ready in '${distDir}' directory`);
console.log('📝 Generated files:');
console.log('   - version.json (build info)');
console.log('   - sw.js (service worker)');
console.log('   - .htaccess (Apache config)');
console.log('   - nginx.conf (Nginx config)');
console.log('   - build-report.json (build statistics)');
console.log('\n💡 Next steps:');
console.log('   1. Deploy dist/ folder to CDN or static hosting');
console.log('   2. Configure web server using provided config files');
console.log('   3. Update API backend to remove template rendering');
console.log('   4. Test the static site with your API backend');
