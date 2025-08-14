#!/usr/bin/env node
/**
 * Simple build script for TAR Global Strategies Static Site
 * Just copies files from static/ to dist/ with basic optimization
 */

const fs = require('fs');
const path = require('path');

const sourceDir = 'static';
const distDir = 'dist';

console.log('🏗️  Building TAR Global Strategies Static Site...');

// Clean dist directory
if (fs.existsSync(distDir)) {
    fs.rmSync(distDir, { recursive: true });
}
fs.mkdirSync(distDir, { recursive: true });

// Simple copy function
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
            console.log(`📄 Copying: ${entry.name}`);
            fs.copyFileSync(srcPath, destPath);
        }
    }
}

// Copy all files
console.log('📁 Copying files...');
copyDir(sourceDir, distDir);

// Copy 404.html as a fallback for SPA routing
const source404 = path.join(sourceDir, '404.html');
const dest404 = path.join(distDir, '404.html');
if (fs.existsSync(source404)) {
    fs.copyFileSync(source404, dest404);
    console.log('✅ Copied 404.html for SPA fallback');
}

// Update API URLs in JS files for production
const apiClientPath = path.join(distDir, 'js', 'api-client.js');
if (fs.existsSync(apiClientPath)) {
    console.log('🔧 Updating API URLs...');
    let content = fs.readFileSync(apiClientPath, 'utf8');
    
    // Replace the API URL logic with environment variable
    content = content.replace(
        /const apiBase = window\.VITE_API_URL.*$/m,
        'const apiBase = "https://tar-strategies-api.onrender.com";'
    );
    
    fs.writeFileSync(apiClientPath, content);
}

// Create version file
const version = {
    buildTime: new Date().toISOString(),
    version: require('./package.json').version,
    environment: 'production'
};

fs.writeFileSync(
    path.join(distDir, 'version.json'),
    JSON.stringify(version, null, 2)
);

console.log('✅ Build complete! Files ready in dist/ directory');
console.log('📝 Files built:');
console.log('   - Static HTML, CSS, JS files');
console.log('   - API URLs configured for production');
console.log('   - Version info generated');
