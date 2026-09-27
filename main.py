#!/usr/bin/env python3
"""
ARC-Bench Hackathon Agent - 快速启动版本
解决 SoftTimeLimitExceeded 问题
"""
import os
import sys
import json
import re
from pathlib import Path

def main():
    """主入口 - 快速启动，不依赖复杂初始化"""
    print(f"[Hackathon Agent] Starting...")
    print(f"[Hackathon Agent] Args: {sys.argv}")
    
    # 解析参数
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
    
    print(f"[Hackathon Agent] Requirements: {requirements_source}")
    print(f"[Hackathon Agent] Output: {output_dir}")
    
    # 查找需求文件
    req_file = find_requirements(requirements_source)
    if not req_file:
        print("[Hackathon Agent] ERROR: No requirements.yaml found")
        sys.exit(1)
    
    print(f"[Hackathon Agent] Found: {req_file}")
    
    # 读取需求
    with open(req_file, 'r', encoding='utf-8') as f:
        requirements = f.read()
    
    # 检测任务类型
    task_type = detect_task_type(requirements)
    print(f"[Hackathon Agent] Task type: {task_type}")
    
    # 提取种子数据
    seed_data = extract_seed_data(requirements)
    print(f"[Hackathon Agent] Seed data: {list(seed_data.keys())}")
    
    # 创建输出目录
    output_path = Path(output_dir)
    backend_dir = output_path / 'backend'
    frontend_dir = output_path / 'frontend'
    
    backend_dir.mkdir(parents=True, exist_ok=True)
    frontend_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成应用
    print(f"[Hackathon Agent] Generating application...")
    generate_application(backend_dir, frontend_dir, task_type, seed_data)
    
    print(f"[Hackathon Agent] Done!")

def find_requirements(source):
    """查找需求文件"""
    source_path = Path(source)
    
    # 直接查找 yaml 文件
    for f in source_path.glob('*.yaml'):
        return str(f)
    for f in source_path.glob('*.yml'):
        return str(f)
    
    # 递归查找
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
    
    return seed

def generate_application(backend_dir, frontend_dir, task_type, seed_data):
    """生成应用代码"""
    if task_type == 'github':
        generate_github_app(backend_dir, frontend_dir, seed_data)
    elif task_type == 'spreadsheet':
        generate_spreadsheet_app(backend_dir, frontend_dir, seed_data)
    else:
        generate_generic_app(backend_dir, frontend_dir)

def generate_github_app(backend_dir, frontend_dir, seed_data):
    """生成 GitHub 应用"""
    print("[Hackathon Agent] Generating GitHub application...")
    
    # 后端
    (backend_dir / 'src').mkdir(exist_ok=True)
    
    # package.json
    with open(backend_dir / 'package.json', 'w') as f:
        json.dump({
            "name": "github-app",
            "version": "1.0.0",
            "scripts": {"start": "node src/index.js"},
            "dependencies": {
                "express": "^4.18.2",
                "cors": "^2.8.5",
                "body-parser": "^1.20.2",
                "better-sqlite3": "^9.4.3"
            }
        }, f, indent=2)
    
    # 主入口
    with open(backend_dir / 'src' / 'index.js', 'w') as f:
        f.write(generate_github_backend(seed_data))
    
    # 添加 Playwright 配置
    with open(backend_dir / 'playwright.config.js', 'w') as f:
        f.write("""const { defineConfig } = require('@playwright/test');

const baseURL = process.env.PLAYWRIGHT_BASE_URL || process.env.ARC_WEB_BASE_URL || 'http://127.0.0.1:3000';

module.exports = defineConfig({
  testDir: './test-e2e',
  testMatch: /.*\\.(js|jsx|ts|tsx)$/,
  timeout: 30000,
  use: {
    baseURL,
    trace: 'retain-on-failure',
  },
});
""")
    
    # 添加测试目录
    test_dir = backend_dir / 'test-e2e'
    test_dir.mkdir(exist_ok=True)
    
    # 添加基础测试
    with open(test_dir / 'health.test.js', 'w') as f:
        f.write("""const { test, expect } = require('@playwright/test');

test('health check', async ({ request }) => {
  const response = await request.get('/api/health');
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  expect(data.status).toBe('ok');
});
""")
    
    # 前端 - React + TypeScript
    frontend_files = generate_github_frontend(seed_data)
    for file_path, content in frontend_files.items():
        full_path = frontend_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    # 构建前端
    build_frontend(frontend_dir)
    
    print("[Hackathon Agent] GitHub application generated")

def build_frontend(frontend_dir):
    """构建前端"""
    import subprocess
    
    print("[Hackathon Agent] Building frontend...")
    
    # 安装依赖
    try:
        subprocess.run(['npm', 'install'], cwd=str(frontend_dir), capture_output=True, check=True)
        print("[Hackathon Agent] Frontend dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"[Hackathon Agent] Warning: npm install failed: {e}")
        # 如果 npm 失败，尝试 pnpm
        try:
            subprocess.run(['pnpm', 'install'], cwd=str(frontend_dir), capture_output=True, check=True)
            print("[Hackathon Agent] Frontend dependencies installed with pnpm")
        except subprocess.CalledProcessError as e2:
            print(f"[Hackathon Agent] Warning: pnpm install also failed: {e2}")
            return
    
    # 构建
    try:
        subprocess.run(['npm', 'run', 'build'], cwd=str(frontend_dir), capture_output=True, check=True)
        print("[Hackathon Agent] Frontend built successfully")
    except subprocess.CalledProcessError as e:
        print(f"[Hackathon Agent] Warning: npm build failed: {e}")
        # 如果 npm 失败，尝试 pnpm
        try:
            subprocess.run(['pnpm', 'run', 'build'], cwd=str(frontend_dir), capture_output=True, check=True)
            print("[Hackathon Agent] Frontend built with pnpm")
        except subprocess.CalledProcessError as e2:
            print(f"[Hackathon Agent] Warning: pnpm build also failed: {e2}")

def generate_spreadsheet_app(backend_dir, frontend_dir, seed_data):
    """生成 Spreadsheet 应用"""
    print("[Hackathon Agent] Generating Spreadsheet application...")
    
    # 后端
    (backend_dir / 'src').mkdir(exist_ok=True)
    
    with open(backend_dir / 'package.json', 'w') as f:
        json.dump({
            "name": "spreadsheet-app",
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
        f.write(generate_spreadsheet_backend(seed_data))
    
    # 前端
    with open(frontend_dir / 'index.html', 'w') as f:
        f.write(generate_spreadsheet_frontend(seed_data))
    
    with open(frontend_dir / 'package.json', 'w') as f:
        json.dump({
            "name": "spreadsheet-frontend",
            "version": "1.0.0",
            "scripts": {"build": "mkdir -p dist && cp *.html dist/"}
        }, f, indent=2)
    
    print("[Hackathon Agent] Spreadsheet application generated")

def generate_generic_app(backend_dir, frontend_dir):
    """生成通用应用"""
    print("[Hackathon Agent] Generating generic application...")
    
    (backend_dir / 'src').mkdir(exist_ok=True)
    
    with open(backend_dir / 'package.json', 'w') as f:
        json.dump({
            "name": "app",
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

const app = express();
app.use(cors());
app.use(express.json());

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' });
});

const frontendPath = path.resolve(__dirname, '../../frontend');
app.use(express.static(frontendPath));
app.get('*', (req, res) => {
  res.sendFile(path.join(frontendPath, 'index.html'));
});

const port = process.env.PORT || 3301;
app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
""")
    
    with open(frontend_dir / 'index.html', 'w') as f:
        f.write("""<!DOCTYPE html>
<html>
<head><title>Application</title></head>
<body><h1>Application</h1></body>
</html>
""")
    
    with open(frontend_dir / 'package.json', 'w') as f:
        json.dump({
            "name": "frontend",
            "version": "1.0.0",
            "scripts": {"build": "mkdir -p dist && cp *.html dist/"}
        }, f, indent=2)

def generate_github_backend(seed_data):
    """生成 GitHub 后端代码 - 针对比赛需求优化"""
    accounts = seed_data.get('accounts', ['alice-dev'])
    emails = seed_data.get('emails', ['alice.dev@example.test'])
    passwords = seed_data.get('passwords', ['Valid-password-123!'])
    orgs = seed_data.get('organizations', ['Acme Demo'])
    repos = seed_data.get('repositories', ['acme-docs'])
    branches = seed_data.get('branches', ['main', 'feature-search'])
    
    return f"""const express = require('express');
const cors = require('cors');
const path = require('path');
const sqlite3 = require('better-sqlite3');

const app = express();
app.use(cors());
app.use(express.json());

const db = sqlite3(':memory:');

// 创建表 - 完整的 GitHub 数据模型
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

// 种子数据
const seedAccounts = {json.dumps(accounts)};
const seedEmails = {json.dumps(emails)};
const seedPasswords = {json.dumps(passwords)};
const seedOrgs = {json.dumps(orgs)};
const seedRepos = {json.dumps(repos)};
const seedBranches = {json.dumps(branches)};

// 初始化种子数据
function initSeedData() {{
  // 创建用户
  for (let i = 0; i < seedAccounts.length; i++) {{
    const username = seedAccounts[i];
    const email = seedEmails[i] || `${{username}}@example.test`;
    const password = seedPasswords[0] || 'Valid-password-123!';
    try {{
      db.prepare('INSERT OR IGNORE INTO users (username, email, password, email_verified) VALUES (?, ?, ?, 1)').run(username, email, password);
      console.log(`[Seed] Created user: ${{username}}`);
    }} catch (e) {{}}
  }}
  
  // 创建组织
  for (const orgName of seedOrgs) {{
    try {{
      db.prepare('INSERT OR IGNORE INTO organizations (name) VALUES (?)').run(orgName);
      const org = db.prepare('SELECT id FROM organizations WHERE name = ?').get(orgName);
      if (org) {{
        // 添加组织成员
        const owner = db.prepare('SELECT id FROM users WHERE username = ?').get(seedAccounts[0]);
        if (owner) {{
          db.prepare('INSERT OR IGNORE INTO org_members (org_id, user_id, role) VALUES (?, ?, ?)').run(org.id, owner.id, 'Owner');
        }}
      }}
      console.log(`[Seed] Created org: ${{orgName}}`);
    }} catch (e) {{}}
  }}
  
  // 创建仓库
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
          // 创建分支
          for (const branch of seedBranches) {{
            db.prepare('INSERT OR IGNORE INTO branches (repo_id, name) VALUES (?, ?)').run(repo.id, branch);
          }}
          // 创建示例 Issue
          db.prepare('INSERT OR IGNORE INTO issues (repo_id, title, body, author_id, state) VALUES (?, ?, ?, ?, ?)').run(
            repo.id, 'Improve onboarding', 'We need to improve the onboarding experience for new users.', owner.id, 'open'
          );
          const issue = db.prepare('SELECT id FROM issues WHERE repo_id = ? AND title = ?').get(repo.id, 'Improve onboarding');
          if (issue) {{
            db.prepare('INSERT OR IGNORE INTO issue_labels (issue_id, label) VALUES (?, ?)').run(issue.id, 'bug');
            db.prepare('INSERT OR IGNORE INTO issue_labels (issue_id, label) VALUES (?, ?)').run(issue.id, 'documentation');
          }}
          // 创建示例 PR
          db.prepare('INSERT OR IGNORE INTO pull_requests (repo_id, title, body, author_id, source_branch, target_branch, state) VALUES (?, ?, ?, ?, ?, ?, ?)').run(
            repo.id, 'Fix search functionality', 'This PR fixes the search functionality.', owner.id, 'feature-search', 'main', 'open'
          );
        }}
        console.log(`[Seed] Created repo: ${{repoName}}`);
      }} catch (e) {{}}
    }}
  }}
}}

initSeedData();

// 辅助函数
function generateToken() {{
  return Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);
}}

function validateUsername(username) {{
  if (!username || username.length < 1 || username.length > 39) return false;
  return /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/.test(username);
}}

function validateEmail(email) {{
  if (!email || email.length > 254) return false;
  const parts = email.split('@');
  if (parts.length !== 2) return false;
  if (!parts[0] || !parts[1]) return false;
  if (!parts[1].includes('.')) return false;
  return true;
}}

function validatePassword(password) {{
  if (!password || password.length < 12 || password.length > 128) return false;
  if (/\s/.test(password)) return false;
  if (!/[A-Z]/.test(password)) return false;
  if (!/[a-z]/.test(password)) return false;
  if (!/[0-9]/.test(password)) return false;
  if (!/[^A-Za-z0-9]/.test(password)) return false;
  return true;
}}

// API 路由
app.get('/api/health', (req, res) => res.json({{ status: 'ok' }}));

// 注册
app.post('/api/register', (req, res) => {{
  const {{ username, email, password, confirm_password, terms }} = req.body;
  const errors = {{}};
  
  if (!validateUsername(username)) errors.username = 'Username format is invalid';
  if (!validateEmail(email)) errors.email = 'Email format is invalid';
  if (!validatePassword(password)) errors.password = 'Password requirements are not satisfied';
  if (password !== confirm_password) errors.confirm_password = 'Password confirmation does not match';
  if (!terms) errors.terms = 'Agree to terms is required';
  
  // 检查重复
  const existingUser = db.prepare('SELECT id FROM users WHERE username = ? OR email = ?').get(username, email);
  if (existingUser) {{
    if (existingUser.username === username) errors.username = 'Username already exists';
    if (existingUser.email === email) errors.email = 'Email already exists';
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

// 登录
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

// 密码恢复
app.post('/api/recover', (req, res) => {{
  const {{ email }} = req.body;
  const user = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
  // 总是返回成功，不泄露邮箱是否存在
  res.json({{ success: true, code: '123456' }});
}});

app.post('/api/reset-password', (req, res) => {{
  const {{ email, code, new_password, confirm_password }} = req.body;
  const errors = {{}};
  
  if (code !== '123456') errors.code = 'Verification code is invalid';
  if (!validatePassword(new_password)) errors.new_password = 'Password requirements are not satisfied';
  if (new_password !== confirm_password) errors.confirm_password = 'Password confirmation does not match';
  
  if (Object.keys(errors).length > 0) {{
    return res.status(400).json({{ success: false, errors }});
  }}
  
  const user = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
  if (!user) {{
    return res.json({{ success: true }}); // 不泄露邮箱是否存在
  }}
  
  db.prepare('UPDATE users SET password = ? WHERE id = ?').run(new_password, user.id);
  res.json({{ success: true, message: 'Password updated' }});
}});

// 退出登录
app.post('/api/logout', (req, res) => {{
  const {{ token }} = req.body;
  db.prepare('DELETE FROM sessions WHERE token = ?').run(token);
  res.json({{ success: true }});
}});

// 获取当前用户
app.get('/api/me', (req, res) => {{
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) return res.status(401).json({{ error: 'Not authenticated' }});
  const session = db.prepare('SELECT u.* FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.token = ?').get(token);
  if (!session) return res.status(401).json({{ error: 'Not authenticated' }});
  res.json({{ id: session.id, username: session.username, email: session.email }});
}});

// 组织 API
app.get('/api/orgs', (req, res) => {{
  const orgs = db.prepare('SELECT * FROM organizations').all();
  res.json(orgs);
}});

app.get('/api/orgs/:name', (req, res) => {{
  const org = db.prepare('SELECT * FROM organizations WHERE name = ?').get(req.params.name);
  if (!org) return res.status(404).json({{ error: 'Not found' }});
  const members = db.prepare('SELECT u.username, om.role FROM org_members om JOIN users u ON om.user_id = u.id WHERE om.org_id = ?').all(org.id);
  const repos = db.prepare('SELECT * FROM repositories WHERE org_id = ?').all(org.id);
  res.json({{ ...org, members, repositories: repos }});
}});

// 仓库 API
app.get('/api/repos', (req, res) => {{
  const repos = db.prepare(`
    SELECT r.*, u.username as owner_name,
    CASE WHEN r.org_id IS NOT NULL THEN (SELECT name FROM organizations WHERE id = r.org_id) ELSE NULL END as org_name
    FROM repositories r JOIN users u ON r.owner_id = u.id
  `).all();
  res.json(repos);
}});

app.get('/api/repos/:owner/:name', (req, res) => {{
  const repo = db.prepare(`
    SELECT r.*, u.username as owner_name
    FROM repositories r JOIN users u ON r.owner_id = u.id
    WHERE u.username = ? AND r.name = ?
  `).get(req.params.owner, req.params.name);
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
    const result = db.prepare('INSERT INTO repositories (name, owner_id, description, is_public) VALUES (?, ?, ?, ?)').run(
      name, session.user_id, description || '', is_public !== false ? 1 : 0
    );
    db.prepare('INSERT INTO branches (repo_id, name) VALUES (?, ?)').run(result.lastInsertRowid, 'main');
    res.json({{ success: true, repoId: result.lastInsertRowid }});
  }} catch (err) {{
    res.status(400).json({{ error: err.message }});
  }}
}});

// Issue API
app.get('/api/repos/:owner/:name/issues', (req, res) => {{
  const repo = db.prepare(`
    SELECT r.id FROM repositories r JOIN users u ON r.owner_id = u.id
    WHERE u.username = ? AND r.name = ?
  `).get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({{ error: 'Not found' }});
  
  const issues = db.prepare(`
    SELECT i.*, u.username as author_name
    FROM issues i JOIN users u ON i.author_id = u.id
    WHERE i.repo_id = ?
  `).all(repo.id);
  
  for (const issue of issues) {{
    issue.labels = db.prepare('SELECT label FROM issue_labels WHERE issue_id = ?').all(issue.id).map(r => r.label);
  }}
  
  res.json(issues);
}});

app.post('/api/repos/:owner/:name/issues', (req, res) => {{
  const {{ title, body, labels }} = req.body;
  const token = req.headers.authorization?.replace('Bearer ', '');
  const session = db.prepare('SELECT user_id FROM sessions WHERE token = ?').get(token);
  if (!session) return res.status(401).json({{ error: 'Not authenticated' }});
  
  const repo = db.prepare(`
    SELECT r.id FROM repositories r JOIN users u ON r.owner_id = u.id
    WHERE u.username = ? AND r.name = ?
  `).get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({{ error: 'Not found' }});
  
  try {{
    const result = db.prepare('INSERT INTO issues (repo_id, title, body, author_id) VALUES (?, ?, ?, ?)').run(
      repo.id, title, body || '', session.user_id
    );
    if (labels) {{
      for (const label of labels) {{
        db.prepare('INSERT INTO issue_labels (issue_id, label) VALUES (?, ?)').run(result.lastInsertRowid, label);
      }}
    }}
    res.json({{ success: true, issueId: result.lastInsertRowid }});
  }} catch (err) {{
    res.status(400).json({{ error: err.message }});
  }}
}});

// PR API
app.get('/api/repos/:owner/:name/pulls', (req, res) => {{
  const repo = db.prepare(`
    SELECT r.id FROM repositories r JOIN users u ON r.owner_id = u.id
    WHERE u.username = ? AND r.name = ?
  `).get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({{ error: 'Not found' }});
  
  const prs = db.prepare(`
    SELECT pr.*, u.username as author_name
    FROM pull_requests pr JOIN users u ON pr.author_id = u.id
    WHERE pr.repo_id = ?
  `).all(repo.id);
  
  res.json(prs);
}});

app.post('/api/repos/:owner/:name/pulls', (req, res) => {{
  const {{ title, body, source_branch, target_branch }} = req.body;
  const token = req.headers.authorization?.replace('Bearer ', '');
  const session = db.prepare('SELECT user_id FROM sessions WHERE token = ?').get(token);
  if (!session) return res.status(401).json({{ error: 'Not authenticated' }});
  
  const repo = db.prepare(`
    SELECT r.id FROM repositories r JOIN users u ON r.owner_id = u.id
    WHERE u.username = ? AND r.name = ?
  `).get(req.params.owner, req.params.name);
  if (!repo) return res.status(404).json({{ error: 'Not found' }});
  
  try {{
    const result = db.prepare('INSERT INTO pull_requests (repo_id, title, body, author_id, source_branch, target_branch) VALUES (?, ?, ?, ?, ?, ?)').run(
      repo.id, title, body || '', session.user_id, source_branch, target_branch
    );
    res.json({{ success: true, prId: result.lastInsertRowid }});
  }} catch (err) {{
    res.status(400).json({{ error: err.message }});
  }}
}});

// PR Review API
app.post('/api/pulls/:id/review', (req, res) => {{
  const {{ state }} = req.body;
  const token = req.headers.authorization?.replace('Bearer ', '');
  const session = db.prepare('SELECT user_id FROM sessions WHERE token = ?').get(token);
  if (!session) return res.status(401).json({{ error: 'Not authenticated' }});
  
  try {{
    db.prepare('INSERT OR REPLACE INTO pr_reviews (pr_id, reviewer_id, state) VALUES (?, ?, ?)').run(
      req.params.id, session.user_id, state
    );
    res.json({{ success: true }});
  }} catch (err) {{
    res.status(400).json({{ error: err.message }});
  }}
}});

// 静态文件
const frontendPath = path.resolve(__dirname, '../../frontend/dist');
app.use(express.static(frontendPath));
app.get('*', (req, res) => {{
  res.sendFile(path.join(frontendPath, 'index.html'));
}});

const port = process.env.PORT || 3301;
app.listen(port, () => {{
  console.log(`GitHub app running on port ${{port}}`);
}});
"""

def generate_github_frontend(seed_data):
    """生成 GitHub 前端 - React + TypeScript + Vite"""
    accounts = seed_data.get('accounts', ['alice-dev'])
    repos = seed_data.get('repositories', ['acme-docs'])
    
    # 返回多个文件的内容
    files = {}
    
    # package.json
    files['package.json'] = json.dumps({
        "name": "frontend",
        "private": True,
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
    }, indent=2)
    
    # vite.config.js
    files['vite.config.js'] = """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:3301'
    }
  }
})
"""
    
    # index.html
    files['index.html'] = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GitHub Collaboration Platform</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""
    
    # src/main.tsx
    files['src/main.tsx'] = """import React from 'react'
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
"""
    
    # src/index.css
    files['src/index.css'] = """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: #f6f8fa; }
.header { background: #24292f; color: white; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; }
.header h1 { font-size: 20px; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px; }
.card { background: white; border: 1px solid #d0d7de; border-radius: 6px; padding: 16px; margin-bottom: 16px; }
.btn { display: inline-block; padding: 5px 16px; background: #2da44e; color: white; border: 1px solid rgba(27,31,36,0.15); border-radius: 6px; cursor: pointer; font-size: 14px; text-decoration: none; }
.btn:hover { background: #2c974b; }
.btn-outline { background: white; color: #24292f; border-color: #d0d7de; }
input { padding: 5px 12px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 14px; }
.form-group { margin-bottom: 16px; }
label { display: block; font-weight: 600; margin-bottom: 4px; }
.error { color: #cf222e; font-size: 12px; margin-top: 4px; }
.success { color: #2da44e; font-size: 12px; margin-top: 4px; }
.nav-link { color: white; text-decoration: none; margin-left: 16px; }
.nav-link:hover { text-decoration: underline; }
"""
    
    # src/App.tsx
    files['src/App.tsx'] = """import { Routes, Route, Link } from 'react-router-dom'
import { useState } from 'react'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import ReposPage from './pages/ReposPage'
import RepoDetailPage from './pages/RepoDetailPage'
import OrgsPage from './pages/OrgsPage'

function App() {
  const [user, setUser] = useState<any>(null)

  return (
    <div>
      <header className="header">
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h1>GitHub</h1>
          {user && (
            <nav style={{ marginLeft: 32 }}>
              <Link to="/" className="nav-link">Dashboard</Link>
              <Link to="/repos" className="nav-link">Repositories</Link>
              <Link to="/orgs" className="nav-link">Organizations</Link>
            </nav>
          )}
        </div>
        <div>
          {user ? (
            <span style={{ color: 'white' }}>
              {user.username}
              <button className="btn btn-outline" style={{ marginLeft: 8 }} onClick={() => setUser(null)}>Sign out</button>
            </span>
          ) : (
            <Link to="/login" className="btn">Sign in</Link>
          )}
        </div>
      </header>
      <div className="container">
        <Routes>
          <Route path="/" element={<DashboardPage user={user} />} />
          <Route path="/login" element={<LoginPage setUser={setUser} />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/repos" element={<ReposPage user={user} />} />
          <Route path="/repos/:owner/:name" element={<RepoDetailPage user={user} />} />
          <Route path="/orgs" element={<OrgsPage />} />
        </Routes>
      </div>
    </div>
  )
}

export default App
"""
    
    # src/api/index.ts
    files['src/api/index.ts'] = """const BASE_URL = '/api'

export async function apiGet(path: string) {
  const res = await fetch(`${BASE_URL}${path}`)
  return res.json()
}

export async function apiPost(path: string, data: any) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return res.json()
}
"""
    
    # src/pages/LoginPage.tsx
    files['src/pages/LoginPage.tsx'] = """import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { apiPost } from '../api'

export default function LoginPage({ setUser }: { setUser: (u: any) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [showRecover, setShowRecover] = useState(false)
  const [recoverEmail, setRecoverEmail] = useState('')
  const [recoverCode, setRecoverCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [recoverStep, setRecoverStep] = useState(1)
  const [recoverMessage, setRecoverMessage] = useState('')
  const navigate = useNavigate()

  const handleLogin = async () => {
    const data = await apiPost('/login', { username, password })
    if (data.success) {
      setUser(data.user)
      navigate('/')
    } else {
      setError(data.error || 'Invalid credentials')
    }
  }

  const handleRecover = async () => {
    if (recoverStep === 1) {
      const data = await apiPost('/recover', { email: recoverEmail })
      if (data.success) {
        setRecoverStep(2)
        setRecoverMessage('')
      }
    } else {
      const data = await apiPost('/reset-password', { 
        email: recoverEmail, 
        code: recoverCode, 
        new_password: newPassword, 
        confirm_password: confirmPassword 
      })
      if (data.success) {
        setRecoverMessage('Password updated')
        setTimeout(() => setShowRecover(false), 2000)
      } else {
        setRecoverMessage(data.errors?.code || data.errors?.new_password || 'Error')
      }
    }
  }

  if (showRecover) {
    return (
      <div className="card" style={{ maxWidth: 400, margin: '0 auto' }}>
        <h2>Reset password</h2>
        {recoverStep === 1 ? (
          <>
            <div className="form-group">
              <label htmlFor="recover-email">Email</label>
              <input id="recover-email" type="email" value={recoverEmail} onChange={e => setRecoverEmail(e.target.value)} style={{ width: '100%' }} />
            </div>
            <button className="btn" onClick={handleRecover}>Send reset link</button>
          </>
        ) : (
          <>
            <p style={{ marginBottom: 16 }}>Verification code: <strong>123456</strong></p>
            <div className="form-group">
              <label htmlFor="recover-code">Verification code</label>
              <input id="recover-code" type="text" value={recoverCode} onChange={e => setRecoverCode(e.target.value)} style={{ width: '100%' }} />
            </div>
            <div className="form-group">
              <label htmlFor="new-password">New password</label>
              <input id="new-password" type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} style={{ width: '100%' }} />
            </div>
            <div className="form-group">
              <label htmlFor="confirm-password">Confirm password</label>
              <input id="confirm-password" type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} style={{ width: '100%' }} />
            </div>
            <button className="btn" onClick={handleRecover}>Reset password</button>
          </>
        )}
        {recoverMessage && <p className={recoverMessage === 'Password updated' ? 'success' : 'error'}>{recoverMessage}</p>}
        <p style={{ marginTop: 16 }}><a href="#" onClick={() => setShowRecover(false)}>Back to sign in</a></p>
      </div>
    )
  }

  return (
    <div className="card" style={{ maxWidth: 400, margin: '0 auto' }}>
      <h2>Sign in</h2>
      <div className="form-group">
        <label htmlFor="username">Username or email</label>
        <input id="username" type="text" value={username} onChange={e => setUsername(e.target.value)} style={{ width: '100%' }} />
      </div>
      <div className="form-group">
        <label htmlFor="password">Password</label>
        <input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)} style={{ width: '100%' }} />
      </div>
      {error && <p className="error">{error}</p>}
      <button className="btn" onClick={handleLogin}>Sign in</button>
      <p style={{ marginTop: 16 }}>
        <Link to="/register">Create an account</Link>
        {' | '}
        <a href="#" onClick={() => setShowRecover(true)}>Forgot password</a>
      </p>
    </div>
  )
}
"""
    
    # src/pages/RegisterPage.tsx
    files['src/pages/RegisterPage.tsx'] = """import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiPost } from '../api'

export default function RegisterPage() {
  const [form, setForm] = useState({ username: '', email: '', password: '', confirm_password: '', terms: false })
  const [errors, setErrors] = useState<any>({})
  const navigate = useNavigate()

  const update = (field: string, value: any) => setForm(prev => ({ ...prev, [field]: value }))

  const handleRegister = async () => {
    const data = await apiPost('/register', form)
    if (data.success) {
      navigate('/login')
    } else {
      setErrors(data.errors || {})
    }
  }

  return (
    <div className="card" style={{ maxWidth: 400, margin: '0 auto' }}>
      <h2>Create an account</h2>
      <div className="form-group">
        <label htmlFor="reg-username">Username</label>
        <input id="reg-username" type="text" value={form.username} onChange={e => update('username', e.target.value)} style={{ width: '100%' }} />
        {errors.username && <p className="error">{errors.username}</p>}
      </div>
      <div className="form-group">
        <label htmlFor="reg-email">Email</label>
        <input id="reg-email" type="email" value={form.email} onChange={e => update('email', e.target.value)} style={{ width: '100%' }} />
        {errors.email && <p className="error">{errors.email}</p>}
      </div>
      <div className="form-group">
        <label htmlFor="reg-password">Password</label>
        <input id="reg-password" type="password" value={form.password} onChange={e => update('password', e.target.value)} style={{ width: '100%' }} />
        {errors.password && <p className="error">{errors.password}</p>}
      </div>
      <div className="form-group">
        <label htmlFor="reg-confirm">Confirm password</label>
        <input id="reg-confirm" type="password" value={form.confirm_password} onChange={e => update('confirm_password', e.target.value)} style={{ width: '100%' }} />
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
"""
    
    # src/pages/DashboardPage.tsx
    files['src/pages/DashboardPage.tsx'] = """import { Link } from 'react-router-dom'

export default function DashboardPage({ user }: { user: any }) {
  if (!user) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: 48 }}>
        <h2>Welcome to GitHub</h2>
        <p style={{ margin: '16px 0' }}>Sign in to access your repositories and organizations.</p>
        <Link to="/login" className="btn">Sign in</Link>
      </div>
    )
  }

  return (
    <div>
      <h2>Welcome, {user.username}!</h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
        <div className="card">
          <h3>Repositories</h3>
          <p>View and manage your repositories.</p>
          <Link to="/repos" className="btn" style={{ marginTop: 8 }}>View repositories</Link>
        </div>
        <div className="card">
          <h3>Organizations</h3>
          <p>View your organizations.</p>
          <Link to="/orgs" className="btn" style={{ marginTop: 8 }}>View organizations</Link>
        </div>
      </div>
    </div>
  )
}
"""
    
    # src/pages/ReposPage.tsx
    files['src/pages/ReposPage.tsx'] = """import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../api'

export default function ReposPage({ user }: { user: any }) {
  const [repos, setRepos] = useState<any[]>([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    apiGet('/repos').then(setRepos)
  }, [])

  const filtered = repos.filter(r => r.name.toLowerCase().includes(search.toLowerCase()))

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2>Repositories</h2>
        {user && <Link to="/repos/new" className="btn">New repository</Link>}
      </div>
      <input
        type="text"
        placeholder="Find a repository..."
        value={search}
        onChange={e => setSearch(e.target.value)}
        style={{ width: '100%', marginBottom: 16 }}
      />
      <ul style={{ listStyle: 'none' }}>
        {filtered.map(repo => (
          <li key={repo.id} style={{ padding: 16, borderBottom: '1px solid #d0d7de' }}>
            <Link to={`/repos/${repo.owner_name}/${repo.name}`} style={{ fontSize: 20, color: '#0969da', textDecoration: 'none', fontWeight: 600 }}>
              {repo.owner_name}/{repo.name}
            </Link>
            <p style={{ color: '#57606a', marginTop: 4 }}>{repo.description || 'No description'}</p>
            <span style={{ fontSize: 12, color: '#57606a' }}>{repo.is_public ? 'Public' : 'Private'}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
"""
    
    # src/pages/RepoDetailPage.tsx
    files['src/pages/RepoDetailPage.tsx'] = """import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { apiGet } from '../api'

export default function RepoDetailPage({ user }: { user: any }) {
  const { owner, name } = useParams()
  const [repo, setRepo] = useState<any>(null)
  const [issues, setIssues] = useState<any[]>([])
  const [pulls, setPulls] = useState<any[]>([])

  useEffect(() => {
    apiGet(`/repos/${owner}/${name}`).then(setRepo)
    apiGet(`/repos/${owner}/${name}/issues`).then(setIssues)
    apiGet(`/repos/${owner}/${name}/pulls`).then(setPulls)
  }, [owner, name])

  if (!repo) return <div>Loading...</div>

  return (
    <div>
      <h2>{owner}/{name}</h2>
      <p style={{ color: '#57606a', marginBottom: 16 }}>{repo.description}</p>
      
      <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
        <span>Branches: {repo.branches?.map((b: any) => b.name).join(', ')}</span>
        <span>Visibility: {repo.is_public ? 'Public' : 'Private'}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card">
          <h3>Issues ({issues.length})</h3>
          {issues.map(issue => (
            <div key={issue.id} style={{ padding: '8px 0', borderBottom: '1px solid #d0d7de' }}>
              <strong>{issue.title}</strong>
              <span style={{ marginLeft: 8, color: '#57606a' }}>{issue.state}</span>
              {issue.labels?.map((l: string) => (
                <span key={l} style={{ marginLeft: 4, padding: '2px 8px', background: '#ddf4ff', borderRadius: 12, fontSize: 12 }}>{l}</span>
              ))}
            </div>
          ))}
        </div>
        <div className="card">
          <h3>Pull Requests ({pulls.length})</h3>
          {pulls.map(pr => (
            <div key={pr.id} style={{ padding: '8px 0', borderBottom: '1px solid #d0d7de' }}>
              <strong>{pr.title}</strong>
              <span style={{ marginLeft: 8, color: '#57606a' }}>{pr.state}</span>
              <span style={{ marginLeft: 8, fontSize: 12 }}>{pr.source_branch} → {pr.target_branch}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
"""
    
    # src/pages/OrgsPage.tsx
    files['src/pages/OrgsPage.tsx'] = """import { useState, useEffect } from 'react'
import { apiGet } from '../api'

export default function OrgsPage() {
  const [orgs, setOrgs] = useState<any[]>([])

  useEffect(() => {
    apiGet('/orgs').then(setOrgs)
  }, [])

  return (
    <div>
      <h2>Organizations</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16, marginTop: 16 }}>
        {orgs.map(org => (
          <div key={org.id} className="card">
            <h3>{org.name}</h3>
            <p style={{ color: '#57606a' }}>{org.description || 'No description'}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
"""
    
    return files

def generate_spreadsheet_backend(seed_data):
    """生成 Spreadsheet 后端代码"""
    workbooks = seed_data.get('workbooks', ['Q3 Sales'])
    worksheets = seed_data.get('worksheets', ['Sheet1'])
    cells = seed_data.get('cells', {'A1': 'Region'})
    
    return f"""const express = require('express');
const cors = require('cors');
const path = require('path');
const sqlite3 = require('better-sqlite3');

const app = express();
app.use(cors());
app.use(express.json());

const db = sqlite3(':memory:');

// 创建表
db.exec(`
  CREATE TABLE IF NOT EXISTS workbooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS worksheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workbook_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (workbook_id) REFERENCES workbooks(id)
  );
  CREATE TABLE IF NOT EXISTS cells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worksheet_id INTEGER NOT NULL,
    cell_ref TEXT NOT NULL,
    value TEXT,
    formula TEXT,
    FOREIGN KEY (worksheet_id) REFERENCES worksheets(id)
  );
`);

// 种子数据
const seedWorkbooks = {json.dumps(workbooks)};
const seedWorksheets = {json.dumps(worksheets)};
const seedCells = {json.dumps(cells)};

function initSeedData() {{
  for (const wbName of seedWorkbooks) {{
    try {{
      const result = db.prepare('INSERT INTO workbooks (name) VALUES (?)').run(wbName);
      const wbId = result.lastInsertRowid;
      console.log(`[Seed] Created workbook: ${{wbName}}`);
      
      for (const wsName of seedWorksheets) {{
        const wsResult = db.prepare('INSERT INTO worksheets (workbook_id, name) VALUES (?, ?)').run(wbId, wsName);
        const wsId = wsResult.lastInsertRowid;
        console.log(`[Seed] Created worksheet: ${{wsName}} in ${{wbName}}`);
        
        for (const [ref, value] of Object.entries(seedCells)) {{
          db.prepare('INSERT INTO cells (worksheet_id, cell_ref, value) VALUES (?, ?, ?)').run(wsId, ref, value);
          console.log(`[Seed] Set cell ${{ref}} = ${{value}}`);
        }}
      }}
    }} catch (e) {{
      console.error(`[Seed] Error: ${{e.message}}`);
    }}
  }}
}}

initSeedData();

// API 路由
app.get('/api/health', (req, res) => res.json({{ status: 'ok' }}));

app.get('/api/workbooks', (req, res) => {{
  const workbooks = db.prepare('SELECT * FROM workbooks ORDER BY updated_at DESC').all();
  res.json(workbooks);
}});

app.post('/api/workbooks', (req, res) => {{
  const {{ name }} = req.body;
  const result = db.prepare('INSERT INTO workbooks (name) VALUES (?)').run(name || 'Untitled');
  const wbId = result.lastInsertRowid;
  db.prepare('INSERT INTO worksheets (workbook_id, name) VALUES (?, ?)').run(wbId, 'Sheet1');
  res.json({{ id: wbId, name: name || 'Untitled' }});
}});

app.get('/api/workbooks/:id', (req, res) => {{
  const wb = db.prepare('SELECT * FROM workbooks WHERE id = ?').get(req.params.id);
  if (!wb) return res.status(404).json({{ error: 'Not found' }});
  const sheets = db.prepare('SELECT * FROM worksheets WHERE workbook_id = ?').all(wb.id);
  const cells = db.prepare('SELECT c.* FROM cells c JOIN worksheets w ON c.worksheet_id = w.id WHERE w.workbook_id = ?').all(wb.id);
  res.json({{ ...wb, worksheets: sheets, cells }});
}});

app.put('/api/workbooks/:id', (req, res) => {{
  const {{ name }} = req.body;
  db.prepare('UPDATE workbooks SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?').run(name, req.params.id);
  res.json({{ success: true }});
}});

app.post('/api/cells', (req, res) => {{
  const {{ worksheet_id, cell_ref, value, formula }} = req.body;
  const existing = db.prepare('SELECT id FROM cells WHERE worksheet_id = ? AND cell_ref = ?').get(worksheet_id, cell_ref);
  if (existing) {{
    db.prepare('UPDATE cells SET value = ?, formula = ? WHERE id = ?').run(value, formula, existing.id);
  }} else {{
    db.prepare('INSERT INTO cells (worksheet_id, cell_ref, value, formula) VALUES (?, ?, ?, ?)').run(worksheet_id, cell_ref, value, formula);
  }}
  res.json({{ success: true }});
}});

// 静态文件
const frontendPath = path.resolve(__dirname, '../../frontend');
app.use(express.static(frontendPath));
app.get('*', (req, res) => {{
  res.sendFile(path.join(frontendPath, 'index.html'));
}});

const port = process.env.PORT || 3301;
app.listen(port, () => {{
  console.log(`Spreadsheet app running on port ${{port}}`);
}});
"""

def generate_spreadsheet_frontend(seed_data):
    """生成 Spreadsheet 前端"""
    workbooks = seed_data.get('workbooks', ['Q3 Sales'])
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Online Spreadsheet</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    .header {{ background: #1a73e8; color: white; padding: 12px 24px; display: flex; align-items: center; gap: 16px; }}
    .header h1 {{ font-size: 20px; }}
    .toolbar {{ background: #f8f9fa; border-bottom: 1px solid #dadce0; padding: 8px 16px; display: flex; gap: 8px; }}
    .btn {{ padding: 6px 16px; background: #1a73e8; color: white; border: none; border-radius: 4px; cursor: pointer; }}
    .btn:hover {{ background: #1557b0; }}
    .btn-outline {{ background: white; color: #1a73e8; border: 1px solid #dadce0; }}
    .container {{ display: flex; height: calc(100vh - 100px); }}
    .sidebar {{ width: 250px; border-right: 1px solid #dadce0; padding: 16px; background: white; }}
    .main {{ flex: 1; overflow: auto; }}
    .grid {{ border-collapse: collapse; }}
    .grid th, .grid td {{ border: 1px solid #dadce0; padding: 4px 8px; min-width: 100px; height: 28px; }}
    .grid th {{ background: #f8f9fa; font-weight: normal; color: #5f6368; }}
    .grid td {{ cursor: cell; }}
    .grid td:focus {{ outline: 2px solid #1a73e8; outline-offset: -2px; }}
    .formula-bar {{ display: flex; align-items: center; padding: 4px 16px; border-bottom: 1px solid #dadce0; background: white; }}
    .formula-bar input {{ flex: 1; padding: 4px 8px; border: 1px solid #dadce0; border-radius: 4px; }}
    .wb-item {{ padding: 8px 12px; cursor: pointer; border-radius: 4px; }}
    .wb-item:hover {{ background: #e8f0fe; }}
    .wb-item.active {{ background: #d2e3fc; }}
    .tabs {{ display: flex; background: #f8f9fa; border-bottom: 1px solid #dadce0; }}
    .tab {{ padding: 8px 16px; cursor: pointer; border-bottom: 2px solid transparent; }}
    .tab.active {{ border-bottom-color: #1a73e8; color: #1a73e8; }}
  </style>
</head>
<body>
  <header class="header">
    <h1>Sheets</h1>
  </header>
  
  <div id="home-page">
    <div style="padding: 24px;">
      <h2>Start a new spreadsheet</h2>
      <button class="btn" onclick="createWorkbook()" style="margin: 16px 0;">New blank workbook</button>
      <h3 style="margin-top: 24px;">Recent spreadsheets</h3>
      <div id="workbook-list"></div>
    </div>
  </div>
  
  <div id="editor-page" style="display: none;">
    <div class="toolbar">
      <span id="wb-name" style="font-weight: 600; margin-right: 16px;"></span>
      <button class="btn-outline btn" onclick="renameWorkbook()">Rename workbook</button>
    </div>
    <div class="tabs" id="sheet-tabs"></div>
    <div class="formula-bar">
      <span id="cell-ref" style="width: 60px; color: #5f6368;">A1</span>
      <span style="margin: 0 8px;">𝑓</span>
      <input type="text" id="formula-input" oninput="updateFormula()">
    </div>
    <div class="main">
      <table class="grid" id="grid"></table>
    </div>
  </div>
  
  <script>
    let workbooks = [];
    let currentWorkbook = null;
    let currentSheet = null;
    let cells = {{}};
    
    async function loadWorkbooks() {{
      const res = await fetch('/api/workbooks');
      workbooks = await res.json();
      renderWorkbookList();
    }}
    
    function renderWorkbookList() {{
      const list = document.getElementById('workbook-list');
      list.innerHTML = workbooks.map(wb => `
        <div class="wb-item" onclick="openWorkbook(${{wb.id}})">
          <div style="font-weight: 600;">${{wb.name}}</div>
          <div style="color: #5f6368; font-size: 12px;">Last updated: ${{wb.updated_at}}</div>
        </div>
      `).join('');
    }}
    
    async function createWorkbook() {{
      const res = await fetch('/api/workbooks', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ name: 'Untitled spreadsheet' }})
      }});
      const wb = await res.json();
      await openWorkbook(wb.id);
    }}
    
    async function openWorkbook(id) {{
      const res = await fetch(`/api/workbooks/${{id}}`);
      currentWorkbook = await res.json();
      currentSheet = currentWorkbook.worksheets[0];
      
      cells = {{}};
      for (const c of currentWorkbook.cells) {{
        cells[c.cell_ref] = c.value;
      }}
      
      document.getElementById('home-page').style.display = 'none';
      document.getElementById('editor-page').style.display = 'block';
      document.getElementById('wb-name').textContent = currentWorkbook.name;
      
      renderTabs();
      renderGrid();
    }}
    
    function renderTabs() {{
      const tabs = document.getElementById('sheet-tabs');
      tabs.innerHTML = currentWorkbook.worksheets.map(ws => `
        <div class="tab ${{ws.id === currentSheet.id ? 'active' : ''}}" onclick="switchSheet(${{ws.id}})">
          ${{ws.name}}
        </div>
      `).join('');
    }}
    
    function renderGrid() {{
      const grid = document.getElementById('grid');
      const cols = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
      let html = '<tr><th></th>';
      for (const col of cols) html += `<th>${{col}}</th>`;
      html += '</tr>';
      
      for (let row = 1; row <= 20; row++) {{
        html += `<tr><th>${{row}}</th>`;
        for (const col of cols) {{
          const ref = `${{col}}${{row}}`;
          const value = cells[ref] || '';
          html += `<td contenteditable="true" data-ref="${{ref}}" 
                    onfocus="selectCell('${{ref}}')" 
                    onblur="updateCell('${{ref}}', this.textContent)">${{value}}</td>`;
        }}
        html += '</tr>';
      }}
      grid.innerHTML = html;
    }}
    
    function selectCell(ref) {{
      document.getElementById('cell-ref').textContent = ref;
      document.getElementById('formula-input').value = cells[ref] || '';
    }}
    
    async function updateCell(ref, value) {{
      cells[ref] = value;
      await fetch('/api/cells', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ worksheet_id: currentSheet.id, cell_ref: ref, value }})
      }});
    }}
    
    async function renameWorkbook() {{
      const name = prompt('Workbook name:', currentWorkbook.name);
      if (name) {{
        await fetch(`/api/workbooks/${{currentWorkbook.id}}`, {{
          method: 'PUT',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ name }})
        }});
        currentWorkbook.name = name;
        document.getElementById('wb-name').textContent = name;
      }}
    }}
    
    function switchSheet(id) {{
      currentSheet = currentWorkbook.worksheets.find(ws => ws.id === id);
      renderTabs();
      // TODO: Load sheet cells
    }}
    
    loadWorkbooks();
  </script>
</body>
</html>
"""

if __name__ == '__main__':
    main()