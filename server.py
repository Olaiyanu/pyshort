import http.server
import socketserver
import sqlite3
import urllib.parse
import urllib.request
import string
import datetime
import logging
import os

# --- CONFIGURATION ---
PORT = 5000
DB_NAME = "urls.db"

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# --- HTML TEMPLATES ---

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyShort - Public URL Shortener</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        body {{ font-family: 'Inter', sans-serif; }}
        .animate-fade-in {{ animation: fadeIn 0.5s ease-out; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    </style>
</head>
<body class="bg-slate-900 text-white min-h-screen flex flex-col">
    <!-- Navbar -->
    <nav class="bg-slate-800 border-b border-slate-700 px-6 py-4 flex justify-between items-center shadow-md">
        <a href="/" class="font-bold text-xl text-blue-400 hover:text-blue-300 transition">FastLinkr</a>
        <div class="text-sm text-slate-400">
            Free Public Shortener By Johnson
        </div>
    </nav>

    <!-- Content -->
    <main class="flex-grow flex flex-col items-center justify-center p-4">
        {content}
    </main>

    <footer class="p-4 text-center text-slate-600 text-xs">
        Data stored locally in {db_name}
    </footer>
</body>
</html>
"""

HOME_TEMPLATE = """
<div class="w-full max-w-4xl space-y-8 animate-fade-in">
    
    <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-white mb-2">Shorten Your Links</h1>
        <p class="text-slate-400">Enter a long URL below to create a short, shareable link.</p>
    </div>

    <!-- Shortener Form -->
    <div class="bg-slate-800 p-8 rounded-xl border border-slate-700 shadow-2xl">
        <form method="POST" action="/shorten" class="flex flex-col gap-4">
            <input type="url" name="url" required placeholder="Paste long URL here (https://...)" 
                class="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none transition text-lg">
            
            <div class="flex flex-col sm:flex-row gap-4">
                <input type="text" name="custom_code" placeholder="Custom Alias (Optional)" pattern="[a-zA-Z0-9-_]+"
                    class="flex-1 px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none transition">
                <input type="date" name="expires_at" title="Expiration Date"
                    class="sm:w-40 px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-400 transition">
                <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-3 rounded-lg transition shadow-lg text-lg">
                    Shorten
                </button>
            </div>
        </form>
        {result_section}
    </div>

    <!-- Global Stats Table -->
    <div class="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden shadow-lg mt-8">
        <div class="p-4 bg-slate-750 border-b border-slate-700 flex justify-between items-center bg-slate-800/50">
            <h3 class="font-bold text-slate-200">Recent Public Links</h3>
            <div class="flex items-center gap-3">
                <span class="text-xs text-slate-500 bg-slate-900 px-3 py-1 rounded border border-slate-700">Displaying last 10</span>
                <form method="POST" action="/clear_all" onsubmit="return confirm('Are you sure you want to delete ALL links?');">
                    <button type="submit" class="text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 px-3 py-1 rounded border border-red-900/50 transition font-bold">Clear All</button>
                </form>
            </div>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-left text-sm text-slate-400">
                <thead class="bg-slate-700 text-slate-200 uppercase font-medium">
                    <tr>
                        <th class="px-6 py-3">Short Link</th>
                        <th class="px-6 py-3">Original Link</th>
                        <th class="px-6 py-3">Clicks</th>
                        <th class="px-6 py-3">Created</th>
                        <th class="px-6 py-3 text-center">QR Code</th>
                        <th class="px-6 py-3 text-right">Action</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-700">
                    {table_rows}
                </tbody>
            </table>
        </div>
    </div>
</div>
"""

RESULT_FRAGMENT = """
<div class="mt-8 p-6 bg-slate-750 border border-green-500/30 rounded-xl flex flex-col md:flex-row gap-6 animate-fade-in relative overflow-hidden">
    <!-- Success Badge -->
    <div class="absolute top-0 right-0 bg-green-500 text-xs font-bold px-3 py-1 rounded-bl-lg text-slate-900 uppercase tracking-wider">
        Success
    </div>

    <!-- QR Code Preview -->
    <div class="bg-white p-3 rounded-lg shrink-0 flex flex-col items-center justify-center shadow-lg">
        <img src="{qr_url}" alt="QR Code" class="w-32 h-32">
        <!-- Direct Backend Download Link -->
        <a href="/download_qr?code={code}" class="mt-2 text-xs bg-slate-100 hover:bg-slate-200 text-slate-800 py-1 px-3 rounded font-bold border border-slate-300 w-full transition flex items-center justify-center gap-1 no-underline">
            <span>⬇</span> Save Image
        </a>
    </div>

    <div class="flex-grow w-full flex flex-col justify-center text-center md:text-left">
         <p class="text-slate-400 text-sm mb-1">Your short link is ready:</p>
         <div class="bg-slate-900/80 p-4 rounded-lg border border-slate-600 mb-4 flex items-center justify-between gap-4 group">
            <span class="text-blue-400 font-mono text-xl truncate select-all">{short_url}</span>
            <button onclick="navigator.clipboard.writeText('{short_url}'); alert('Copied!');" class="text-slate-500 hover:text-white transition" title="Copy">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
            </button>
         </div>
         
         <div class="flex flex-wrap gap-3 justify-center md:justify-start">
            <a href="{short_url}" target="_blank" class="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg font-bold transition shadow-lg shadow-blue-600/20">
                Visit Link
            </a>
            <a href="/download_qr?code={code}" class="bg-slate-700 hover:bg-slate-600 text-white px-6 py-2 rounded-lg font-bold transition border border-slate-600">
                Download QR Code
            </a>
         </div>
    </div>
</div>
"""

ERROR_FRAGMENT = """
<div class="mt-6 p-4 bg-red-900/30 border border-red-500/30 rounded-lg text-red-200 text-center animate-fade-in flex flex-col items-center">
    <div class="text-3xl mb-2">⚠️</div>
    <div class="font-bold">Something went wrong</div>
    <div class="text-sm opacity-80">{msg}</div>
</div>
"""

# --- DATABASE LOGIC ---

def init_db():
    """Initializes the SQLite database file."""
    db_exists = os.path.exists(DB_NAME)
    
    with sqlite3.connect(DB_NAME) as conn:
        # Links Table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                clicks INTEGER DEFAULT 0
            )
        ''')
    
    if not db_exists:
        print(f"[{datetime.datetime.now()}] Database file '{DB_NAME}' created successfully.")

class Base62:
    CHARACTERS = string.digits + string.ascii_letters
    BASE = len(CHARACTERS)

    @staticmethod
    def encode(num):
        if num == 0: return Base62.CHARACTERS[0]
        arr = []
        while num:
            num, rem = divmod(num, Base62.BASE)
            arr.append(Base62.CHARACTERS[rem])
        arr.reverse()
        return ''.join(arr)

# --- APP HANDLER ---

class AppHandler(http.server.BaseHTTPRequestHandler):
    
    def get_domain(self):
        host = self.headers.get('Host') or f"localhost:{PORT}"
        return f"http://{host}/"

    def send_page(self, title, content):
        html = BASE_TEMPLATE.format(content=content, db_name=DB_NAME)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    # --- ROUTING ---

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self.render_home()
        elif path == "/favicon.ico":
            self.send_error(404)
        elif path == "/download_qr":
            code = query.get('code', [None])[0]
            if code:
                self.handle_qr_download(code)
            else:
                self.send_error(400, "Missing code")
        else:
            # Handle Redirects
            code = path.lstrip("/")
            self.handle_redirect(code)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(length).decode('utf-8')
        params = urllib.parse.parse_qs(data)
        path = self.path
        
        if path == "/shorten":
            url = params.get('url', [''])[0]
            custom_code = params.get('custom_code', [''])[0].strip()
            expires_at = params.get('expires_at', [''])[0]
            self.handle_shorten(url, custom_code, expires_at)
        
        elif path == "/delete":
            code = params.get('code', [''])[0]
            if code:
                self.handle_delete(code)
            else:
                self.send_error(400, "Missing code to delete")
                
        elif path == "/clear_all":
            self.handle_clear_all()

    # --- LOGIC ---

    def handle_qr_download(self, code):
        """Fetches QR code from external API and streams it to client to force download."""
        try:
            # Reconstruct the full short URL
            short_url = self.get_domain() + code
            # Construct QR API URL
            qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={short_url}"
            
            with urllib.request.urlopen(qr_api_url) as response:
                if response.status == 200:
                    data = response.read()
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Disposition", f'attachment; filename="qrcode_{code}.png"')
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self.send_error(502, "Failed to generate QR code")
        except Exception as e:
            self.send_error(500, f"Error downloading QR: {str(e)}")

    def handle_delete(self, code):
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM links WHERE short_code = ?", (code,))
            self.render_home()
        except Exception as e:
            self.render_home(error=ERROR_FRAGMENT.format(msg=f"Delete failed: {str(e)}"))

    def handle_clear_all(self):
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM links")
            self.render_home()
        except Exception as e:
            self.render_home(error=ERROR_FRAGMENT.format(msg=f"Clear failed: {str(e)}"))

    def handle_shorten(self, url, custom_code, expires_at):
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        try:
            with sqlite3.connect(DB_NAME) as conn:
                cur = conn.cursor()
                final_code = ""
                
                if custom_code:
                    cur.execute("SELECT id FROM links WHERE short_code = ?", (custom_code,))
                    if cur.fetchone():
                        raise ValueError("Alias already taken")
                    final_code = custom_code
                    cur.execute("INSERT INTO links (short_code, original_url, expires_at) VALUES (?, ?, ?)",
                               (final_code, url, expires_at))
                else:
                    cur.execute("INSERT INTO links (short_code, original_url, expires_at) VALUES (?, ?, ?)", 
                               ("TEMP", url, expires_at))
                    lid = cur.lastrowid
                    final_code = Base62.encode(lid + 1000)
                    cur.execute("UPDATE links SET short_code = ? WHERE id = ?", (final_code, lid))
                
                short_url = self.get_domain() + final_code
                qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={short_url}"
                
                self.render_home(result=RESULT_FRAGMENT.format(short_url=short_url, qr_url=qr_url, code=final_code))

        except ValueError as e:
            self.render_home(error=ERROR_FRAGMENT.format(msg=str(e)))

    def render_home(self, result="", error=""):
        # Fetch last 10 links for the public feed
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM links ORDER BY created_at DESC LIMIT 10").fetchall()

        table_rows = ""
        for row in rows:
            s_url = self.get_domain() + row['short_code']
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={s_url}"
            expiry = row['expires_at'] if row['expires_at'] else "-"
            
            table_rows += f"""
            <tr class="hover:bg-slate-750 border-b border-slate-700/50 transition group">
                <td class="px-6 py-4 font-mono text-blue-400 font-bold"><a href="{s_url}" target="_blank" class="hover:underline">{row['short_code']}</a></td>
                <td class="px-6 py-4 truncate max-w-xs text-slate-500" title="{row['original_url']}">{row['original_url']}</td>
                <td class="px-6 py-4 font-bold text-green-400">{row['clicks']}</td>
                <td class="px-6 py-4 text-xs text-slate-500">{row['created_at'][:10]}</td>
                <td class="px-6 py-2 text-center">
                    <div class="flex flex-col items-center gap-1">
                        <img src="{qr_url}" class="w-10 h-10 rounded border border-white/10 bg-white p-1">
                        <a href="/download_qr?code={row['short_code']}" class="text-[10px] text-blue-400 hover:text-blue-300 uppercase font-bold tracking-wide">Download</a>
                    </div>
                </td>
                <td class="px-6 py-4 text-right">
                    <form method="POST" action="/delete" onsubmit="return confirm('Delete this link?');">
                        <input type="hidden" name="code" value="{row['short_code']}">
                        <button type="submit" class="text-slate-500 hover:text-red-400 transition p-2" title="Delete Link">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                        </button>
                    </form>
                </td>
            </tr>
            """
        
        content = HOME_TEMPLATE.format(
            result_section=result if result else error, 
            table_rows=table_rows
        )
        self.send_page("Home", content)

    def handle_redirect(self, code):
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT original_url, expires_at FROM links WHERE short_code = ?", (code,))
            row = cur.fetchone()
            
            if row:
                if row['expires_at']:
                    expire_dt = datetime.datetime.strptime(row['expires_at'], '%Y-%m-%d')
                    if datetime.datetime.now() > expire_dt + datetime.timedelta(days=1):
                        self.send_error(410, "Link Expired")
                        return

                cur.execute("UPDATE links SET clicks = clicks + 1 WHERE short_code = ?", (code,))
                
                self.send_response(302)
                self.send_header('Location', row['original_url'])
                self.end_headers()
            else:
                self.send_error(404, "Link Not Found")

if __name__ == "__main__":
    init_db()
    server_address = ('', PORT)
    httpd = socketserver.TCPServer(server_address, AppHandler)
    print(f"Server running on port {PORT}")
    print(f"Database file: {os.path.abspath(DB_NAME)}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()