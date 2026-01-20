# Bionocular Landing Page

A static landing page for Bionocular.ai, optimized for Cloudflare Pages deployment.

## 🚀 Features

- **Static HTML/CSS/JS** - No build process required
- **No Dependencies** - Pure vanilla JavaScript
- **No Authentication** - Public landing page only
- **Cloudflare Optimized** - Ready for Cloudflare Pages deployment
- **Responsive Design** - Works on all devices
- **Modern UI** - Clean, professional design

## 📁 Project Structure

```
landing-page/
├── index.html          # Main HTML file
├── styles.css          # All styles
├── script.js           # JavaScript functionality
├── logo.png            # Logo image
├── Bionocular.mp4      # Hero video
├── .gitignore          # Git ignore rules
├── _redirects          # Cloudflare Pages redirects
└── README.md           # This file
```

## 🚀 Deployment to Cloudflare Pages

### Option 1: Deploy via Git (Recommended)

1. **Push to your personal repository:**
   ```bash
   cd landing-page
   git init
   git add .
   git commit -m "Initial commit: Static landing page"
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

2. **Connect to Cloudflare Pages:**
   - Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
   - Navigate to **Pages** → **Create a project**
   - Select **Connect to Git**
   - Choose your repository
   - Configure build settings:
     - **Build command:** (leave empty - no build needed)
     - **Build output directory:** `/` (root directory)
     - **Root directory:** `/` (or `landing-page` if repo root)
   - Click **Save and Deploy**

### Option 2: Deploy via Wrangler CLI

1. **Install Wrangler:**
   ```bash
   npm install -g wrangler
   ```

2. **Login to Cloudflare:**
   ```bash
   wrangler login
   ```

3. **Deploy:**
   ```bash
   cd landing-page
   wrangler pages deploy . --project-name=bionocular-landing
   ```

### Option 3: Direct Upload

1. Go to Cloudflare Dashboard → Pages
2. Create a new project
3. Select **Upload assets**
4. Zip the `landing-page` directory contents and upload

## 🔧 Local Development

Simply open `index.html` in a browser or use a local server:

```bash
# Using Python
python3 -m http.server 8000

# Using Node.js (http-server)
npx http-server -p 8000

# Using PHP
php -S localhost:8000
```

Then visit `http://localhost:8000`

## 📝 Customization

### Update Content

- Edit `index.html` to change text, sections, or structure
- Modify `styles.css` to change colors, fonts, or layout
- Update `script.js` to change behavior or add features

### Change Colors

Edit the CSS variables in `styles.css`:

```css
:root {
  --accent: #0EA5E9;      /* Primary accent color */
  --text: #0b1220;        /* Text color */
  --bg: #ffffff;          /* Background color */
  /* ... */
}
```

### Update Headlines

Edit the `headlines` array in `script.js`:

```javascript
const headlines = [
  'Your first headline',
  'Your second headline'
];
```

## 📦 Assets

The following assets should be in the root directory:

- `logo.png` - Logo image (37x37px recommended)
- `Bionocular.mp4` - Hero background video
- `favicon.ico` - Browser favicon (optional, can be added later)

## 🌐 Custom Domain

1. In Cloudflare Pages, go to your project
2. Click **Custom domains**
3. Add your domain
4. Follow the DNS configuration instructions

## 📄 License

This landing page is part of the Bionocular project.

## 🤝 Support

For questions or issues, contact: info@bionocular.ai

