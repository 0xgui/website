// Fetch and display latest articles from Substack RSS feed
async function loadArticles() {
    const articlesContainer = document.getElementById('articles');
    const loadingIndicator = document.getElementById('articles-loading');

    try {
        // Replace with your Cloudflare Worker URL after deployment
        const response = await fetch('https://rss.silvags.com');
        const data = await response.json();

        if (data.items && data.items.length > 0) {
            // Get the 5 most recent articles
            const articles = data.items.slice(0, 5);

            articlesContainer.innerHTML = articles.map(article => {
                // Strip HTML tags from description
                const description = article.description.replace(/<[^>]*>/g, '').substring(0, 150);

                // Format date
                const date = new Date(article.pubDate).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                });

                return `
                    <article class="article-item">
                        <time>${date}</time>
                        <h3><a href="${article.link}" target="_blank" rel="noopener">${article.title}</a></h3>
                        <p>${description}...</p>
                    </article>
                `;
            }).join('');

            loadingIndicator.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading articles:', error);
        articlesContainer.innerHTML = '<p>Unable to load articles. Visit <a href="https://binarypaths.substack.com" target="_blank" rel="noopener">Binary Paths</a> directly.</p>';
        loadingIndicator.style.display = 'none';
    }
}

// Load articles when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadArticles);
} else {
    loadArticles();
}

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});

// Typing Animation
function typeWriter() {
    const tagline = document.querySelector('.tagline');
    if (!tagline) return;

    const text = tagline.textContent;
    tagline.textContent = '';
    tagline.classList.add('typing-text');

    let i = 0;
    function type() {
        if (i < text.length) {
            tagline.textContent += text.charAt(i);
            i++;
            setTimeout(type, 100);
        } else {
            // Remove cursor animation after typing is done
            setTimeout(() => {
                tagline.style.borderRight = 'none';
            }, 1000);
        }
    }

    // Start typing after a short delay
    setTimeout(type, 500);
}

// Initialize typing animation
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', typeWriter);
} else {
    typeWriter();
}

// ── Robot Arm Animator ────────────────────────────────────────────────────────
// Drives a pick-and-place loop on the SVG arm in the intro section.
// Reads IDs: arm-shoulder, arm-elbow, arm-wrist, arm-jaw-left, arm-jaw-right,
//            arm-target, j1-val, j2-val, j3-val, gr-val
class RobotArmAnimator {
    constructor() {
        const g = id => document.getElementById(id);
        this.els = {
            shoulder: g('arm-shoulder'), elbow: g('arm-elbow'),
            wrist:    g('arm-wrist'),    jawL:  g('arm-jaw-left'),
            jawR:     g('arm-jaw-right'),target: g('arm-target'),
            j1: g('j1-val'), j2: g('j2-val'), j3: g('j3-val'), gr: g('gr-val'),
        };
        if (!this.els.shoulder) return;

        this.t0    = performance.now();
        this.CYCLE = 7000; // ms per full pick-and-place cycle

        // Keyframes: { t∈[0,1], s=shoulder, e=elbow, w=wrist, g=gripper∈[0,1] }
        this.KF = [
            { t: 0.00, s:  0,  e: -10, w:  5,  g: 0 }, // rest
            { t: 0.28, s:  25, e:  42, w: -28, g: 0 }, // reach forward-down
            { t: 0.37, s:  25, e:  42, w: -28, g: 1 }, // grip
            { t: 0.60, s: -18, e: -22, w:  14, g: 1 }, // lift & swing back
            { t: 0.75, s:  16, e:  22, w: -18, g: 1 }, // move to place
            { t: 0.84, s:  16, e:  22, w: -18, g: 0 }, // release
            { t: 1.00, s:  0,  e: -10, w:  5,  g: 0 }, // return to rest
        ];

        requestAnimationFrame(() => this.tick());
    }

    // Cubic ease-in-out
    ease(t) { return t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2; }

    interpolate(t) {
        const kf = this.KF;
        for (let i = 0; i < kf.length - 1; i++) {
            if (t >= kf[i].t && t <= kf[i + 1].t) {
                const p = this.ease((t - kf[i].t) / (kf[i + 1].t - kf[i].t));
                const l = (a, b) => a + (b - a) * p;
                return { s: l(kf[i].s, kf[i+1].s), e: l(kf[i].e, kf[i+1].e),
                         w: l(kf[i].w, kf[i+1].w), g: l(kf[i].g, kf[i+1].g) };
            }
        }
        return kf[kf.length - 1];
    }

    tick() {
        const t = ((performance.now() - this.t0) % this.CYCLE) / this.CYCLE;
        const a = this.interpolate(t);
        const { shoulder, elbow, wrist, jawL, jawR, target, j1, j2, j3, gr } = this.els;

        shoulder.setAttribute('transform', `translate(100,248) rotate(${a.s})`);
        elbow   .setAttribute('transform', `translate(0,-95)  rotate(${a.e})`);
        wrist   .setAttribute('transform', `translate(0,-75)  rotate(${a.w})`);

        const jaw = a.g * 9;
        jawL  .setAttribute('transform', `translate(${-jaw},0)`);
        jawR  .setAttribute('transform', `translate(${jaw},0)`);
        target.setAttribute('opacity', a.g > 0.5 ? String((a.g - 0.5) * 2) : '0');

        const fmt = v => (v >= 0 ? '+' : '') + Math.round(v) + '°';
        if (j1) j1.textContent = fmt(a.s);
        if (j2) j2.textContent = fmt(a.e);
        if (j3) j3.textContent = fmt(a.w);
        if (gr) gr.textContent = a.g > 0.5 ? 'CLOSED' : 'OPEN';

        requestAnimationFrame(() => this.tick());
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new RobotArmAnimator());
} else {
    new RobotArmAnimator();
}

