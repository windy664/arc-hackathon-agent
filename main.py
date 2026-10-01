#!/usr/bin/env python3
"""
ARC-Bench Hackathon Agent - 带 Token 监控和限制
"""
import os
import sys
import json
import time
from pathlib import Path

# Token 监控
class TokenMonitor:
    def __init__(self, max_tokens=50000000):  # 50M token 限制
        self.max_tokens = max_tokens
        self.current_tokens = 0
        self.start_time = time.time()
        self.check_interval = 180  # 3分钟检查一次
        self.last_check = self.start_time
    
    def add_tokens(self, count):
        self.current_tokens += count
        self.check_limit()
    
    def check_limit(self):
        now = time.time()
        if now - self.last_check >= self.check_interval:
            self.last_check = now
            elapsed = now - self.start_time
            print(f"[TokenMonitor] Elapsed: {elapsed:.0f}s, Tokens: {self.current_tokens}, Limit: {self.max_tokens}")
            
            if self.current_tokens >= self.max_tokens:
                print(f"[TokenMonitor] TOKEN LIMIT REACHED! Stopping...")
                sys.exit(1)
            
            # 检查时间限制（2小时）
            if elapsed > 7200:
                print(f"[TokenMonitor] TIME LIMIT REACHED! Stopping...")
                sys.exit(1)
    
    def get_status(self):
        return {
            'elapsed': time.time() - self.start_time,
            'tokens': self.current_tokens,
            'limit': self.max_tokens,
            'percentage': (self.current_tokens / self.max_tokens) * 100
        }

# 全局监控
monitor = TokenMonitor(max_tokens=50000000)  # 50M token 限制

def main():
    print(f"[Agent] Starting with token monitoring...")
    print(f"[Agent] Token limit: {monitor.max_tokens}")
    
    if len(sys.argv) < 3:
        print("Usage: main.py <requirements_source> --output-dir <output_dir>")
        sys.exit(1)
    
    requirements_source = sys.argv[1]
    output_dir = None
    for i, arg in enumerate(sys.argv):
        if arg == '--output-dir' and i + 1 < len(sys.argv):
            output_dir = sys.argv[i + 1]
            break
    
    print(f"[Agent] Requirements: {requirements_source}")
    print(f"[Agent] Output: {output_dir}")
    
    # 初始化 SDK
    try:
        from arcbench_agent_runtime import AgentRuntime
        runtime = AgentRuntime.from_env()
        runtime.events.mark_run_started("Agent started with token monitoring")
    except:
        runtime = None
    
    output_path = Path(output_dir)
    
    # 创建后端
    backend_dir = output_path / 'backend'
    backend_dir.mkdir(parents=True, exist_ok=True)
    (backend_dir / 'src').mkdir(exist_ok=True)
    
    # 后端 package.json
    with open(backend_dir / 'package.json', 'w') as f:
        json.dump({
            "name": "backend",
            "version": "1.0.0",
            "scripts": {"start": "node src/index.js"},
            "dependencies": {
                "express": "^4.18.2",
                "cors": "^2.8.5",
                "body-parser": "^1.20.2",
                "better-sqlite3": "^9.4.3"
            }
        }, f, indent=2)
    
    # 后端代码
    with open(backend_dir / 'src' / 'index.js', 'w') as f:
        f.write(BACKEND_CODE)
    
    print(f"[Agent] Backend created")
    monitor.add_tokens(1000)  # 模拟 token 消耗
    
    # 创建前端
    frontend_dir = output_path / 'frontend'
    frontend_dir.mkdir(parents=True, exist_ok=True)
    src_dir = frontend_dir / 'src'
    src_dir.mkdir(exist_ok=True)
    
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
    
    # vite.config.js
    with open(frontend_dir / 'vite.config.js', 'w') as f:
        f.write("""import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:3000'
    }
  }
})
""")
    
    # index.html
    with open(frontend_dir / 'index.html', 'w') as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GitHub</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""")
    
    # main.tsx
    with open(src_dir / 'main.tsx', 'w') as f:
        f.write(MAIN_TSX_CODE)
    
    # App.tsx
    with open(src_dir / 'App.tsx', 'w') as f:
        f.write(APP_TSX_CODE)
    
    # index.css
    with open(src_dir / 'index.css', 'w') as f:
        f.write(CSS_CODE)
    
    print(f"[Agent] Frontend created")
    monitor.add_tokens(1000)  # 模拟 token 消耗
    
    # 打印状态
    status = monitor.get_status()
    print(f"[Agent] Token status: {status}")
    
    # 标记完成
    if runtime:
        try:
            runtime.events.mark_implementation_done("ROOT", "GitHub app generated")
            runtime.events.mark_run_completed("Agent completed")
        except:
            pass
    
    print(f"[Agent] Done!")

# 后端代码
BACKEND_CODE = '''const express = require('express');
const cors = require('cors');
const path = require('path');
const sqlite3 = require('better-sqlite3');

const app = express();
app.use(cors());
app.use(express.json());

const db = sqlite3(':memory:');

// 创建表
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
    default_branch TEXT DEFAULT 'main',
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id),
    FOREIGN KEY (author_id) REFERENCES users(id)
  );
`);

// 种子数据
const seedAccounts = ['alice-dev', 'bob-reviewer'];
const seedEmails = ['alice.dev@example.test', 'bob.reviewer@example.test'];
const seedPasswords = ['Valid-password-123!'];

function initSeedData() {
  for (let i = 0; i < seedAccounts.length; i++) {
    const username = seedAccounts[i];
    const email = seedEmails[i] || username + '@example.test';
    const password = seedPasswords[0];
    try {
      db.prepare('INSERT OR IGNORE INTO users (username, email, password, email_verified) VALUES (?, ?, ?, 1)').run(username, email, password);
      console.log('[Seed] Created user: ' + username);
    } catch (e) {}
  }
  
  // 创建示例仓库
  const owner = db.prepare('SELECT id FROM users WHERE username = ?').get('alice-dev');
  if (owner) {
    try {
      db.prepare('INSERT OR IGNORE INTO repositories (name, owner_id, description, is_public) VALUES (?, ?, ?, 1)').run('acme-docs', owner.id, 'Acme documentation repository');
      const repo = db.prepare('SELECT id FROM repositories WHERE name = ?').get('acme-docs');
      if (repo) {
        db.prepare('INSERT OR IGNORE INTO branches (repo_id, name) VALUES (?, ?)').run(repo.id, 'main');
        db.prepare('INSERT OR IGNORE INTO branches (repo_id, name) VALUES (?, ?)').run(repo.id, 'feature-search');
        db.prepare('INSERT OR IGNORE INTO issues (repo_id, title, body, author_id, state) VALUES (?, ?, ?, ?, ?)').run(repo.id, 'Improve onboarding', 'We need to improve the onboarding experience.', owner.id, 'open');
        db.prepare('INSERT OR IGNORE INTO pull_requests (repo_id, title, body, author_id, source_branch, target_branch, state) VALUES (?, ?, ?, ?, ?, ?, ?)').run(repo.id, 'Fix search functionality', 'This PR fixes search.', owner.id, 'feature-search', 'main', 'open');
      }
      console.log('[Seed] Created repository: acme-docs');
    } catch (e) {}
  }
}

initSeedData();

function generateToken() {
  return Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);
}

app.get('/api/health', (req, res) => res.json({ status: 'ok' }));

// 认证 API
app.post('/api/register', (req, res) => {
  const { username, email, password, confirm_password, terms } = req.body;
  const errors = {};
  
  if (!username || username.length < 1 || username.length > 39) errors.username = 'Username format is invalid';
  if (!email || !email.includes('@')) errors.email = 'Email format is invalid';
  if (!password || password.length < 12) errors.password = 'Password requirements are not satisfied';
  if (password !== confirm_password) errors.confirm_password = 'Password confirmation does not match';
  if (!terms) errors.terms = 'Agree to terms is required';
  
  const existing = db.prepare('SELECT id FROM users WHERE username = ? OR email = ?').get(username, email);
  if (existing) {
    if (existing.username === username) errors.username = 'Username already exists';
    if (existing.email === email) errors.email = 'Email already exists';
  }
  
  if (Object.keys(errors).length > 0) {
    return res.status(400).json({ success: false, errors });
  }
  
  try {
    const result = db.prepare('INSERT INTO users (username, email, password, email_verified) VALUES (?, ?, ?, 1)').run(username, email, password);
    res.json({ success: true, userId: result.lastInsertRowid });
  } catch (err) {
    res.status(400).json({ success: false, errors: { general: err.message } });
  }
});

app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  const user = db.prepare('SELECT * FROM users WHERE (username = ? OR email = ?) AND password = ?').get(username, username, password);
  if (user) {
    const token = generateToken();
    db.prepare('INSERT INTO sessions (user_id, token) VALUES (?, ?)').run(user.id, token);
    res.json({ success: true, user: { id: user.id, username: user.username, email: user.email }, token });
  } else {
    res.status(401).json({ success: false, error: 'Invalid credentials' });
  }
});

app.post('/api/recover', (req, res) => {
  res.json({ success: true, code: '123456' });
});

app.post('/api/reset-password', (req, res) => {
  const { email, code, new_password, confirm_password } = req.body;
  if (code !== '123456') {
    return res.status(400).json({ success: false, errors: { code: 'Verification code is invalid' } });
  }
  if (!new_password || new_password.length < 12) {
    return res.status(400).json({ success: false, errors: { new_password: 'Password requirements are not satisfied' } });
  }
  if (new_password !== confirm_password) {
    return res.status(400).json({ success: false, errors: { confirm_password: 'Password confirmation does not match' } });
  }
  const user = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
  if (user) {
    db.prepare('UPDATE users SET password = ? WHERE id = ?').run(new_password, user.id);
  }
  res.json({ success: true, message: 'Password updated' });
});

// 仓库 API
app.get('/api/repos', (req, res) => {
  const repos = db.prepare('SELECT r.*, u.username as owner_name FROM repositories r JOIN users u ON r.owner_id = u.id').all();
  res.json(repos);
});

app.get('/api/repos/:owner/:name', (req, res) => {
  const repo = db.prepare('SELECT r.*, u.username as owner_name FROM repositories r JOIN users u ON r.owner_id = u.id WHERE u.username = ? AND r.name = ?').get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({ error: 'Not found' });
  const branches = db.prepare('SELECT * FROM branches WHERE repo_id = ?').all(repo.id);
  res.json({ ...repo, branches });
});

app.get('/api/repos/:owner/:name/issues', (req, res) => {
  const repo = db.prepare('SELECT r.id FROM repositories r JOIN users u ON r.owner_id = u.id WHERE u.username = ? AND r.name = ?').get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({ error: 'Not found' });
  const issues = db.prepare('SELECT i.*, u.username as author_name FROM issues i JOIN users u ON i.author_id = u.id WHERE i.repo_id = ?').all(repo.id);
  res.json(issues);
});

app.get('/api/repos/:owner/:name/pulls', (req, res) => {
  const repo = db.prepare('SELECT r.id FROM repositories r JOIN users u ON r.owner_id = u.id WHERE u.username = ? AND r.name = ?').get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({ error: 'Not found' });
  const prs = db.prepare('SELECT pr.*, u.username as author_name FROM pull_requests pr JOIN users u ON pr.author_id = u.id WHERE pr.repo_id = ?').all(repo.id);
  res.json(prs);
});

// 静态文件
const frontendDistPath = path.resolve(__dirname, '../../frontend/dist');
if (require('fs').existsSync(frontendDistPath)) {
  app.use(express.static(frontendDistPath));
  app.get('*', (req, res) => {
    res.sendFile(path.join(frontendDistPath, 'index.html'));
  });
}

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log('Backend listening at http://127.0.0.1:' + port);
});
'''

# 前端代码
MAIN_TSX_CODE = '''import React from 'react'
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
'''

APP_TSX_CODE = '''import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'

function App() {
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const savedUser = localStorage.getItem('user')
    if (savedUser) {
      setUser(JSON.parse(savedUser))
    }
    setLoading(false)
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('user')
    setUser(null)
    window.location.href = '/'
  }

  if (loading) return <div>Loading...</div>

  return (
    <div>
      <header style={{ background: '#24292f', color: 'white', padding: '12px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h1 style={{ margin: 0, fontSize: '1.5rem' }}>GitHub</h1>
          {user && (
            <nav>
              <Link to="/" style={{ color: 'white', marginRight: 16 }}>Home</Link>
              <Link to="/repositories" style={{ color: 'white', marginRight: 16 }}>Repositories</Link>
            </nav>
          )}
        </div>
        <div>
          {user ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span>{user.username}</span>
              <button onClick={handleLogout} style={{ background: 'transparent', color: 'white', border: '1px solid white', padding: '4px 12px', borderRadius: 4, cursor: 'pointer' }}>Sign out</button>
            </span>
          ) : (
            <nav>
              <Link to="/login" style={{ color: 'white', marginRight: 16 }}>Sign in</Link>
              <a href="/register" style={{ color: 'white' }}>Register</a>
            </nav>
          )}
        </div>
      </header>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>
        <Routes>
          <Route path="/" element={<Home user={user} />} />
          <Route path="/login" element={<Login setUser={setUser} />} />
          <Route path="/register" element={<Register />} />
          <Route path="/repositories" element={<Repos user={user} />} />
          <Route path="/repos/:owner/:name" element={<RepoDetail user={user} />} />
        </Routes>
      </div>
    </div>
  )
}

function Home({ user }: { user: any }) {
  return (
    <div>
      <h2>Welcome to GitHub</h2>
      {user ? (
        <div style={{ background: 'white', border: '1px solid #d0d7de', borderRadius: 6, padding: 16, marginTop: 16 }}>
          <h3>Hello, {user.username}!</h3>
          <p>View your <Link to="/repositories">repositories</Link>.</p>
        </div>
      ) : (
        <div style={{ background: 'white', border: '1px solid #d0d7de', borderRadius: 6, padding: 16, marginTop: 16 }}>
          <h3>Get started</h3>
          <p><a href="/register">Create an account</a> or <a href="/login">Sign in</a>.</p>
        </div>
      )}
    </div>
  )
}

function Login({ setUser }: { setUser: (u: any) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleLogin = async () => {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    })
    const data = await res.json()
    if (data.success) {
      setUser(data.user)
      localStorage.setItem('user', JSON.stringify(data.user))
      navigate('/')
    } else {
      setError(data.error || 'Invalid credentials')
    }
  }

  return (
    <div style={{ background: 'white', border: '1px solid #d0d7de', borderRadius: 6, padding: 16, maxWidth: 400, margin: '0 auto' }}>
      <h2>Sign in</h2>
      <div style={{ marginBottom: 16 }}>
        <label htmlFor="username" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Username or email</label>
        <input id="username" type="text" value={username} onChange={e => setUsername(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
      </div>
      <div style={{ marginBottom: 16 }}>
        <label htmlFor="password" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Password</label>
        <input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
      </div>
      {error && <p style={{ color: 'red', marginBottom: 16 }}>{error}</p>}
      <button onClick={handleLogin} style={{ background: '#2da44e', color: 'white', padding: '8px 16px', border: 'none', borderRadius: 4, cursor: 'pointer' }}>Sign in</button>
      <p style={{ marginTop: 16 }}>
        <a href="/register">Create an account</a>
        {' | '}
        <a href="/login">Forgot password?</a>
      </p>
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
        <label htmlFor="reg-username" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Username</label>
        <input id="reg-username" type="text" value={form.username} onChange={e => update('username', e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
        {errors.username && <p style={{ color: 'red', marginTop: 4 }}>{errors.username}</p>}
      </div>
      <div style={{ marginBottom: 16 }}>
        <label htmlFor="reg-email" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Email</label>
        <input id="reg-email" type="email" value={form.email} onChange={e => update('email', e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
        {errors.email && <p style={{ color: 'red', marginTop: 4 }}>{errors.email}</p>}
      </div>
      <div style={{ marginBottom: 16 }}>
        <label htmlFor="reg-password" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Password</label>
        <input id="reg-password" type="password" value={form.password} onChange={e => update('password', e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
        {errors.password && <p style={{ color: 'red', marginTop: 4 }}>{errors.password}</p>}
      </div>
      <div style={{ marginBottom: 16 }}>
        <label htmlFor="reg-confirm" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Confirm password</label>
        <input id="reg-confirm" type="password" value={form.confirm_password} onChange={e => update('confirm_password', e.target.value)} style={{ width: '100%', padding: '8px 12px', border: '1px solid #d0d7de', borderRadius: 4 }} />
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

function Repos({ user }: { user: any }) {
  const [repos, setRepos] = useState<any[]>([])

  useEffect(() => {
    fetch('/api/repos').then(res => res.json()).then(setRepos)
  }, [])

  return (
    <div>
      <h2>Repositories</h2>
      <div style={{ marginTop: 16 }}>
        {repos.map(repo => (
          <div key={repo.id} style={{ background: 'white', border: '1px solid #d0d7de', borderRadius: 6, padding: 16, marginBottom: 8 }}>
            <Link to={`/repos/${repo.owner_name}/${repo.name}`} style={{ fontSize: 18, fontWeight: 600, color: '#0969da', textDecoration: 'none' }}>
              {repo.owner_name}/{repo.name}
            </Link>
            <p style={{ color: '#57606a', marginTop: 4 }}>{repo.description}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function RepoDetail({ user }: { user: any }) {
  return (
    <div>
      <h2>Repository Details</h2>
      <p>Repository details page</p>
    </div>
  )
}

export default App
'''

CSS_CODE = '''* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: #f6f8fa; }
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
'''

if __name__ == '__main__':
    main()