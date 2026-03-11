# elitepvpers-sro-pserver MCP

An MCP server that scrapes [elitepvpers.com](https://www.elitepvpers.com/forum/sro-private-server/) to help you find resources for hosting a **Silkroad Online private server** — opcodes, setup guides, source code releases, GM commands, troubleshooting, tools, and more.

## Tools

| Tool | Description |
|------|-------------|
| `list_forums` | List the 6 available subforums |
| `get_popular_threads` | Browse a subforum sorted by views / replies / rating |
| `get_latest_releases` | Newest posts from Guides & Releases (page + RSS) |
| `find_resources` | 27 pre-built topic shortcuts (see below) |
| `search_threads` | Keyword search across any subforum |
| `find_error_fix` | Paste an error message → find Q&A threads about it |
| `browse_by_prefix` | Filter by `[RELEASE]`, `[GUIDE]`, `[TOOL]`, `[DEVKIT]`… |
| `get_thread_op` | Read just the first/original post of a thread |
| `get_thread_content` | Read all posts on a specific page of a thread |
| `get_full_thread` | Fetch every page of a long thread at once |
| `get_thread_stats` | Quick metadata + 500-char preview without full load |
| `get_member_threads` | Find all threads by a specific username |

### `find_resources` topics

`opcodes` · `packets` · `vsro-setup` · `isro-setup` · `source-code` · `emulator` · `database` · `client-setup` · `gm-commands` · `login-server` · `gateway-server` · `game-server` · `tools` · `bot` · `cap` · `silk-system` · `packet-sniffer` · `how-to-host` · `troubleshoot` · `port-forwarding` · `connection-error` · `disconnect` · `login-error` · `shard-files` · `vsro-files` · `release`

---

## Installation

### Option A — Local (Python)

**Requirements:** Python 3.10+

```bash
git clone https://github.com/Alvis1337/elitepvpers-mcp.git
cd elitepvpers-mcp
pip install -r requirements.txt
```

Add to your **Claude Desktop** config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "elitepvpers-sro-pserver": {
      "command": "python",
      "args": ["C:/path/to/elitepvpers-mcp/server.py"]
    }
  }
}
```

> **Windows path:** `C:\\Users\\yourname\\elitepvpers-mcp\\server.py`

---

### Option B — Docker

**Requirements:** Docker Desktop

```bash
git clone https://github.com/Alvis1337/elitepvpers-mcp.git
cd elitepvpers-mcp
docker build -t elitepvpers-mcp .
```

Add to your **Claude Desktop** config:

```json
{
  "mcpServers": {
    "elitepvpers-sro-pserver": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "elitepvpers-mcp"]
    }
  }
}
```

> `-i` keeps stdin open for MCP stdio transport. `--rm` cleans up the container after Claude closes.

---

## Claude Desktop config file location

| OS | Path |
|----|------|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

---

## Example usage

```
find_resources("opcodes")           → opcode/packet threads from SRO Coding Corner
find_resources("vsro-setup")        → vSRO 1.188 server files and setup threads
find_error_fix("access violation")  → Q&A threads about that error
search_threads("gm command", "guides") → guide threads mentioning GM commands
get_thread_op(<url>)                → read the full guide from a thread's first post
get_full_thread(<url>)              → read every reply in a long troubleshooting thread
```
