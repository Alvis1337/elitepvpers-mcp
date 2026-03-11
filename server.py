"""
ElitePvpers SRO Private Server MCP
-----------------------------------
Helps you find resources for hosting a Silkroad Online private server:
opcodes, server setup guides, source code releases, troubleshooting, tools, GM commands, etc.

Available tools:
  list_forums            - List the available subforums
  get_popular_threads    - Browse a subforum sorted by views/replies/rating/date
  get_latest_releases    - Latest posts from the Guides & Releases subforum
  get_thread_op          - Read just the first (original) post of a thread
  get_thread_content     - Read all posts on a page of a thread
  get_full_thread        - Fetch every page of a thread and return all posts
  search_threads         - Full-text or title search across subforums
  find_resources         - Shortcut searches for common pserver topics
  find_error_fix         - Search Q&A for a specific error message
  get_member_threads     - Find threads started by a specific member
  browse_by_prefix       - Browse threads with a specific tag prefix ([RELEASE], [GUIDE], etc.)
  get_thread_stats       - Return basic metadata (title, replies, views) for a thread URL
"""

import re
import time
from typing import Optional
from urllib.parse import urljoin, urlencode

import requests
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("elitepvpers-sro-pserver")

BASE_URL = "https://www.elitepvpers.com/forum/"

FORUMS = {
    "guides":      {"id": 399, "name": "SRO PServer Guides & Releases",    "slug": "sro-pserver-guides-releases"},
    "qa":          {"id": 400, "name": "SRO PServer Questions & Answers",   "slug": "sro-pserver-questions-answers"},
    "main":        {"id": 398, "name": "SRO Private Server (Main)",         "slug": "sro-private-server"},
    "advertising": {"id": 401, "name": "SRO PServer Advertising",           "slug": "sro-pserver-advertising"},
    "coding":      {"id": 632, "name": "SRO Coding Corner",                 "slug": "sro-coding-corner"},
    "hacks":       {"id": 315, "name": "SRO Hacks, Bots, Cheats & Exploits","slug": "sro-hacks-bots-cheats-exploits"},
}

# Pre-defined topic shortcuts → (keywords list, forum key, match_all)
TOPIC_MAP = {
    # Coding & protocol
    "opcodes":         (["opcode"],                    "coding",  False),
    "packets":         (["packet"],                    "coding",  False),
    "source-code":     (["source", "code"],            "guides",  True),
    "emulator":        (["emulator"],                  "coding",  False),
    # Server setup
    "vsro-setup":      (["vsro"],                      "guides",  False),
    "isro-setup":      (["isro"],                      "guides",  False),
    "how-to-host":     (["install", "server"],         "guides",  False),
    "login-server":    (["login", "server"],           "guides",  True),
    "gateway-server":  (["gateway"],                   "guides",  False),
    "game-server":     (["gameserver"],                "guides",  False),
    "database":        (["database"],                  "guides",  False),
    "client-setup":    (["client", "setup"],           "guides",  True),
    "cap":             (["cap"],                       "guides",  False),
    "silk-system":     (["silk"],                      "guides",  False),
    # GM & admin
    "gm-commands":     (["gm"],                        "guides",  False),
    "tools":           (["tool"],                      "guides",  False),
    # Bots & automation
    "bot":             (["bot"],                       "hacks",   False),
    "packet-sniffer":  (["sniffer", "viewer"],         "coding",  False),
    # Troubleshooting
    "troubleshoot":    (["error", "fix"],              "qa",      False),
    "port-forwarding": (["port"],                      "qa",      False),
    "connection-error":(["connection", "error"],       "qa",      False),
    "disconnect":      (["disconnect"],                "qa",      False),
    "login-error":     (["login", "error"],            "qa",      False),
    # Files
    "shard-files":     (["shard"],                     "main",    False),
    "vsro-files":      (["vsro", "files"],             "main",    False),
    "release":         (["release"],                   "guides",  False),
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

_last_request = 0.0


def _get(url: str, params: dict = None) -> BeautifulSoup:
    global _last_request
    elapsed = time.time() - _last_request
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    resp = SESSION.get(url, params=params, timeout=20)
    _last_request = time.time()
    resp.raise_for_status()
    return BeautifulSoup(resp.content, "lxml")


def _parse_number(text: str) -> int:
    text = re.sub(r"[^\d]", "", text.strip())
    return int(text) if text else 0


def _abs_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return urljoin(BASE_URL, href)


def _parse_thread_rows(soup: BeautifulSoup, skip_sticky: bool = False) -> list[dict]:
    """Parse vBulletin thread list rows from a forum page."""
    threads = []
    tbody = soup.find("tbody", id=re.compile(r"^threadbits_forum_"))
    if not tbody:
        return threads

    for row in tbody.find_all("tr", recursive=False):
        title_td = row.find("td", id=re.compile(r"^td_threadtitle_"))
        if not title_td:
            continue

        title_a = title_td.find("a", id=re.compile(r"^thread_title_"))
        if not title_a:
            continue

        title = title_a.get_text(strip=True)
        url = _abs_url(title_a.get("href", ""))

        # Thread starter is in div.smallfont inside title_td
        author = ""
        for div in title_td.find_all("div", class_="smallfont"):
            txt = div.get_text(strip=True)
            if txt:
                author = txt
                break

        # Replies and views are in title attr of last-post td OR the two trailing cells
        replies, views = 0, 0
        lastpost_td = row.find("td", attrs={"title": re.compile(r"Replies:")})
        if lastpost_td:
            m = re.search(r"Replies:\s*([\d,]+),\s*Views:\s*([\d,]+)", lastpost_td.get("title", ""))
            if m:
                replies = _parse_number(m.group(1))
                views = _parse_number(m.group(2))
        else:
            center_tds = row.find_all("td", align="center")
            if len(center_tds) >= 2:
                replies = _parse_number(center_tds[-2].get_text())
                views = _parse_number(center_tds[-1].get_text())

        # Last post info from last-post td
        last_post = ""
        if lastpost_td:
            last_post = lastpost_td.get_text(" ", strip=True)

        # Is sticky?
        status_td = row.find("td", id=re.compile(r"^td_threadstatusicon_"))
        sticky = False
        hot = False
        if status_td:
            img = status_td.find("img")
            if img:
                src = img.get("src", "")
                alt = img.get("alt", "")
                hot = "thread_hot" in src
                sticky = "sticky" in alt.lower() or "sticky" in src.lower()

        if skip_sticky and sticky:
            continue

        threads.append({
            "title":     title,
            "url":       url,
            "author":    author,
            "replies":   replies,
            "views":     views,
            "last_post": last_post,
            "sticky":    sticky,
            "hot":       hot,
        })
    return threads


def _parse_posts(soup: BeautifulSoup) -> list[dict]:
    """Parse posts from a vBulletin showthread page."""
    posts = []
    posts_div = soup.find("div", id="posts")
    if not posts_div:
        # Also try the page-level div
        posts_div = soup

    for post_table in posts_div.find_all("table", id=re.compile(r"^post\d+"), class_="tborder"):
        post_id = post_table.get("id", "").replace("post", "")

        # Date from thead row
        date_span = post_table.find("span", attrs={"itemprop": "datePublished"})
        date = date_span.get_text(strip=True) if date_span else ""

        # Author
        author_a = post_table.find("a", class_="bigusername")
        author = author_a.get_text(strip=True) if author_a else "unknown"

        # Content: the wider td.alt1 (not the sidebar which has width=175)
        content = ""
        content_td = post_table.find("td", class_="alt1", attrs={"width": False})
        if not content_td:
            # Fallback: find alt1 td that doesn't have the sidebar width
            for td in post_table.find_all("td", class_="alt1"):
                if td.get("width") not in ("175",):
                    content_td = td
                    break

        if content_td:
            # Remove quote blocks and signatures to keep content clean
            for el in content_td.find_all("div", class_=re.compile(r"quote|signature")):
                el.decompose()
            # Remove inline images (just keep alt text)
            for img in content_td.find_all("img"):
                alt = img.get("alt", "")
                if alt and not any(x in alt.lower() for x in ["smile", "wink", "tongue", ":)", ";)"]):
                    img.replace_with(f"[img:{alt}]")
                else:
                    img.decompose()
            content = content_td.get_text("\n", strip=True)
            # Collapse excessive blank lines
            content = re.sub(r"\n{3,}", "\n\n", content)

        if content:
            posts.append({
                "post_id": post_id,
                "author":  author,
                "date":    date,
                "content": content[:5000],  # cap per-post to avoid huge responses
            })
    return posts


def _search_forum_pages(
    forum_key: str,
    keywords: list[str],
    sort_by: str = "views",
    num_pages: int = 5,
    limit: int = 25,
    match_all: bool = True,
) -> list[dict]:
    """
    Browse forum pages and filter threads by keywords in their titles.
    match_all=True  → all keywords must appear (AND logic, precise)
    match_all=False → any keyword must appear (OR logic, broader)
    Returns threads sorted by the forum's own sort order (default: most views first).
    """
    if forum_key not in FORUMS:
        return []

    slug = FORUMS[forum_key]["slug"]
    sort_map = {"views": "views", "replies": "replycount", "rating": "voteavg", "lastpost": "lastpost"}
    sort_key = sort_map.get(sort_by, "views")

    kw_lower = [k.lower() for k in keywords if k]
    results = []

    for page in range(1, num_pages + 1):
        index = "" if page == 1 else f"index{page}.html"
        url = f"{BASE_URL}{slug}/{index}"
        try:
            soup = _get(url, {"daysprune": -1, "order": "desc", "sort": sort_key})
        except Exception:
            break

        threads = _parse_thread_rows(soup, skip_sticky=True)
        if not threads:
            break

        for t in threads:
            haystack = t["title"].lower()
            if match_all:
                matched = all(kw in haystack for kw in kw_lower)
            else:
                matched = any(kw in haystack for kw in kw_lower)
            if matched:
                results.append(t)
                if len(results) >= limit:
                    return results

    return results


def _get_thread_page_count(soup: BeautifulSoup) -> int:
    """Return the total number of pages in a thread."""
    pagenav = soup.find("table", class_="tborder", attrs={"cellpadding": "3"})
    if not pagenav:
        return 1
    max_page = 1
    for a in pagenav.find_all("a"):
        try:
            n = int(a.get_text(strip=True))
            if n > max_page:
                max_page = n
        except ValueError:
            pass
    return max_page


def _thread_page_url(base_url: str, page: int) -> str:
    """Build the URL for a specific page of a vBulletin thread."""
    if page <= 1:
        return base_url
    # vBulletin pattern: thread-name.html → thread-name-2.html
    if base_url.endswith(".html"):
        # Strip existing page number if present
        base_url = re.sub(r"-(\d+)\.html$", ".html", base_url)
        return base_url[:-5] + f"-{page}.html"
    return base_url


# ─────────────────────────────────────────────────────────────
# TOOL: list_forums
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def list_forums() -> list[dict]:
    """
    List all available SRO private server subforums with descriptions.
    Use this to understand what forum key to pass to other tools.
    """
    return [
        {
            "key":         "guides",
            "name":        "SRO PServer Guides & Releases",
            "url":         f"{BASE_URL}sro-pserver-guides-releases/",
            "description": "Source code releases, tool releases, setup guides, bots, patches. Best starting point.",
        },
        {
            "key":         "qa",
            "name":        "SRO PServer Questions & Answers",
            "url":         f"{BASE_URL}sro-pserver-questions-answers/",
            "description": "Error fixes, troubleshooting, how-to questions.",
        },
        {
            "key":         "coding",
            "name":        "SRO Coding Corner",
            "url":         f"{BASE_URL}sro-coding-corner/",
            "description": "Opcode lists, packet structures, emulators, protocol docs. Essential for development.",
        },
        {
            "key":         "hacks",
            "name":        "SRO Hacks, Bots, Cheats & Exploits",
            "url":         f"{BASE_URL}sro-hacks-bots-cheats-exploits/",
            "description": "Bots, macros, automation tools for Silkroad Online.",
        },
        {
            "key":         "main",
            "name":        "SRO Private Server (Main Discussions)",
            "url":         f"{BASE_URL}sro-private-server/",
            "description": "General discussions, team recruitment, server file links.",
        },
        {
            "key":         "advertising",
            "name":        "SRO PServer Advertising",
            "url":         f"{BASE_URL}sro-pserver-advertising/",
            "description": "Live server advertisements — useful for seeing cap configs others run.",
        },
    ]


# ─────────────────────────────────────────────────────────────
# TOOL: get_popular_threads
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_popular_threads(
    forum: str = "guides",
    sort_by: str = "views",
    limit: int = 25,
    page: int = 1,
    skip_sticky: bool = True,
) -> list[dict]:
    """
    Browse a subforum and return threads sorted by popularity.

    Args:
        forum:        Which subforum: "guides", "qa", "main", or "advertising"
        sort_by:      Ranking method: "views" (most viewed), "replies" (most discussed),
                      "rating" (highest rated), "lastpost" (most recently active)
        limit:        Max threads to return (1–50)
        page:         Page of the forum listing (25 threads per page)
        skip_sticky:  Skip pinned/sticky threads (default True to focus on actual content)

    Returns:
        List of thread dicts with title, url, author, replies, views, last_post, hot.

    Example:
        get_popular_threads("guides", "views", 20)   → top 20 most-viewed guide threads
        get_popular_threads("qa", "replies", 15)     → top 15 most-discussed Q&A threads
    """
    forum = forum.lower()
    if forum not in FORUMS:
        return [{"error": f"Unknown forum '{forum}'. Use: {list(FORUMS.keys())}"}]

    sort_map = {"views": "views", "replies": "replycount", "rating": "voteavg", "lastpost": "lastpost"}
    sort_key = sort_map.get(sort_by.lower(), "views")
    slug = FORUMS[forum]["slug"]
    index = "" if page == 1 else f"index{page}.html"
    url = f"{BASE_URL}{slug}/{index}"

    soup = _get(url, {"daysprune": -1, "order": "desc", "sort": sort_key})
    threads = _parse_thread_rows(soup, skip_sticky=skip_sticky)

    if not threads:
        return [{"error": "No threads found. The site may be blocking requests or the page structure changed."}]

    return threads[:max(1, min(limit, 50))]


# ─────────────────────────────────────────────────────────────
# TOOL: get_latest_releases
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_latest_releases(limit: int = 20) -> list[dict]:
    """
    Get the most recently posted threads from the Guides & Releases forum.
    Useful for finding the newest tools, source code drops, and patches.
    Also checks the RSS feed for even fresher items.

    Args:
        limit: Number of results (1–50)

    Returns:
        List of the latest threads with title, url, author, replies, views, last_post.
    """
    results = []
    seen = set()

    # RSS feed for quick recent items
    try:
        resp = SESSION.get(f"{BASE_URL}external.php", params={"type": "RSS2", "forumids": "399"}, timeout=15)
        rss = BeautifulSoup(resp.content, "xml")
        for item in rss.find_all("item"):
            title_tag = item.find("title")
            link_tag  = item.find("link")
            author_tag = item.find("author") or item.find("dc:creator")
            if title_tag and link_tag:
                url = link_tag.get_text(strip=True)
                if url not in seen:
                    seen.add(url)
                    results.append({
                        "title":     title_tag.get_text(strip=True),
                        "url":       url,
                        "author":    author_tag.get_text(strip=True) if author_tag else "",
                        "replies":   0,
                        "views":     0,
                        "last_post": "",
                        "source":    "rss",
                    })
    except Exception:
        pass

    # Also grab the forum page sorted by last post
    slug = FORUMS["guides"]["slug"]
    try:
        soup = _get(f"{BASE_URL}{slug}/", {"daysprune": -1, "order": "desc", "sort": "lastpost"})
        for t in _parse_thread_rows(soup, skip_sticky=True):
            if t["url"] not in seen:
                seen.add(t["url"])
                t["source"] = "forum"
                results.append(t)
    except Exception:
        pass

    return results[:max(1, min(limit, 50))]


# ─────────────────────────────────────────────────────────────
# TOOL: get_thread_op
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_thread_op(url: str) -> dict:
    """
    Read only the first (original) post of a thread.
    Perfect for reading guides, release announcements, or tutorials quickly
    without loading replies.

    Args:
        url: Full thread URL (e.g. from get_popular_threads or search_threads)

    Returns:
        Dict with: title, url, author, date, content (the full OP text)
    """
    soup = _get(url)

    title_tag = soup.find("h1", attrs={"itemprop": "headline"})
    if not title_tag:
        title_tag = soup.find("div", class_="cwhead")
    title = title_tag.get_text(strip=True) if title_tag else "Unknown"

    total_pages = _get_thread_page_count(soup)
    posts = _parse_posts(soup)

    if not posts:
        return {"error": "Could not parse posts. Thread may require login.", "url": url}

    op = posts[0]
    return {
        "title":       title,
        "url":         url,
        "total_pages": total_pages,
        "author":      op["author"],
        "date":        op["date"],
        "content":     op["content"],
    }


# ─────────────────────────────────────────────────────────────
# TOOL: get_thread_content
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_thread_content(url: str, page: int = 1) -> dict:
    """
    Read all posts on a specific page of a thread.
    Use this for reading replies and discussions, not just the guide/OP.

    Args:
        url:  Full thread URL
        page: Page number within the thread (default 1)

    Returns:
        Dict with title, url, page, total_pages, and a list of posts
        (each post has: post_id, author, date, content)
    """
    page_url = _thread_page_url(url, page)
    soup = _get(page_url)

    title_tag = soup.find("h1", attrs={"itemprop": "headline"})
    if not title_tag:
        title_tag = soup.find("div", class_="cwhead")
    title = title_tag.get_text(strip=True) if title_tag else "Unknown"

    total_pages = _get_thread_page_count(soup)
    posts = _parse_posts(soup)

    return {
        "title":       title,
        "url":         page_url,
        "page":        page,
        "total_pages": total_pages,
        "post_count":  len(posts),
        "posts":       posts,
    }


# ─────────────────────────────────────────────────────────────
# TOOL: get_full_thread
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_full_thread(url: str, max_pages: int = 10) -> dict:
    """
    Fetch ALL pages of a thread and return every post concatenated.
    Best for reading long guides or troubleshooting threads end-to-end.
    WARNING: Can be slow for very long threads — use max_pages to limit.

    Args:
        url:       Full thread URL
        max_pages: Maximum pages to fetch (default 10, max 30).
                   Increase for very long threads.

    Returns:
        Dict with title, url, total_pages, pages_fetched, and all_posts (list)
    """
    max_pages = min(max_pages, 30)
    soup = _get(url)

    title_tag = soup.find("h1", attrs={"itemprop": "headline"})
    if not title_tag:
        title_tag = soup.find("div", class_="cwhead")
    title = title_tag.get_text(strip=True) if title_tag else "Unknown"

    total_pages = _get_thread_page_count(soup)
    all_posts = _parse_posts(soup)
    pages_fetched = 1

    for p in range(2, min(total_pages + 1, max_pages + 1)):
        page_url = _thread_page_url(url, p)
        try:
            psoup = _get(page_url)
            all_posts.extend(_parse_posts(psoup))
            pages_fetched += 1
        except Exception as e:
            all_posts.append({"error": f"Failed to fetch page {p}: {e}"})
            break

    return {
        "title":         title,
        "url":           url,
        "total_pages":   total_pages,
        "pages_fetched": pages_fetched,
        "post_count":    len(all_posts),
        "all_posts":     all_posts,
    }


# ─────────────────────────────────────────────────────────────
# TOOL: search_threads
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def search_threads(
    query: str,
    forum: str = "all",
    sort_by: str = "views",
    limit: int = 20,
    num_pages: int = 8,
) -> list[dict]:
    """
    Search SRO private server subforums by keyword — browses the most popular threads
    and returns those whose titles contain your search terms.

    Args:
        query:     Search keywords. Space-separated — ALL words must appear in the title.
                   Examples: "opcode", "vsro setup", "login server", "gm commands",
                             "source code release", "client patch", "gateway error"
        forum:     Which subforum: "guides", "qa", "main", "advertising", or "all"
                   "all" searches guides + qa + main together.
        sort_by:   How to rank results: "views" (most popular first, default),
                   "replies" (most discussed), "lastpost" (most recent)
        limit:     Max results to return (1–50)
        num_pages: Pages of the forum to scan per subforum (default 8, max 20).
                   Increase to search deeper into older threads.

    Returns:
        List of matching thread dicts with title, url, author, replies, views.

    Tips:
        - Use short, specific keywords: "vsro 188" instead of "how do I set up vsro 188"
        - Try different keywords if no results: "opcode" vs "packet" vs "opcodes"
        - Use forum="guides" to only search the guides & releases section
    """
    forum = forum.lower()
    num_pages = min(num_pages, 20)
    keywords = [w for w in query.strip().split() if len(w) > 1]

    if not keywords:
        return [{"error": "Please provide at least one keyword."}]

    if forum == "all":
        forum_keys = ["guides", "qa", "main"]
    elif forum in FORUMS:
        forum_keys = [forum]
    else:
        return [{"error": f"Unknown forum '{forum}'. Use: all, {list(FORUMS.keys())}"}]

    results = []
    seen_urls = set()
    per_forum_limit = max(limit, 10)

    for fk in forum_keys:
        matches = _search_forum_pages(fk, keywords, sort_by=sort_by,
                                       num_pages=num_pages, limit=per_forum_limit)
        for t in matches:
            if t["url"] not in seen_urls:
                seen_urls.add(t["url"])
                t["forum"] = fk
                results.append(t)

    if not results:
        return [{
            "note": f"No threads found matching '{query}' in forum '{forum}'.",
            "suggestions": [
                "Try shorter keywords (e.g. 'opcode' instead of 'opcode list')",
                "Try a different forum (guides, qa, main)",
                "Increase num_pages to search more threads",
                "Use find_resources() for common topics",
            ]
        }]

    # Sort combined results by views (most popular first)
    results.sort(key=lambda x: x.get("views", 0), reverse=True)
    return results[:max(1, min(limit, 50))]


# ─────────────────────────────────────────────────────────────
# TOOL: find_resources
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def find_resources(topic: str) -> list[dict]:
    """
    Find resources for common SRO private server topics using pre-built keyword shortcuts.
    Much easier than writing your own search query for well-known topics.

    Args:
        topic: One of the predefined topic keys. Available topics:
               "opcodes"          - Opcode lists and packet documentation
               "vsro-setup"       - vSRO 1.188 server setup guides
               "isro-setup"       - iSRO R server setup guides
               "source-code"      - Server source code releases
               "database"         - Database setup (SQL, MySQL, mssql)
               "client-setup"     - Client patching and setup
               "gm-commands"      - GM / admin command lists
               "login-server"     - Login server configuration
               "gateway-server"   - Gateway server setup
               "game-server"      - Game server setup
               "tools"            - Admin tools, managers, editors
               "bot"              - Bot / macro / AutoAlchemy scripts
               "cap"              - Level cap increase guides
               "silk-system"      - Silk / donation system setup
               "packet-sniffer"   - Packet sniffing tools
               "how-to-host"      - General how-to-host guides
               "troubleshoot"     - General error troubleshooting
               "port-forwarding"  - Port forwarding / networking setup
               "connection-error" - Connection refused / failed errors
               "disconnect"       - Player disconnect / crash issues
               "shard-files"      - Server shard file downloads
               "vsro-files"       - vSRO server files

    Returns:
        List of threads relevant to that topic, sorted by most viewed.
    """
    topic = topic.lower().strip()
    if topic not in TOPIC_MAP:
        available = ", ".join(sorted(TOPIC_MAP.keys()))
        return [{"error": f"Unknown topic '{topic}'", "available_topics": available}]

    keywords, forum, match_all = TOPIC_MAP[topic]
    forum_keys = ["guides", "qa", "main"] if forum == "all" else [forum]

    results = []
    seen = set()
    for fk in forum_keys:
        for t in _search_forum_pages(fk, keywords, sort_by="views", num_pages=10, limit=25, match_all=match_all):
            if t["url"] not in seen:
                seen.add(t["url"])
                t["forum"] = fk
                results.append(t)

    results.sort(key=lambda x: x.get("views", 0), reverse=True)

    if not results:
        return [{"note": f"No threads found for topic '{topic}'. Try search_threads() with custom keywords."}]

    return results[:25]


# ─────────────────────────────────────────────────────────────
# TOOL: find_error_fix
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def find_error_fix(error_message: str) -> list[dict]:
    """
    Search the Q&A subforum for threads that discuss a specific error message or problem.
    Paste in the error text, code, or a short description to find matching threads.

    Args:
        error_message: The error or problem you're encountering.
                       Examples: "access violation", "cannot connect to server",
                                 "table not found", "failed to initialize",
                                 "port 15779", "login failed", "character select crash"

    Returns:
        List of Q&A threads that mention this error, sorted by most viewed (most helpful first).
    """
    keywords = [w for w in error_message.lower().split() if len(w) > 2][:4]
    if not keywords:
        return [{"error": "Please provide a more specific error message."}]

    results = _search_forum_pages("qa", keywords, sort_by="views", num_pages=10, limit=20, match_all=False)

    if not results:
        results = _search_forum_pages("main", keywords, sort_by="views", num_pages=6, limit=10, match_all=False)

    if not results:
        return [{
            "note": f"No Q&A threads found matching '{error_message}'.",
            "suggestions": [
                "Try shorter keywords (1-2 key words from the error)",
                "Check the main forum too: get_popular_threads('main', 'replies')",
                "Search guides for known bug fixes: search_threads('fix', 'guides')",
            ]
        }]

    return results


# ─────────────────────────────────────────────────────────────
# TOOL: get_member_threads
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_member_threads(
    username: str,
    forum: str = "all",
    limit: int = 20,
) -> list[dict]:
    """
    Find threads started by a specific member — useful when you find a knowledgeable
    developer and want to see all their releases, guides, and contributions.

    Args:
        username: The elitepvpers username to find threads for.
                  Note: matching is case-insensitive but must be an exact username.
        forum:    Limit to "all", "guides", "qa", "main", or "advertising"
        limit:    Max results (1–50)

    Returns:
        List of threads by that member.
    """
    forum = forum.lower()
    forum_keys = ["guides", "qa", "main"] if forum == "all" else ([forum] if forum in FORUMS else None)
    if forum_keys is None:
        return [{"error": f"Unknown forum '{forum}'. Use: all, {list(FORUMS.keys())}"}]

    uname_lower = username.lower()
    results = []
    seen = set()

    for fk in forum_keys:
        # Scan forum pages looking for threads authored by this user
        slug = FORUMS[fk]["slug"]
        for page in range(1, 15):  # Check up to 14 pages
            index = "" if page == 1 else f"index{page}.html"
            try:
                soup = _get(f"{BASE_URL}{slug}/{index}", {"daysprune": -1, "order": "desc", "sort": "lastpost"})
            except Exception:
                break
            threads = _parse_thread_rows(soup, skip_sticky=False)
            if not threads:
                break
            for t in threads:
                if t["author"].lower() == uname_lower and t["url"] not in seen:
                    seen.add(t["url"])
                    t["forum"] = fk
                    results.append(t)
                    if len(results) >= limit:
                        return results

    if not results:
        return [{"note": f"No threads found for user '{username}'. Check exact spelling (try different capitalisation)."}]

    return results[:max(1, min(limit, 50))]


# ─────────────────────────────────────────────────────────────
# TOOL: browse_by_prefix
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def browse_by_prefix(
    prefix: str = "RELEASE",
    forum: str = "guides",
    sort_by: str = "views",
    limit: int = 20,
) -> list[dict]:
    """
    Find threads with a specific title prefix/tag like [RELEASE], [GUIDE], [TOOL], etc.
    Thread authors commonly tag their posts, so this is a great way to filter by type.

    Args:
        prefix:  The tag to look for — without brackets. Common values:
                 "RELEASE"   - released tools, files, or source code
                 "GUIDE"     - step-by-step tutorials
                 "TOOL"      - utilities and editors
                 "REQUEST"   - requests for help or files
                 "UPDATE"    - updates to existing releases
                 "DEVKIT"    - development kit releases
                 "FIX"       - bug fix releases
        forum:   Which subforum to search: "guides", "qa", "main", "advertising"
        sort_by: "views", "replies", "rating", or "lastpost"
        limit:   Max results (1–50)

    Returns:
        List of matching thread dicts.
    """
    forum = forum.lower()
    if forum not in FORUMS:
        return [{"error": f"Unknown forum '{forum}'. Use: {list(FORUMS.keys())}"}]

    tag = f"[{prefix.upper()}]"
    keywords = [prefix.lower()]
    results = _search_forum_pages(forum, keywords, sort_by=sort_by, num_pages=10, limit=limit)
    # Further filter to only those that contain the bracketed prefix
    results = [t for t in results if tag.lower() in t["title"].lower() or prefix.lower() in t["title"].lower()]
    return results[:max(1, min(limit, 50))]


# ─────────────────────────────────────────────────────────────
# TOOL: get_thread_stats
# ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_thread_stats(url: str) -> dict:
    """
    Get quick metadata for a thread without reading all the posts.
    Returns title, total pages, reply count, views, and the first sentence of the OP.

    Args:
        url: Full thread URL

    Returns:
        Dict with title, url, total_pages, author, date, preview (first 500 chars of OP)
    """
    soup = _get(url)

    title_tag = soup.find("h1", attrs={"itemprop": "headline"})
    if not title_tag:
        title_tag = soup.find("div", class_="cwhead")
    title = title_tag.get_text(strip=True) if title_tag else "Unknown"

    total_pages = _get_thread_page_count(soup)
    posts = _parse_posts(soup)

    if not posts:
        return {"error": "Could not parse thread.", "url": url}

    op = posts[0]
    return {
        "title":       title,
        "url":         url,
        "total_pages": total_pages,
        "total_posts_on_page1": len(posts),
        "author":      op["author"],
        "date":        op["date"],
        "preview":     op["content"][:500],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
