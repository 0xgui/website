// Cloudflare Worker to proxy Substack RSS feed
// Deploy this to Cloudflare Workers and point your app.js to the worker URL

export default {
  async fetch(request, env, ctx) {
    // Only allow GET requests
    if (request.method !== 'GET') {
      return new Response('Method not allowed', { status: 405 });
    }

    const SUBSTACK_RSS_URL = 'https://binarypaths.substack.com/feed';
    const CACHE_TTL = 3600; // Cache for 1 hour

    try {
      // Check cache first
      const cache = caches.default;
      let response = await cache.match(request);

      if (!response) {
        // Fetch RSS feed from Substack
        const rssResponse = await fetch(SUBSTACK_RSS_URL);

        if (!rssResponse.ok) {
          throw new Error(`Failed to fetch RSS: ${rssResponse.status}`);
        }

        const rssText = await rssResponse.text();

        // Simple regex-based XML parsing (works for standard RSS feeds)
        const itemRegex = /<item>([\s\S]*?)<\/item>/g;
        const titleRegex = /<title><!\[CDATA\[(.*?)\]\]><\/title>/;
        const linkRegex = /<link>(.*?)<\/link>/;
        const pubDateRegex = /<pubDate>(.*?)<\/pubDate>/;
        const descriptionRegex = /<description><!\[CDATA\[([\s\S]*?)\]\]><\/description>/;

        const items = [];
        let match;

        while ((match = itemRegex.exec(rssText)) !== null && items.length < 5) {
          const itemContent = match[1];

          const titleMatch = itemContent.match(titleRegex);
          const linkMatch = itemContent.match(linkRegex);
          const pubDateMatch = itemContent.match(pubDateRegex);
          const descriptionMatch = itemContent.match(descriptionRegex);

          items.push({
            title: titleMatch ? titleMatch[1] : '',
            link: linkMatch ? linkMatch[1].trim() : '',
            pubDate: pubDateMatch ? pubDateMatch[1] : '',
            description: descriptionMatch ? descriptionMatch[1] : ''
          });
        }

        // Create JSON response
        response = new Response(JSON.stringify({ items }), {
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': `public, max-age=${CACHE_TTL}`,
          },
        });

        // Store in cache
        ctx.waitUntil(cache.put(request, response.clone()));
      }

      return response;
    } catch (error) {
      return new Response(
        JSON.stringify({ error: 'Failed to fetch RSS feed', details: error.message }),
        {
          status: 500,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
          }
        }
      );
    }
  },
};
