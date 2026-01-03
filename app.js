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

// Magnetic Cursor Effect
class MagneticCursor {
    constructor() {
        // Check if device has mouse (not mobile)
        this.isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

        if (this.isMobile) return;

        this.cursor = document.createElement('div');
        this.cursor.className = 'magnetic-cursor';
        document.body.appendChild(this.cursor);
        document.body.classList.add('magnetic-active');

        this.position = { x: 0, y: 0 };
        this.mouse = { x: 0, y: 0 };

        this.init();
    }

    init() {
        // Track mouse movement
        document.addEventListener('mousemove', (e) => {
            this.mouse.x = e.clientX;
            this.mouse.y = e.clientY;
        });

        // Animate cursor
        this.animate();

        // Add magnetic effect to interactive elements
        const magneticElements = document.querySelectorAll('a, button, .profile-pic, h1, h2');
        magneticElements.forEach(el => {
            el.addEventListener('mouseenter', () => {
                this.cursor.classList.add('hovering');
            });

            el.addEventListener('mouseleave', () => {
                this.cursor.classList.remove('hovering');
            });

            el.addEventListener('mousemove', (e) => {
                const rect = el.getBoundingClientRect();
                const x = e.clientX - rect.left - rect.width / 2;
                const y = e.clientY - rect.top - rect.height / 2;

                // Apply magnetic effect (subtle pull)
                const distance = Math.sqrt(x * x + y * y);
                const maxDistance = 100;

                if (distance < maxDistance) {
                    const force = (maxDistance - distance) / maxDistance;
                    const translateX = x * force * 0.3;
                    const translateY = y * force * 0.3;

                    el.style.transform = `translate(${translateX}px, ${translateY}px)`;
                }
            });

            el.addEventListener('mouseleave', () => {
                el.style.transform = 'translate(0, 0)';
            });
        });
    }

    animate() {
        // Smooth cursor movement
        this.position.x += (this.mouse.x - this.position.x) * 0.15;
        this.position.y += (this.mouse.y - this.position.y) * 0.15;

        this.cursor.style.left = `${this.position.x}px`;
        this.cursor.style.top = `${this.position.y}px`;

        requestAnimationFrame(() => this.animate());
    }
}

// Initialize magnetic cursor
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new MagneticCursor());
} else {
    new MagneticCursor();
}
