#!/usr/bin/env python3
"""
ARC-Bench Hackathon Agent - 使用固定模板 + LLM 生成代码
"""
import os
import sys
import json
import re
import subprocess
from pathlib import Path

def main():
    print(f"[Agent] Starting...")
    print(f"[Agent] Args: {sys.argv}")
    
    if len(sys.argv) < 3:
        print("Usage: main.py <requirements_source> --output-dir <output_dir>")
        sys.exit(1)
    
    requirements_source = sys.argv[1]
    output_dir = None
    for i, arg in enumerate(sys.argv):
        if arg == '--output-dir' and i + 1 < len(sys.argv):
            output_dir = sys.argv[i + 1]
            break
    
    if not output_dir:
        print("Error: --output-dir is required")
        sys.exit(1)
    
    print(f"[Agent] Requirements: {requirements_source}")
    print(f"[Agent] Output: {output_dir}")
    
    # 读取需求文件
    req_file = find_requirements(requirements_source)
    if not req_file:
        print("[Agent] ERROR: No requirements.yaml found")
        sys.exit(1)
    
    print(f"[Agent] Found: {req_file}")
    
    with open(req_file, 'r', encoding='utf-8') as f:
        requirements_content = f.read()
    
    # 检测任务类型
    task_type = detect_task_type(requirements_content)
    print(f"[Agent] Task type: {task_type}")
    
    # 提取种子数据
    seed_data = extract_seed_data(requirements_content)
    print(f"[Agent] Seed data: {list(seed_data.keys())}")
    
    # 获取 LLM 配置
    api_key = os.environ.get('OPENAI_API_KEY', '')
    base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.arc-bench.com/v1')
    model = os.environ.get('MODEL', 'deepseek-v4-flash')
    
    print(f"[Agent] API Key: {'set' if api_key else 'not set'}")
    print(f"[Agent] Base URL: {base_url}")
    print(f"[Agent] Model: {model}")
    
    # 创建输出目录
    output_path = Path(output_dir)
    backend_dir = output_path / 'backend'
    frontend_dir = output_path / 'frontend'
    backend_dir.mkdir(parents=True, exist_ok=True)
    frontend_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 生成固定的、有效的 package.json
    print(f"[Agent] Creating fixed package.json files...")
    create_fixed_package_json(backend_dir, frontend_dir)
    
    # 2. 使用 LLM 生成后端代码
    print(f"[Agent] Generating backend with LLM...")
    backend_prompt = build_backend_prompt(requirements_content, seed_data, task_type)
    backend_code = generate_with_llm(api_key, base_url, model, backend_prompt)
    
    if backend_code:
        write_backend_code(backend_dir, backend_code)
    else:
        print("[Agent] LLM failed, using fallback backend")
        write_fallback_backend(backend_dir, task_type, seed_data)
    
    # 3. 使用 LLM 生成前端代码
    print(f"[Agent] Generating frontend with LLM...")
    frontend_prompt = build_frontend_prompt(requirements_content, seed_data, task_type)
    frontend_code = generate_with_llm(api_key, base_url, model, frontend_prompt)
    
    if frontend_code:
        write_frontend_code(frontend_dir, frontend_code)
    else:
        print("[Agent] LLM failed, using fallback frontend")
        write_fallback_frontend(frontend_dir, task_type, seed_data)
    
    # 4. 构建前端
    print(f"[Agent] Building frontend...")
    build_frontend(frontend_dir)
    
    print(f"[Agent] Done!")

def find_requirements(source):
    source_path = Path(source)
    for f in source_path.glob('*.yaml'):
        return str(f)
    for f in source_path.glob('*.yml'):
        return str(f)
    for f in source_path.rglob('*.yaml'):
        return str(f)
    return None

def detect_task_type(requirements):
    req_lower = requirements.lower()
    if 'github' in req_lower or 'repository' in req_lower:
        return 'github'
    elif 'spreadsheet' in req_lower or 'workbook' in req_lower:
        return 'spreadsheet'
    return 'unknown'

def extract_seed_data(requirements):
    seed = {}
    accounts = re.findall(r"account\s+[`']([a-zA-Z0-9_-]+)[`']", requirements, re.I)
    if accounts:
        seed['accounts'] = list(set(accounts))
    emails = re.findall(r"email\s+[`']([^@`']+@[^`']+)[`']", requirements, re.I)
    if emails:
        seed['emails'] = list(set(emails))
    passwords = re.findall(r"password\s+[`']([^`']+)[`']", requirements, re.I)
    if passwords:
        seed['passwords'] = list(set(passwords))
    return seed

def create_fixed_package_json(backend_dir, frontend_dir):
    """创建固定的、有效的 package.json"""
    # 后端 package.json
    with open(backend_dir / 'package.json', 'w') as f:
        json.dump({
            "name": "backend",
            "version": "1.0.0",
            "scripts": {
                "start": "node src/index.js"
            },
            "dependencies": {
                "express": "^4.18.2",
                "cors": "^2.8.5",
                "body-parser": "^1.20.2",
                "better-sqlite3": "^9.4.3"
            }
        }, f, indent=2)
    
    # 前端 package.json
    with open(frontend_dir / 'package.json', 'w') as f:
        json.dump({
            "name": "frontend",
            "version": "0.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview"
            },
            "dependencies": {
                "react": "^19.2.0",
                "react-dom": "^19.2.0",
                "react-router-dom": "^7.11.0"
            },
            "devDependencies": {
                "@types/react": "^19.2.5",
                "@types/react-dom": "^19.2.3",
                "@vitejs/plugin-react": "^5.1.1",
                "vite": "^7.2.4"
            }
        }, f, indent=2)
    
    # 前端 vite.config.js
    with open(frontend_dir / 'vite.config.js', 'w') as f:
        f.write("""import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:3301'
    }
  }
})
""")
    
    # 前端 index.html
    with open(frontend_dir / 'index.html', 'w') as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Application</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""")

def build_backend_prompt(requirements, seed_data, task_type):
    accounts = seed_data.get('accounts', ['alice-dev'])
    emails = seed_data.get('emails', ['alice.dev@example.test'])
    passwords = seed_data.get('passwords', ['Valid-password-123!'])
    
    return f"""Generate ONLY the JavaScript code for a backend Express.js server.

The server must:
1. Listen on PORT environment variable (default 3301)
2. Expose GET /api/health returning {{ status: 'ok' }}
3. Use SQLite database (better-sqlite3)
4. Initialize seed data on startup

Seed data: accounts={accounts}, emails={emails}, passwords={passwords}

Required API endpoints:
- POST /api/register
- POST /api/login
- POST /api/recover
- POST /api/reset-password
- GET /api/orgs
- GET /api/repos
- GET /api/repos/:owner/:name
- POST /api/repos
- GET /api/repos/:owner/:name/issues
- POST /api/repos/:owner/:name/issues
- GET /api/repos/:owner/:name/pulls
- POST /api/repos/:owner/:name/pulls

Output ONLY the JavaScript code, no explanations."""

def build_frontend_prompt(requirements, seed_data, task_type):
    return """Generate ONLY the TypeScript/React code for a frontend application.

Required files:
1. src/main.tsx - React entry point
2. src/App.tsx - Main app with routing
3. src/index.css - Styles

The app must:
- Use React Router for navigation
- Have login, register, dashboard, repos, orgs pages
- Call backend API endpoints

Output ONLY the code, no explanations."""

def generate_with_llm(api_key, base_url, model, prompt):
    import urllib.request
    import urllib.error
    
    if not api_key:
        print("[Agent] No API key, skipping LLM")
        return None
    
    try:
        url = f"{base_url}/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        data = {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 8000,
            'temperature': 0.7
        }
        
        req = urllib.request.Request(url, json.dumps(data).encode(), headers)
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode())
        
        content = result['choices'][0]['message']['content']
        print(f"[Agent] LLM generated {len(content)} chars")
        return content
        
    except Exception as e:
        print(f"[Agent] LLM error: {e}")
        return None

def write_backend_code(backend_dir, code):
    """写入后端代码"""
    src_dir = backend_dir / 'src'
    src_dir.mkdir(exist_ok=True)
    
    # 提取 JavaScript 代码
    code_blocks = re.findall(r'```(?:javascript|js)?\n(.*?)```', code, re.DOTALL)
    
    if code_blocks:
        # 写入第一个代码块
        with open(src_dir / 'index.js', 'w') as f:
            f.write(code_blocks[0])
        print(f"[Agent] Written backend/src/index.js")
    else:
        # 直接写入
        with open(src_dir / 'index.js', 'w') as f:
            f.write(code)
        print(f"[Agent] Written backend/src/index.js")

def write_frontend_code(frontend_dir, code):
    """写入前端代码"""
    src_dir = frontend_dir / 'src'
    src_dir.mkdir(exist_ok=True)
    
    # 提取代码块
    code_blocks = re.findall(r'```(?:typescript|tsx|jsx)?\n(.*?)```', code, re.DOTALL)
    
    for block in code_blocks:
        block = block.strip()
        if 'main.tsx' in block[:50] or 'ReactDOM' in block[:100]:
            with open(src_dir / 'main.tsx', 'w') as f:
                f.write(block)
            print(f"[Agent] Written src/main.tsx")
        elif 'App.tsx' in block[:50] or 'function App' in block[:100]:
            with open(src_dir / 'App.tsx', 'w') as f:
                f.write(block)
            print(f"[Agent] Written src/App.tsx")
        elif 'index.css' in block[:50] or 'margin' in block[:100]:
            with open(src_dir / 'index.css', 'w') as f:
                f.write(block)
            print(f"[Agent] Written src/index.css")
    
    # 如果没有找到，写入默认代码
    if not (src_dir / 'main.tsx').exists():
        write_fallback_frontend(frontend_dir, 'github', {})

def write_fallback_backend(backend_dir, task_type, seed_data):
    """写入备用后端代码"""
    accounts = seed_data.get('accounts', ['alice-dev'])
    emails = seed_data.get('emails', ['alice.dev@example.test'])
    passwords = seed_data.get('passwords', ['Valid-password-123!'])
    
    src_dir = backend_dir / 'src'
    src_dir.mkdir(exist_ok=True)
    
    code = f"""const express = require('express');
const cors = require('cors');
const path = require('path');
const sqlite3 = require('better-sqlite3');

const app = express();
app.use(cors());
app.use(express.json());

const db = sqlite3(':memory:');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email_verified BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );
  CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_id INTEGER,
    description TEXT,
    is_public BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
  );
  CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES repositories(id)
  );
  CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    author_id INTEGER NOT NULL,
    state TEXT DEFAULT 'open',
    FOREIGN KEY (repo_id) REFERENCES repositories(id),
    FOREIGN KEY (author_id) REFERENCES users(id)
  );
  CREATE TABLE IF NOT EXISTS pull_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    author_id INTEGER NOT NULL,
    source_branch TEXT,
    target_branch TEXT,
    state TEXT DEFAULT 'open',
    FOREIGN KEY (repo_id) REFERENCES repositories(id),
    FOREIGN KEY (author_id) REFERENCES users(id)
  );
`);

const seedAccounts = {json.dumps(accounts)};
const seedEmails = {json.dumps(emails)};
const seedPasswords = {json.dumps(passwords)};

function initSeedData() {{
  for (let i = 0; i < seedAccounts.length; i++) {{
    const username = seedAccounts[i];
    const email = seedEmails[i] || username + '@example.test';
    const password = seedPasswords[0] || 'Valid-password-123!';
    try {{
      db.prepare('INSERT OR IGNORE INTO users (username, email, password, email_verified) VALUES (?, ?, ?, 1)').run(username, email, password);
      console.log('[Seed] Created user: ' + username);
    }} catch (e) {{}}
  }}
}}

initSeedData();

function generateToken() {{
  return Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);
}}

app.get('/api/health', (req, res) => res.json({{ status: 'ok' }}));

app.post('/api/register', (req, res) => {{
  const {{ username, email, password, confirm_password, terms }} = req.body;
  const errors = {{}};
  
  if (!username || username.length < 1 || username.length > 39) errors.username = 'Username format is invalid';
  if (!email || !email.includes('@')) errors.email = 'Email format is invalid';
  if (!password || password.length < 12) errors.password = 'Password requirements are not satisfied';
  if (password !== confirm_password) errors.confirm_password = 'Password confirmation does not match';
  if (!terms) errors.terms = 'Agree to terms is required';
  
  const existing = db.prepare('SELECT id FROM users WHERE username = ? OR email = ?').get(username, email);
  if (existing) {{
    if (existing.username === username) errors.username = 'Username already exists';
    if (existing.email === email) errors.email = 'Email already exists';
  }}
  
  if (Object.keys(errors).length > 0) {{
    return res.status(400).json({{ success: false, errors }});
  }}
  
  try {{
    const result = db.prepare('INSERT INTO users (username, email, password, email_verified) VALUES (?, ?, ?, 1)').run(username, email, password);
    res.json({{ success: true, userId: result.lastInsertRowid }});
  }} catch (err) {{
    res.status(400).json({{ success: false, errors: {{ general: err.message }} }});
  }}
}});

app.post('/api/login', (req, res) => {{
  const {{ username, password }} = req.body;
  const user = db.prepare('SELECT * FROM users WHERE (username = ? OR email = ?) AND password = ?').get(username, username, password);
  if (user) {{
    const token = generateToken();
    db.prepare('INSERT INTO sessions (user_id, token) VALUES (?, ?)').run(user.id, token);
    res.json({{ success: true, user: {{ id: user.id, username: user.username, email: user.email }}, token }});
  }} else {{
    res.status(401).json({{ success: false, error: 'Invalid credentials' }});
  }}
}});

app.post('/api/recover', (req, res) => {{
  res.json({{ success: true, code: '123456' }});
}});

app.post('/api/reset-password', (req, res) => {{
  const {{ email, code, new_password, confirm_password }} = req.body;
  if (code !== '123456') {{
    return res.status(400).json({{ success: false, errors: {{ code: 'Verification code is invalid' }} }});
  }}
  if (!new_password || new_password.length < 12) {{
    return res.status(400).json({{ success: false, errors: {{ new_password: 'Password requirements are not satisfied' }} }});
  }}
  if (new_password !== confirm_password) {{
    return res.status(400).json({{ success: false, errors: {{ confirm_password: 'Password confirmation does not match' }} }});
  }}
  const user = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
  if (user) {{
    db.prepare('UPDATE users SET password = ? WHERE id = ?').run(new_password, user.id);
  }}
  res.json({{ success: true, message: 'Password updated' }});
}});

app.get('/api/orgs', (req, res) => {{
  res.json([]);
}});

app.get('/api/repos', (req, res) => {{
  const repos = db.prepare('SELECT r.*, u.username as owner_name FROM repositories r JOIN users u ON r.owner_id = u.id').all();
  res.json(repos);
}});

app.get('/api/repos/:owner/:name', (req, res) => {{
  const repo = db.prepare('SELECT r.*, u.username as owner_name FROM repositories r JOIN users u ON r.owner_id = u.id WHERE u.username = ? AND r.name = ?').get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({{ error: 'Not found' }});
  const branches = db.prepare('SELECT * FROM branches WHERE repo_id = ?').all(repo.id);
  res.json({{ ...repo, branches }});
}});

app.post('/api/repos', (req, res) => {{
  const {{ name, description, is_public }} = req.body;
  const token = req.headers.authorization?.replace('Bearer ', '');
  const session = db.prepare('SELECT user_id FROM sessions WHERE token = ?').get(token);
  if (!session) return res.status(401).json({{ error: 'Not authenticated' }});
  try {{
    const result = db.prepare('INSERT INTO repositories (name, owner_id, description, is_public) VALUES (?, ?, ?, ?)').run(name, session.user_id, description || '', is_public !== false ? 1 : 0);
    db.prepare('INSERT INTO branches (repo_id, name) VALUES (?, ?)').run(result.lastInsertRowid, 'main');
    res.json({{ success: true, repoId: result.lastInsertRowid }});
  }} catch (err) {{
    res.status(400).json({{ error: err.message }});
  }}
}});

app.get('/api/repos/:owner/:name/issues', (req, res) => {{
  const repo = db.prepare('SELECT r.id FROM repositories r JOIN users u ON r.owner_id = u.id WHERE u.username = ? AND r.name = ?').get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({{ error: 'Not found' }});
  const issues = db.prepare('SELECT i.*, u.username as author_name FROM issues i JOIN users u ON i.author_id = u.id WHERE i.repo_id = ?').all(repo.id);
  res.json(issues);
}});

app.post('/api/repos/:owner/:name/issues', (req, res) => {{
  const {{ title, body }} = req.body;
  const token = req.headers.authorization?.replace('Bearer ', '');
  const session = db.prepare('SELECT user_id FROM sessions WHERE token = ?').get(token);
  if (!session) return res.status(401).json({{ error: 'Not authenticated' }});
  const repo = db.prepare('SELECT r.id FROM repositories r JOIN users u ON r.owner_id = u.id WHERE u.username = ? AND r.name = ?').get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({{ error: 'Not found' }});
  try {{
    const result = db.prepare('INSERT INTO issues (repo_id, title, body, author_id) VALUES (?, ?, ?, ?)').run(repo.id, title, body || '', session.user_id);
    res.json({{ success: true, issueId: result.lastInsertRowid }});
  }} catch (err) {{
    res.status(400).json({{ error: err.message }});
  }}
}});

app.get('/api/repos/:owner/:name/pulls', (req, res) => {{
  const repo = db.prepare('SELECT r.id FROM repositories r JOIN users u ON r.owner_id = u.id WHERE u.username = ? AND r.name = ?').get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({{ error: 'Not found' }});
  const prs = db.prepare('SELECT pr.*, u.username as author_name FROM pull_requests pr JOIN users u ON pr.author_id = u.id WHERE pr.repo_id = ?').all(repo.id);
  res.json(prs);
}});

app.post('/api/repos/:owner/:name/pulls', (req, res) => {{
  const {{ title, body, source_branch, target_branch }} = req.body;
  const token = req.headers.authorization?.replace('Bearer ', '');
  const session = db.prepare('SELECT user_id FROM sessions WHERE token = ?').get(token);
  if (!session) return res.status(401).json({{ error: 'Not authenticated' }});
  const repo = db.prepare('SELECT r.id FROM repositories r JOIN users u ON r.owner_id = u.id WHERE u.username = ? AND r.name = ?').get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({{ error: 'Not found' }});
  try {{
    const result = db.prepare('INSERT INTO pull_requests (repo_id, title, body, author_id, source_branch, target_branch) VALUES (?, ?, ?, ?, ?, ?)').run(repo.id, title, body || '', session.user_id, source_branch, target_branch);
    res.json({{ success: true, prId: result.lastInsertRowid }});
  }} catch (err) {{
    res.status(400).json({{ error: err.message }});
  }}
}});

const frontendDistPath = path.resolve(__dirname, '../../frontend/dist');
if (require('fs').existsSync(frontendDistPath)) {{
  app.use(express.static(frontendDistPath));
  app.get('*', (req, res) => {{
    res.sendFile(path.join(frontendDistPath, 'index.html'));
  }});
}}

const port = process.env.PORT || 3301;
app.listen(port, () => {{
  console.log('Backend listening at http://127.0.0.1:' + port);
}});
"""
    
    with open(src_dir / 'index.js', 'w') as f:
        f.write(code)
    print(f"[Agent] Written fallback backend")

def write_fallback_frontend(frontend_dir, task_type, seed_data):
    """写入备用前端代码"""
    src_dir = frontend_dir / 'src'
    src_dir.mkdir(exist_ok=True)
    
    # main.tsx
    with open(src_dir / 'main.tsx', 'w') as f:
        f.write("""import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
""")
    
    # App.tsx
    with open(src_dir / 'App.tsx', 'w') as f:
        f.write("""import { Routes, Route, Link } from 'react-router-dom'
import { useState } from 'react'

function App() {
  const [user, setUser] = useState<any>(null)

  return (
    <div>
      <header style={{ background: '#24292f', color: 'white', padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Application</h1>
        <nav>
          <Link to="/" style={{ color: 'white', marginRight: 16 }}>Home</Link>
          {!user && <Link to="/login" style={{ color: 'white', marginRight: 16 }}>Login</Link>}
          {!user && <Link to="/register" style={{ color: 'white', marginRight: 16 }}>Register</Link>}
          {user && <span style={{ color: 'white' }}>{user.username}</span>}
        </nav>
      </header>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>
        <Routes>
          <Route path="/" element={<Home user={user} />} />
          <Route path="/login" element={<Login setUser={setUser} />} />
          <Route path="/register" element={<Register />} />
        </Routes>
      </div>
    </div>
  )
}

function Home({ user }: { user: any }) {
  return (
    <div style={{ background: 'white', border: '1px solid #d0d7de', borderRadius: 6, padding: 16, marginBottom: 16 }}>
      <h2>Welcome{user ? ', ' + user.username : ''}</h2>
      <p>This is the application home page.</p>
    </div>
  )
}

function Login({ setUser }: { setUser: (u: any) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleLogin = async () => {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    })
    const data = await res.json()
    if (data.success) {
      setUser(data.user)
    } else {
      setError(data.error || 'Invalid credentials')
    }
  }

  return (
    <div style={{ background: 'white', border: '1px solid #d0d7de', borderRadius: 6, padding: 16, maxWidth: 400, margin: '0 auto' }}>
      <h2>Login</h2>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Username or email</label>
        <input type="text" value={username} onChange={e => setUsername(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Password</label>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
      </div>
      {error && <p style={{ color: 'red', marginBottom: 16 }}>{error}</p>}
      <button onClick={handleLogin} style={{ background: '#2da44e', color: 'white', padding: '8px 16px', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Login</button>
      <p style={{ marginTop: 16 }}><Link to="/register">Create an account</Link></p>
    </div>
  )
}

function Register() {
  const [form, setForm] = useState({ username: '', email: '', password: '', confirm_password: '', terms: false })
  const [errors, setErrors] = useState<any>({})

  const update = (field: string, value: any) => setForm(prev => ({ ...prev, [field]: value }))

  const handleRegister = async () => {
    const res = await fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form)
    })
    const data = await res.json()
    if (data.success) {
      window.location.href = '/login'
    } else {
      setErrors(data.errors || {})
    }
  }

  return (
    <div style={{ background: 'white', border: '1px solid #d0d7de', borderRadius: 6, padding: 16, maxWidth: 400, margin: '0 auto' }}>
      <h2>Create an account</h2>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Username</label>
        <input type="text" value={form.username} onChange={e => update('username', e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
        {errors.username && <p style={{ color: 'red', marginTop: 4 }}>{errors.username}</p>}
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Email</label>
        <input type="email" value={form.email} onChange={e => update('email', e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
        {errors.email && <p style={{ color: 'red', marginTop: 4 }}>{errors.email}</p>}
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Password</label>
        <input type="password" value={form.password} onChange={e => update('password', e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
        {errors.password && <p style={{ color: 'red', marginTop: 4 }}>{errors.password}</p>}
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Confirm password</label>
        <input type="password" value={form.confirm_password} onChange={e => update('confirm_password', e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
        {errors.confirm_password && <p style={{ color: 'red', marginTop: 4 }}>{errors.confirm_password}</p>}
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={form.terms} onChange={e => update('terms', e.target.checked)} />
          Agree to the terms
        </label>
        {errors.terms && <p style={{ color: 'red', marginTop: 4 }}>{errors.terms}</p>}
      </div>
      <button onClick={handleRegister} style={{ background: '#2da44e', color: 'white', padding: '8px 16px', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Create account</button>
    </div>
  )
}

export default App
""")
    
    # index.css
    with open(src_dir / 'index.css', 'w') as f:
        f.write("""* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: #f6f8fa; }
""")
    
    print(f"[Agent] Written fallback frontend")

def build_frontend(frontend_dir):
    """构建前端"""
    print("[Agent] Building frontend...")
    
    try:
        subprocess.run(['npm', 'install'], cwd=str(frontend_dir), capture_output=True, check=True)
        print("[Agent] Frontend dependencies installed")
    except Exception as e:
        print(f"[Agent] Warning: npm install failed: {e}")
        return
    
    try:
        subprocess.run(['npm', 'run', 'build'], cwd=str(frontend_dir), capture_output=True, check=True)
        print("[Agent] Frontend built successfully")
    except Exception as e:
        print(f"[Agent] Warning: npm build failed: {e}")

if __name__ == '__main__':
    main()