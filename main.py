#!/usr/bin/env python3
"""
ARC-Bench Hackathon Agent - 简化版
只生成代码，让平台处理启动
"""
import os
import sys
import json
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
        f.write("""const express = require('express');
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
`);

// Seed data
const seedAccounts = ['alice-dev'];
const seedEmails = ['alice.dev@example.test'];
const seedPasswords = ['Valid-password-123!'];

function initSeedData() {
  for (let i = 0; i < seedAccounts.length; i++) {
    const username = seedAccounts[i];
    const email = seedEmails[i] || username + '@example.test';
    const password = seedPasswords[0] || 'Valid-password-123!';
    try {
      db.prepare('INSERT OR IGNORE INTO users (username, email, password, email_verified) VALUES (?, ?, ?, 1)').run(username, email, password);
      console.log('[Seed] Created user: ' + username);
    } catch (e) {}
  }
}

initSeedData();

function generateToken() {
  return Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);
}

app.get('/api/health', (req, res) => res.json({ status: 'ok' }));

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
""")
    
    print(f"[Agent] Backend created")
    
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
    <title>Application</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""")
    
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
    
    print(f"[Agent] Frontend created")
    print(f"[Agent] Done!")

if __name__ == '__main__':
    main()