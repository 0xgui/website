// ── Fetch latest articles from Substack RSS ────────────────────────────────────
async function loadArticles() {
    const articlesContainer = document.getElementById('articles');
    const loadingIndicator = document.getElementById('articles-loading');

    try {
        const response = await fetch('https://rss.silvags.com');
        const data = await response.json();

        if (data.items && data.items.length > 0) {
            const articles = data.items.slice(0, 5);

            articlesContainer.innerHTML = articles.map(article => {
                const description = article.description.replace(/<[^>]*>/g, '').substring(0, 150);
                const date = new Date(article.pubDate).toLocaleDateString('en-US', {
                    year: 'numeric', month: 'short', day: 'numeric'
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

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadArticles);
} else {
    loadArticles();
}

// ── Smooth scroll ──────────────────────────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) target.scrollIntoView({ behavior: 'smooth' });
    });
});

// ── Typing animation ───────────────────────────────────────────────────────────
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
            setTimeout(() => { tagline.style.borderRight = 'none'; }, 1000);
        }
    }
    setTimeout(type, 500);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', typeWriter);
} else {
    typeWriter();
}

// ── Interactive Robot Arm — User picks the cube ─────────────────────────────────

class MouseArmController {
    constructor() {
        const g = id => document.getElementById(id);
        this.els = {
            shoulder: g('arm-shoulder'), elbow: g('arm-elbow'),
            wrist:    g('arm-wrist'),    jawL:  g('arm-jaw-left'),
            jawR:     g('arm-jaw-right'),target: g('arm-target'),
        };
        this.objEl = g('pickup-object');
        this.svg = document.getElementById('robot-arm-svg');
        if (!this.svg || !this.els.shoulder) return;

        this.SX = 90;   this.SY = 248;
        this.L1 = 95;   this.L2 = 75;   this.L3 = 55;

        // Cube home (on left pedestal)
        this.ped1 = { x: 221, y: 246 };
        this.ped2 = { x: 301, y: 246 };
        this.objX = this.ped1.x;
        this.objY = this.ped1.y;
        this.carried = false;

        // Mouse / interaction
        this.mouseX = 0;
        this.mouseY = 0;
        this.mouseOver = false;
        this.clickPending = false;
        this.grip = 0;  // 0..1 smooth grip state

        // Current angles
        this.angles = { s: 18, e: 40, w: -12 };

        // Events
        this.svg.addEventListener('mousemove', e => this.onMouseMove(e));
        this.svg.addEventListener('mouseenter', () => { this.mouseOver = true; });
        this.svg.addEventListener('mouseleave', () => { this.mouseOver = false; });
        this.svg.addEventListener('mousedown', () => { this.clickPending = true; });
        this.svg.addEventListener('mouseup', () => { this.clickPending = false; });
        this.svg.addEventListener('touchmove', e => {
            e.preventDefault();
            const t = e.touches[0];
            this.onMouseMove(t);
            this.mouseOver = true;
        }, { passive: false });
        this.svg.addEventListener('touchend', () => { this.mouseOver = false; this.clickPending = false; });
        this.svg.addEventListener('touchstart', () => { this.clickPending = true; this.mouseOver = true; });

        requestAnimationFrame(() => this.tick());
    }

    svgPoint(e) {
        const pt = this.svg.createSVGPoint();
        pt.x = e.clientX;
        pt.y = e.clientY;
        return pt.matrixTransform(this.svg.getScreenCTM().inverse());
    }

    onMouseMove(e) {
        const pt = this.svgPoint(e);
        this.mouseX = pt.x;
        this.mouseY = pt.y;
    }

    // Forward kinematics — tip position from angles
    tipPos(a) {
        const sr = a.s * Math.PI / 180;
        const er = (a.s + a.e) * Math.PI / 180;
        const wr = (a.s + a.e + a.w) * Math.PI / 180;
        return {
            x: this.SX + this.L1 * Math.sin(sr) + this.L2 * Math.sin(er) + this.L3 * Math.sin(wr),
            y: this.SY - this.L1 * Math.cos(sr) - this.L2 * Math.cos(er) - this.L3 * Math.cos(wr),
        };
    }

    // Raw 2-joint IK — returns angles for a given target (wrist-oriented)
    _solveIK(tx, ty) {
        const lx = tx - this.SX;
        const ly = this.SY - ty;
        let d = Math.sqrt(lx * lx + ly * ly);
        const maxReach = this.L1 + this.L2;
        const minReach = Math.abs(this.L1 - this.L2);
        if (d < minReach) d = minReach;
        if (d > maxReach - 2) d = maxReach - 2;

        const targetAngle = Math.atan2(lx, ly);

        let cosB = (this.L1 * this.L1 + this.L2 * this.L2 - d * d) / (2 * this.L1 * this.L2);
        cosB = Math.max(-1, Math.min(1, cosB));
        const beta = Math.acos(cosB);
        const elbowDeg = (Math.PI - beta) * 180 / Math.PI;

        let cosA = (this.L1 * this.L1 + d * d - this.L2 * this.L2) / (2 * this.L1 * d);
        cosA = Math.max(-1, Math.min(1, cosA));
        const alpha = Math.acos(cosA);

        const shoulderDeg = (targetAngle - alpha) * 180 / Math.PI;

        const sRad = shoulderDeg * Math.PI / 180;
        const eRad = (shoulderDeg + elbowDeg) * Math.PI / 180;
        const wristX = this.SX + this.L1 * Math.sin(sRad) + this.L2 * Math.sin(eRad);
        const wristY = this.SY - this.L1 * Math.cos(sRad) - this.L2 * Math.cos(eRad);

        const wristAngle = Math.atan2(tx - wristX, wristY - ty) * 180 / Math.PI;
        let wristDeg = wristAngle - (shoulderDeg + elbowDeg);
        while (wristDeg > 180) wristDeg -= 360;
        while (wristDeg < -180) wristDeg += 360;
        wristDeg = Math.max(-60, Math.min(60, wristDeg));

        return { s: shoulderDeg, e: elbowDeg, w: wristDeg };
    }

    // Tip-tracking IK: 2-pass refinement so gripper tip lands exactly on (tx, ty)
    solveIK(tx, ty) {
        // Pass 1
        let ik = this._solveIK(tx, ty);
        // Pass 2: correct for tip offset
        const tip = this.tipPos(ik);
        ik = this._solveIK(tx + (tx - tip.x), ty + (ty - tip.y));
        return ik;
    }

    tick() {
        const { shoulder, elbow, wrist, jawL, jawR, target } = this.els;
        let a = this.angles;

        // ── Target computation ────────────────────────────────────────────────
        let tx, ty;

        if (!this.mouseOver) {
            // Return to rest when mouse leaves
            tx = 130;
            ty = 200;
        } else {
            // Clamp mouse to reachable workspace (don't let arm invert)
            tx = Math.max(60, Math.min(340, this.mouseX));
            ty = Math.max(80, Math.min(260, this.mouseY));
        }

        const ik = this.solveIK(tx, ty);

        // Smooth toward target (heavy smoothing = no shaking)
        a.s += (ik.s - a.s) * 0.08;
        a.e += (ik.e - a.e) * 0.08;
        a.w += (ik.w - a.w) * 0.10;

        // ── Pickup / drop logic ───────────────────────────────────────────────
        const tip = this.tipPos(a);
        const dist = Math.hypot(tip.x - this.objX, tip.y - this.objY);
        const pickupRange = 16;

        if (this.clickPending) {
            if (!this.carried && dist < pickupRange) {
                // Grab!
                this.carried = true;
            } else if (this.carried) {
                // Drop
                this.carried = false;
                // Clamp drop position to stay in view
                this.objX = Math.max(20, Math.min(340, tip.x));
                this.objY = Math.max(180, Math.min(260, tip.y));
            }
            this.clickPending = false;
        }

        // Smooth grip animation
        const gripTarget = this.carried ? 1 : 0;
        this.grip += (gripTarget - this.grip) * 0.15;

        // Return object home if mouse leaves and not carried
        if (!this.mouseOver && !this.carried) {
            this.objX += (this.ped1.x - this.objX) * 0.04;
            this.objY += (this.ped1.y - this.objY) * 0.04;
        }

        // When carrying, object follows gripper tip
        if (this.carried) {
            this.objX += (tip.x - this.objX) * 0.35;
            this.objY += (tip.y - this.objY) * 0.35;
        }

        // ── Render ────────────────────────────────────────────────────────────
        shoulder.setAttribute('transform', `translate(${this.SX},${this.SY}) rotate(${a.s.toFixed(2)})`);
        elbow   .setAttribute('transform', `translate(0,-95) rotate(${a.e.toFixed(2)})`);
        wrist   .setAttribute('transform', `translate(0,-75) rotate(${a.w.toFixed(2)})`);

        const jaw = this.grip * 9;
        jawL.setAttribute('transform', `translate(${-jaw.toFixed(1)},0)`);
        jawR.setAttribute('transform', `translate(${jaw.toFixed(1)},0)`);
        target.setAttribute('opacity', this.grip > 0.5 ? String((this.grip - 0.5) * 2) : '0');

        // Move pickup object
        if (this.objEl) {
            this.objEl.setAttribute('transform',
                `translate(${(this.objX - 221).toFixed(1)},${(this.objY - 246).toFixed(1)})`);
        }

        requestAnimationFrame(() => this.tick());
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new MouseArmController());
} else {
    new MouseArmController();
}
