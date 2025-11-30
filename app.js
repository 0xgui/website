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
