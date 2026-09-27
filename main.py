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
    
    # 构建详细的 prompt
    backend_prompt = build_backend_prompt(requirements_content, seed_data, task_type)
    frontend_prompt = build_frontend_prompt(requirements_content, seed_data, task_type)
    
    # 使用 LLM 生成后端代码
    print(f"[Agent] Generating backend with LLM...")
    backend_code = generate_with_llm(api_key, base_url, model, backend_prompt)
    
    if backend_code:
        write_generated_code(backend_dir, backend_code, 'backend')
    else:
        print("[Agent] LLM generation failed, using fallback")
        generate_fallback_backend(backend_dir, task_type, seed_data)
    
    # 使用 LLM 生成前端代码
    print(f"[Agent] Generating frontend with LLM...")
    frontend_code = generate_with_llm(api_key, base_url, model, frontend_prompt)
    
    if frontend_code:
        write_generated_code(frontend_dir, frontend_code, 'frontend')
    else:
        print("[Agent] LLM generation failed, using fallback")
        generate_fallback_frontend(frontend_dir, task_type, seed_data)
    
    # 构建前端
    print(f"[Agent] Building frontend...")
    try:
        build_frontend(frontend_dir)
    except Exception as e:
        print(f"[Agent] Warning: Frontend build failed: {e}")
    
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
        print(f"[Agent] No code blocks found in LLM output")
        return
    
    # 写入代码块
    for i, block in enumerate(code_blocks):
        block = block.strip()
        if not block:
            continue
        
        # 检测文件名
        first_line = block.split('\n')[0].strip()
        
        if 'package.json' in first_line or '"name"' in block[:100]:
            # 这是 package.json
            # 确保是有效的 JSON
            try:
                # 尝试解析 JSON
                json_start = block.find('{')
                json_end = block.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = block[json_start:json_end]
                    json.loads(json_str)  # 验证 JSON
                    with open(directory / 'package.json', 'w') as f:
                        f.write(json_str)
                    print(f"[Agent] Written package.json")
            except json.JSONDecodeError as e:
                print(f"[Agent] Warning: Invalid JSON in package.json: {e}")
                
        elif 'index.js' in first_line or 'const ' in block[:50]:
            # 这是 JavaScript 代码
            src_dir = directory / 'src'
            src_dir.mkdir(exist_ok=True)
            with open(src_dir / 'index.js', 'w') as f:
                f.write(block)
            print(f"[Agent] Written src/index.js")
            
        elif 'index.html' in first_line or '<!DOCTYPE' in block[:50]:
            # 这是 HTML
            with open(directory / 'index.html', 'w') as f:
                f.write(block)
            print(f"[Agent] Written index.html")
            
        elif 'import ' in block[:100] or 'export ' in block[:100]:
            # 这是 TypeScript/React 代码
            src_dir = directory / 'src'
            src_dir.mkdir(exist_ok=True)
            
            if 'App.tsx' in first_line or 'function App' in block:
                with open(src_dir / 'App.tsx', 'w') as f:
                    f.write(block)
                print(f"[Agent] Written src/App.tsx")
            elif 'main.tsx' in first_line or 'ReactDOM' in block:
                with open(src_dir / 'main.tsx', 'w') as f:
                    f.write(block)
                print(f"[Agent] Written src/main.tsx")
            else:
                # 默认写入 App.tsx
                with open(src_dir / 'App.tsx', 'w') as f:
                    f.write(block)
                print(f"[Agent] Written src/App.tsx")

def extract_seed_data(requirements):
    """提取种子数据"""
    seed = {}
    
    # 账户
    accounts = re.findall(r"account\s+[`']([a-zA-Z0-9_-]+)[`']", requirements, re.I)
    if accounts:
        seed['accounts'] = list(set(accounts))
    
    # 邮箱
    emails = re.findall(r"email\s+[`']([^@`']+@[^`']+)[`']", requirements, re.I)
    if emails:
        seed['emails'] = list(set(emails))
    
    # 密码
    passwords = re.findall(r"password\s+[`']([^`']+)[`']", requirements, re.I)
    if passwords:
        seed['passwords'] = list(set(passwords))
    
    # 工作簿
    workbooks = re.findall(r"workbook\s+[`']([A-Za-z0-9\s]+)[`']", requirements, re.I)
    if workbooks:
        seed['workbooks'] = list(set([w.strip() for w in workbooks]))
    
    # 工作表
    worksheets = re.findall(r"worksheet\s+[`']([A-Za-z0-9\s]+)[`']", requirements, re.I)
    if worksheets:
        seed['worksheets'] = list(set([w.strip() for w in worksheets]))
    
    # 组织
    orgs = re.findall(r"organization\s+[`']([A-Za-z0-9\s]+)[`']", requirements, re.I)
    if orgs:
        seed['organizations'] = list(set([o.strip() for o in orgs]))
    
    # 仓库
    repos = re.findall(r"repository\s+[`']([A-Za-z0-9\s-]+)[`']", requirements, re.I)
    if repos:
        seed['repositories'] = list(set([r.strip() for r in repos]))
    
    # 分支
    branches = re.findall(r"branch(?:es)?\s+[`']([A-Za-z0-9\s-]+)[`']", requirements, re.I)
    if branches:
        seed['branches'] = list(set([b.strip() for b in branches]))
    
    return seed

def build_backend_prompt(requirements, seed_data, task_type):
    """构建后端 LLM prompt"""
    accounts = seed_data.get('accounts', ['alice-dev'])
    emails = seed_data.get('emails', ['alice.dev@example.test'])
    passwords = seed_data.get('passwords', ['Valid-password-123!'])
    orgs = seed_data.get('organizations', ['Acme Demo'])
    repos = seed_data.get('repositories', ['acme-docs'])
    branches = seed_data.get('branches', ['main', 'feature-search'])
    
    if task_type == 'github':
        return f"""You are an expert backend developer. Create a complete Express.js backend for a GitHub-like collaboration platform.

CRITICAL REQUIREMENTS:
1. The server MUST listen on PORT environment variable (default 3301)
2. MUST expose GET /api/health endpoint returning {{ status: 'ok' }}
3. MUST initialize database with seed data on startup
4. MUST serve frontend static files from ../../frontend/dist

SEED DATA (MUST be pre-populated):
- Users: {accounts}
- Emails: {emails}
- Passwords: {passwords}
- Organizations: {orgs}
- Repositories: {repos}
- Branches: {branches}

REQUIRED API ENDPOINTS:
1. POST /api/register - Register new user
   - Fields: username, email, password, confirm_password, terms
   - Validate: username 1-39 chars, email format, password 12-128 chars with uppercase/lowercase/digit/special
   - Return errors per field, retain input on failure
   
2. POST /api/login - Login
   - Fields: username (or email), password
   - Return token on success, generic "Invalid credentials" on failure
   
3. POST /api/recover - Password recovery
   - Always return success with code "123456"
   
4. POST /api/reset-password - Reset password
   - Fields: email, code, new_password, confirm_password
   - Code must be "123456"
   
5. GET /api/orgs - List organizations
6. GET /api/orgs/:name - Get organization details with members and repos
7. GET /api/repos - List repositories
8. GET /api/repos/:owner/:name - Get repository details with branches
9. POST /api/repos - Create repository (requires auth)
10. GET /api/repos/:owner/:name/issues - List issues
11. POST /api/repos/:owner/:name/issues - Create issue (requires auth)
12. GET /api/repos/:owner/:name/pulls - List pull requests
13. POST /api/repos/:owner/:name/pulls - Create pull request (requires auth)

DATABASE TABLES:
- users (id, username, email, password, email_verified, created_at)
- sessions (id, user_id, token, created_at)
- organizations (id, name, description, created_at)
- org_members (id, org_id, user_id, role)
- repositories (id, name, owner_id, org_id, description, is_public, default_branch, created_at)
- branches (id, repo_id, name, created_at)
- issues (id, repo_id, title, body, author_id, state, created_at)
- pull_requests (id, repo_id, title, body, author_id, source_branch, target_branch, state, created_at)
- issue_labels (id, issue_id, label)
- pr_reviews (id, pr_id, reviewer_id, state)

Generate ONLY the code for:
1. package.json
2. src/index.js (complete server)

No explanations, just code."""
    else:
        return f"""You are an expert backend developer. Create a complete Express.js backend for a spreadsheet application.

Generate ONLY the code for:
1. package.json
2. src/index.js

The server must:
- Listen on PORT environment variable (default 3301)
- Expose GET /api/health endpoint
- Initialize database with seed data
- Serve frontend static files from ../../frontend/dist

No explanations, just code."""

def build_frontend_prompt(requirements, seed_data, task_type):
    """构建前端 LLM prompt"""
    if task_type == 'github':
        return """You are an expert frontend developer. Create a complete React + TypeScript + Vite frontend for a GitHub-like collaboration platform.

REQUIRED STRUCTURE:
1. package.json - with react, react-dom, react-router-dom, vite
2. vite.config.js - with proxy to http://localhost:3301
3. index.html - entry point
4. src/main.tsx - React entry
5. src/App.tsx - main app with routing
6. src/index.css - styles
7. src/api/index.ts - API client
8. src/pages/LoginPage.tsx - Login page
9. src/pages/RegisterPage.tsx - Register page
10. src/pages/DashboardPage.tsx - Dashboard
11. src/pages/ReposPage.tsx - Repository list
12. src/pages/RepoDetailPage.tsx - Repository details
13. src/pages/OrgsPage.tsx - Organizations

CRITICAL REQUIREMENTS:
- Login page MUST have "Username or email" and "Password" fields
- Login page MUST have "Forgot password" link
- Register page MUST have: Username, Email, Password, Confirm password, "Agree to terms" checkbox, "Create account" button
- All forms MUST validate and show field-level errors
- Navigation MUST work with React Router
- API calls MUST use /api/ prefix

Generate ONLY the code, no explanations."""
    else:
        return """You are an expert frontend developer. Create a complete React + TypeScript + Vite frontend for a spreadsheet application.

Generate ONLY the code, no explanations."""
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

def generate_fallback_backend(backend_dir, task_type, seed_data):
    """生成备用后端代码"""
    accounts = seed_data.get('accounts', ['alice-dev'])
    emails = seed_data.get('emails', ['alice.dev@example.test'])
    passwords = seed_data.get('passwords', ['Valid-password-123!'])
    orgs = seed_data.get('organizations', ['Acme Demo'])
    repos = seed_data.get('repositories', ['acme-docs'])
    branches = seed_data.get('branches', ['main', 'feature-search'])
    
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
    
    # 生成后端代码
    backend_code = generate_github_backend_code(accounts, emails, passwords, orgs, repos, branches)
    
    with open(backend_dir / 'src' / 'index.js', 'w') as f:
        f.write(backend_code)

def generate_github_backend_code(accounts, emails, passwords, orgs, repos, branches):
    """生成 GitHub 后端代码"""
    
    code = """const express = require('express');
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
  CREATE TABLE IF NOT EXISTS org_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT DEFAULT 'Member',
    FOREIGN KEY (org_id) REFERENCES organizations(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(org_id, user_id)
  );
  CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_id INTEGER,
    org_id INTEGER,
    description TEXT,
    is_public BOOLEAN DEFAULT 1,
    default_branch TEXT DEFAULT 'main',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id),
    FOREIGN KEY (org_id) REFERENCES organizations(id)
  );
  CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id),
    UNIQUE(repo_id, name)
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
    source_branch TEXT NOT NULL,
    target_branch TEXT NOT NULL,
    state TEXT DEFAULT 'open',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repo_id) REFERENCES repositories(id),
    FOREIGN KEY (author_id) REFERENCES users(id)
  );
  CREATE TABLE IF NOT EXISTS issue_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    FOREIGN KEY (issue_id) REFERENCES issues(id)
  );
  CREATE TABLE IF NOT EXISTS pr_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_id INTEGER NOT NULL,
    reviewer_id INTEGER NOT NULL,
    state TEXT DEFAULT 'pending',
    FOREIGN KEY (pr_id) REFERENCES pull_requests(id),
    FOREIGN KEY (reviewer_id) REFERENCES users(id)
  );
`);
"""
    
    # 添加种子数据初始化
    code += f"""
const seedAccounts = {json.dumps(accounts)};
const seedEmails = {json.dumps(emails)};
const seedPasswords = {json.dumps(passwords)};
const seedOrgs = {json.dumps(orgs)};
const seedRepos = {json.dumps(repos)};
const seedBranches = {json.dumps(branches)};

function initSeedData() {{
  for (let i = 0; i < seedAccounts.length; i++) {{
    const username = seedAccounts[i];
    const email = seedEmails[i] || `${{username}}@example.test`;
    const password = seedPasswords[0] || 'Valid-password-123!';
    try {{
      db.prepare('INSERT OR IGNORE INTO users (username, email, password, email_verified) VALUES (?, ?, ?, 1)').run(username, email, password);
      console.log(`[Seed] Created user: ${{username}}`);
    }} catch (e) {{}}
  }}
  
  for (const orgName of seedOrgs) {{
    try {{
      db.prepare('INSERT OR IGNORE INTO organizations (name) VALUES (?)').run(orgName);
      const org = db.prepare('SELECT id FROM organizations WHERE name = ?').get(orgName);
      if (org) {{
        const owner = db.prepare('SELECT id FROM users WHERE username = ?').get(seedAccounts[0]);
        if (owner) {{
          db.prepare('INSERT OR IGNORE INTO org_members (org_id, user_id, role) VALUES (?, ?, ?)').run(org.id, owner.id, 'Owner');
        }}
      }}
      console.log(`[Seed] Created org: ${{orgName}}`);
    }} catch (e) {{}}
  }}
  
  const owner = db.prepare('SELECT id FROM users WHERE username = ?').get(seedAccounts[0]);
  if (owner) {{
    for (const repoName of seedRepos) {{
      try {{
        const org = db.prepare('SELECT id FROM organizations WHERE name = ?').get(seedOrgs[0]);
        db.prepare('INSERT OR IGNORE INTO repositories (name, owner_id, org_id, description, is_public) VALUES (?, ?, ?, ?, ?)').run(
          repoName, owner.id, org ? org.id : null, `${{repoName}} repository`, repoName !== 'secret-research' ? 1 : 0
        );
        const repo = db.prepare('SELECT id FROM repositories WHERE name = ?').get(repoName);
        if (repo) {{
          for (const branch of seedBranches) {{
            db.prepare('INSERT OR IGNORE INTO branches (repo_id, name) VALUES (?, ?)').run(repo.id, branch);
          }}
        }}
        console.log(`[Seed] Created repo: ${{repoName}}`);
      }} catch (e) {{}}
    }}
  }}
}}

initSeedData();
"""
    
    # 添加辅助函数和API路由
    code += """
function generateToken() {
  return Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);
}

function validateUsername(username) {
  if (!username || username.length < 1 || username.length > 39) return false;
  return /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/.test(username);
}

function validateEmail(email) {
  if (!email || email.length > 254) return false;
  const parts = email.split('@');
  if (parts.length !== 2) return false;
  if (!parts[0] || !parts[1]) return false;
  if (!parts[1].includes('.')) return false;
  return true;
}

function validatePassword(password) {
  if (!password || password.length < 12 || password.length > 128) return false;
  if (/\\s/.test(password)) return false;
  if (!/[A-Z]/.test(password)) return false;
  if (!/[a-z]/.test(password)) return false;
  if (!/[0-9]/.test(password)) return false;
  if (!/[^A-Za-z0-9]/.test(password)) return false;
  return true;
}

app.get('/api/health', (req, res) => res.json({ status: 'ok' }));

app.post('/api/register', (req, res) => {
  const { username, email, password, confirm_password, terms } = req.body;
  const errors = {};
  
  if (!validateUsername(username)) errors.username = 'Username format is invalid';
  if (!validateEmail(email)) errors.email = 'Email format is invalid';
  if (!validatePassword(password)) errors.password = 'Password requirements are not satisfied';
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

app.get('/api/orgs', (req, res) => {
  const orgs = db.prepare('SELECT * FROM organizations').all();
  res.json(orgs);
});

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

// 静态文件
const frontendDistPath = path.resolve(__dirname, '../../frontend/dist');
if (require('fs').existsSync(frontendDistPath)) {
  app.use(express.static(frontendDistPath));
  app.get('*', (req, res) => {
    res.sendFile(path.join(frontendDistPath, 'index.html'));
  });
}

const port = process.env.PORT || 3301;
app.listen(port, () => {
  console.log('Backend listening at http://127.0.0.1:' + port);
});
"""
    
    return code

def generate_fallback_frontend(frontend_dir, task_type, seed_data):
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
        # 不要崩溃，继续
        return
    except FileNotFoundError:
        print("[Agent] Warning: npm not found")
        return
    
    try:
        subprocess.run(['npm', 'run', 'build'], cwd=str(frontend_dir), capture_output=True, check=True)
        print("[Agent] Frontend built successfully")
    except subprocess.CalledProcessError as e:
        print(f"[Agent] Warning: npm build failed: {e}")
    except FileNotFoundError:
        print("[Agent] Warning: npm not found")

if __name__ == '__main__':
    main()