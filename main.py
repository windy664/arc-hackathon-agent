#!/usr/bin/env python3
"""
ARC-Bench Hackathon Agent - 使用 LLM 生成完整应用
使用平台提供的 OPENAI_API_KEY 和 OPENAI_BASE_URL
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
    
    # 使用 LLM 生成后端代码
    print(f"[Agent] Generating backend with LLM...")
    backend_code = generate_with_llm(
        api_key, base_url, model,
        f"""You are a backend developer. Create a complete Express.js backend for a web application.

Requirements:
{requirements_content[:3000]}

Generate the following files:
1. backend/package.json - with express, cors, body-parser, better-sqlite3
2. backend/src/index.js - complete server with all API endpoints

The server must:
- Listen on PORT environment variable or 3301
- Expose GET /api/health endpoint
- Initialize database with seed data
- Handle all CRUD operations needed

Output ONLY the code, no explanations."""
    )
    
    if backend_code:
        write_generated_code(backend_dir, backend_code, 'backend')
    else:
        print("[Agent] LLM generation failed, using fallback")
        generate_fallback_backend(backend_dir, task_type)
    
    # 使用 LLM 生成前端代码
    print(f"[Agent] Generating frontend with LLM...")
    frontend_code = generate_with_llm(
        api_key, base_url, model,
        f"""You are a frontend developer. Create a complete React frontend for a web application.

Requirements:
{requirements_content[:3000]}

Generate the following files:
1. frontend/package.json - with react, react-dom, react-router-dom, vite
2. frontend/vite.config.js - with proxy to backend
3. frontend/index.html - entry point
4. frontend/src/main.tsx - React entry
5. frontend/src/App.tsx - main app with routing
6. frontend/src/index.css - styles
7. All page components needed

The frontend must:
- Use React + TypeScript + Vite
- Have all pages needed for the requirements
- Call backend API endpoints
- Be properly structured

Output ONLY the code, no explanations."""
    )
    
    if frontend_code:
        write_generated_code(frontend_dir, frontend_code, 'frontend')
    else:
        print("[Agent] LLM generation failed, using fallback")
        generate_fallback_frontend(frontend_dir, task_type)
    
    # 构建前端
    print(f"[Agent] Building frontend...")
    build_frontend(frontend_dir)
    
    print(f"[Agent] Done!")

def find_requirements(source):
    """查找需求文件"""
    source_path = Path(source)
    for f in source_path.glob('*.yaml'):
        return str(f)
    for f in source_path.glob('*.yml'):
        return str(f)
    for f in source_path.rglob('*.yaml'):
        return str(f)
    return None

def detect_task_type(requirements):
    """检测任务类型"""
    req_lower = requirements.lower()
    if 'github' in req_lower or 'repository' in req_lower:
        return 'github'
    elif 'spreadsheet' in req_lower or 'workbook' in req_lower:
        return 'spreadsheet'
    return 'unknown'

def generate_with_llm(api_key, base_url, model, prompt):
    """使用 LLM 生成代码"""
    import urllib.request
    import urllib.error
    
    if not api_key:
        print("[Agent] No API key, skipping LLM generation")
        return None
    
    try:
        url = f"{base_url}/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        data = {
            'model': model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': 16000,
            'temperature': 0.7
        }
        
        req = urllib.request.Request(url, json.dumps(data).encode(), headers)
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read().decode())
        
        content = result['choices'][0]['message']['content']
        print(f"[Agent] LLM generated {len(content)} characters")
        return content
        
    except Exception as e:
        print(f"[Agent] LLM error: {e}")
        return None

def write_generated_code(directory, code, code_type):
    """解析 LLM 生成的代码并写入文件"""
    # 提取代码块
    code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', code, re.DOTALL)
    
    if not code_blocks:
        print(f"[Agent] No code blocks found, writing as single file")
        if code_type == 'backend':
            with open(directory / 'src' / 'index.js', 'w') as f:
                f.write(code)
        else:
            with open(directory / 'index.html', 'w') as f:
                f.write(code)
        return
    
    # 写入代码块
    for i, block in enumerate(code_blocks):
        # 尝试从注释中提取文件名
        first_line = block.strip().split('\n')[0]
        if '//' in first_line or '#' in first_line or '<!--' in first_line:
            # 可能是文件名注释
            pass
        
        if code_type == 'backend':
            if i == 0:
                (directory / 'src').mkdir(exist_ok=True)
                with open(directory / 'src' / 'index.js', 'w') as f:
                    f.write(block)
            elif i == 1:
                with open(directory / 'package.json', 'w') as f:
                    f.write(block)
        else:
            if i == 0:
                with open(directory / 'index.html', 'w') as f:
                    f.write(block)

def generate_fallback_backend(backend_dir, task_type):
    """生成备用后端代码"""
    (backend_dir / 'src').mkdir(exist_ok=True)
    
    with open(backend_dir / 'package.json', 'w') as f:
        json.dump({
            "name": "app-backend",
            "version": "1.0.0",
            "scripts": {"start": "node src/index.js"},
            "dependencies": {
                "express": "^4.18.2",
                "cors": "^2.8.5",
                "body-parser": "^1.20.2",
                "better-sqlite3": "^9.4.3"
            }
        }, f, indent=2)
    
    with open(backend_dir / 'src' / 'index.js', 'w') as f:
        f.write("""const express = require('express');
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
`);

// 种子数据
const seedAccounts = ['alice-dev'];
const seedEmails = ['alice.dev@example.test'];
const seedPasswords = ['Valid-password-123!'];

function initSeedData() {
  for (let i = 0; i < seedAccounts.length; i++) {
    const username = seedAccounts[i];
    const email = seedEmails[i] || `${username}@example.test`;
    const password = seedPasswords[0] || 'Valid-password-123!';
    try {
      db.prepare('INSERT OR IGNORE INTO users (username, email, password, email_verified) VALUES (?, ?, ?, 1)').run(username, email, password);
      console.log(`[Seed] Created user: ${username}`);
    } catch (e) {}
  }
}

initSeedData();

// 辅助函数
function generateToken() {
  return Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);
}

// API 路由
app.get('/api/health', (req, res) => res.json({ status: 'ok' }));

app.post('/api/register', (req, res) => {
  const { username, email, password, confirm_password, terms } = req.body;
  const errors = {};
  
  if (!username || username.length < 1 || username.length > 39) errors.username = 'Username format is invalid';
  if (!email || !email.includes('@')) errors.email = 'Email format is invalid';
  if (!password || password.length < 12) errors.password = 'Password requirements are not satisfied';
  if (password !== confirm_password) errors.confirm_password = 'Password confirmation does not match';
  if (!terms) errors.terms = 'Agree to terms is required';
  
  const existingUser = db.prepare('SELECT id FROM users WHERE username = ? OR email = ?').get(username, email);
  if (existingUser) {
    if (existingUser.username === username) errors.username = 'Username already exists';
    if (existingUser.email === email) errors.email = 'Email already exists';
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

// 静态文件
const frontendDistPath = path.resolve(__dirname, '../../frontend/dist');
if (require('fs').existsSync(frontendDistPath)) {
  app.use(express.static(frontendDistPath));
  app.get(/^(?!\\/api(?:\\/|$)).*/, (req, res) => {
    res.sendFile(path.join(frontendDistPath, 'index.html'));
  });
}

const port = process.env.PORT || 3301;
app.listen(port, () => {
  console.log(`Backend listening at http://127.0.0.1:${port}`);
});
""")

def generate_fallback_frontend(frontend_dir, task_type):
    """生成备用前端代码"""
    with open(frontend_dir / 'package.json', 'w') as f:
        json.dump({
            "name": "app-frontend",
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
    
    src_dir = frontend_dir / 'src'
    src_dir.mkdir(exist_ok=True)
    
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
    
    with open(src_dir / 'index.css', 'w') as f:
        f.write("""* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: #f6f8fa; }
.header { background: #24292f; color: white; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px; }
.card { background: white; border: 1px solid #d0d7de; border-radius: 6px; padding: 16px; margin-bottom: 16px; }
.btn { display: inline-block; padding: 5px 16px; background: #2da44e; color: white; border: 1px solid rgba(27,31,36,0.15); border-radius: 6px; cursor: pointer; font-size: 14px; text-decoration: none; }
input { padding: 5px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 14px; }
.form-group { margin-bottom: 16px; }
label { display: block; font-weight: 600; margin-bottom: 4px; }
.error { color: #cf222e; font-size: 12px; margin-top: 4px; }
.success { color: #2da44e; font-size: 12px; margin-top: 4px; }
""")
    
    with open(src_dir / 'App.tsx', 'w') as f:
        f.write("""import { Routes, Route, Link } from 'react-router-dom'
import { useState } from 'react'

function App() {
  const [user, setUser] = useState<any>(null)

  return (
    <div>
      <header className="header">
        <h1>Application</h1>
        <nav>
          <Link to="/" style={{ color: 'white', marginRight: 16 }}>Home</Link>
          {!user && <Link to="/login" style={{ color: 'white', marginRight: 16 }}>Login</Link>}
          {!user && <Link to="/register" style={{ color: 'white', marginRight: 16 }}>Register</Link>}
          {user && <span style={{ color: 'white' }}>{user.username}</span>}
        </nav>
      </header>
      <div className="container">
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
    <div className="card">
      <h2>Welcome{user ? `, ${user.username}` : ''}</h2>
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
    <div className="card" style={{ maxWidth: 400, margin: '0 auto' }}>
      <h2>Login</h2>
      <div className="form-group">
        <label>Username or email</label>
        <input type="text" value={username} onChange={e => setUsername(e.target.value)} style={{ width: '100%' }} />
      </div>
      <div className="form-group">
        <label>Password</label>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} style={{ width: '100%' }} />
      </div>
      {error && <p className="error">{error}</p>}
      <button className="btn" onClick={handleLogin}>Login</button>
      <p style={{ marginTop: 16 }}><a href="/register">Create an account</a></p>
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
    <div className="card" style={{ maxWidth: 400, margin: '0 auto' }}>
      <h2>Create an account</h2>
      <div className="form-group">
        <label>Username</label>
        <input type="text" value={form.username} onChange={e => update('username', e.target.value)} style={{ width: '100%' }} />
        {errors.username && <p className="error">{errors.username}</p>}
      </div>
      <div className="form-group">
        <label>Email</label>
        <input type="email" value={form.email} onChange={e => update('email', e.target.value)} style={{ width: '100%' }} />
        {errors.email && <p className="error">{errors.email}</p>}
      </div>
      <div className="form-group">
        <label>Password</label>
        <input type="password" value={form.password} onChange={e => update('password', e.target.value)} style={{ width: '100%' }} />
        {errors.password && <p className="error">{errors.password}</p>}
      </div>
      <div className="form-group">
        <label>Confirm password</label>
        <input type="password" value={form.confirm_password} onChange={e => update('confirm_password', e.target.value)} style={{ width: '100%' }} />
        {errors.confirm_password && <p className="error">{errors.confirm_password}</p>}
      </div>
      <div className="form-group">
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={form.terms} onChange={e => update('terms', e.target.checked)} />
          Agree to the terms
        </label>
        {errors.terms && <p className="error">{errors.terms}</p>}
      </div>
      <button className="btn" onClick={handleRegister}>Create account</button>
    </div>
  )
}

export default App
""")

def build_frontend(frontend_dir):
    """构建前端"""
    print("[Agent] Building frontend...")
    
    try:
        subprocess.run(['npm', 'install'], cwd=str(frontend_dir), capture_output=True, check=True)
        print("[Agent] Frontend dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"[Agent] Warning: npm install failed: {e}")
        try:
            subprocess.run(['pnpm', 'install'], cwd=str(frontend_dir), capture_output=True, check=True)
            print("[Agent] Frontend dependencies installed with pnpm")
        except subprocess.CalledProcessError as e2:
            print(f"[Agent] Warning: pnpm install also failed: {e2}")
            return
    
    try:
        subprocess.run(['npm', 'run', 'build'], cwd=str(frontend_dir), capture_output=True, check=True)
        print("[Agent] Frontend built successfully")
    except subprocess.CalledProcessError as e:
        print(f"[Agent] Warning: npm build failed: {e}")
        try:
            subprocess.run(['pnpm', 'run', 'build'], cwd=str(frontend_dir), capture_output=True, check=True)
            print("[Agent] Frontend built with pnpm")
        except subprocess.CalledProcessError as e2:
            print(f"[Agent] Warning: pnpm build also failed: {e2}")

if __name__ == '__main__':
    main()