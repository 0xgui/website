# Guilherme Silva - Personal Website

A minimal, brutalist personal website built with pure HTML, CSS, and vanilla JavaScript.

## Features

- **Zero dependencies** - No npm packages, no frameworks, nothing
- Super fast and lightweight (~8.5KB total)
- Light theme with brutalist design
- Fetches latest articles from Binary Paths (Substack)
- Optimized for Cloudflare Pages

## Development

Just open `index.html` in your browser. That's it.

Or use Python's built-in server:

```bash
python3 -m http.server 3000
```

Or if you have PHP:

```bash
php -S localhost:3000
```

## Deploy to Cloudflare Pages

### Option 1: Direct Upload (Simplest)
1. Go to Cloudflare Pages dashboard
2. Upload the three files: `index.html`, `style.css`, `app.js`
3. Done!

### Option 2: GitHub Integration
1. Push to GitHub
2. Connect repository to Cloudflare Pages
3. Build command: *leave empty*
4. Build output directory: `/` (root)
5. Deploy!

No build step needed. No npm install. Just deploy the files.

## Files

- `index.html` - 3.2KB
- `style.css` - 3.1KB
- `app.js` - 2.2KB
- **Total: 8.5KB**

## Tech Stack

- HTML
- CSS
- Vanilla JavaScript

That's it. No package.json needed, no node_modules, no build process.

## Performance

- Zero dependencies
- No JavaScript frameworks
- No CSS frameworks
- Total page size: 8.5KB
- Loads in milliseconds
- Perfect Lighthouse score
