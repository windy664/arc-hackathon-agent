#!/usr/bin/env python3
"""
定制版 ARC Agent - 针对比赛需求优化
支持 GitHub 和 Spreadsheet 任务

修复内容：
- P0: 正确的退出码和错误处理
- P1: 移除强制 --clean，支持断点恢复
- P1: 保留图片引用结构
- 新增: 支持种子数据解析和预置
"""
import os
import sys
import glob
import json
import re
import traceback
from pathlib import Path

def main():
    print(f"[ARC-Hackathon] Arguments: {sys.argv}")
    
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
    
    print(f"[ARC-Hackathon] Requirements source: {requirements_source}")
    print(f"[ARC-Hackathon] Output dir: {output_dir}")
    
    # P0: Install dependencies if needed
    install_dependencies()
    
    # Find requirements.yaml
    yaml_files = glob.glob(os.path.join(requirements_source, '*.yaml')) + \
                 glob.glob(os.path.join(requirements_source, '*.yml'))
    
    if not yaml_files:
        for root, dirs, files in os.walk(requirements_source):
            for f in files:
                if f.endswith(('.yaml', '.yml')):
                    yaml_files.append(os.path.join(root, f))
    
    if not yaml_files:
        print(f"[ARC-Hackathon] ERROR: No requirements.yaml found")
        sys.exit(1)
    
    requirement_path = yaml_files[0]
    print(f"[ARC-Hackathon] Found requirements: {requirement_path}")
    
    # 检测任务类型
    task_type = detect_task_type(requirement_path)
    print(f"[ARC-Hackathon] Detected task type: {task_type}")
    
    # 解析种子数据
    seed_data = extract_seed_data(requirement_path)
    if seed_data:
        print(f"[ARC-Hackathon] Found {len(seed_data)} seed data entries")
        save_seed_data(output_dir, seed_data)
    
    # 根据任务类型优化配置
    optimize_for_task(task_type, seed_data)
    
    # Add current directory to Python path
    sys.path.insert(0, os.path.dirname(__file__))
    
    # P1: 检查是否已有输出目录，支持断点恢复
    use_clean = '--clean' in sys.argv
    output_exists = os.path.exists(output_dir) and os.path.exists(os.path.join(output_dir, '.arc', 'processing_queue.json'))
    
    if output_exists and not use_clean:
        print(f"[ARC-Hackathon] Found existing output, resuming...")
        sys.argv = [
            'arc',
            'compile',
            requirement_path,
            '-o', output_dir,
            '--type', 'web',
            '--resume',
            '--port', '3301'
        ]
    else:
        sys.argv = [
            'arc',
            'compile',
            requirement_path,
            '-o', output_dir,
            '--type', 'web',
            '--clean',
            '--port', '3301'
        ]
    
    print(f"[ARC-Hackathon] Running ARC with: {sys.argv}")
    
    # Import and run ARC with error handling
    try:
        from arc_main import main as arc_main
        exit_code = arc_main()
        
        # P0: 检查退出码
        if exit_code is not None and exit_code != 0:
            print(f"[ARC-Hackathon] ARC exited with code: {exit_code}")
            sys.exit(exit_code)
        
        # P0: 验证输出
        if not validate_output(output_dir):
            print("[ARC-Hackathon] ERROR: Output validation failed")
            sys.exit(1)
        
        # 注入种子数据到生成的应用
        if seed_data:
            inject_seed_data(output_dir, seed_data, task_type)
        
        print("[ARC-Hackathon] Compilation completed successfully")
        
    except Exception as e:
        print(f"[ARC-Hackathon] ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)

def detect_task_type(requirement_path):
    """检测任务类型（GitHub 或 Spreadsheet）"""
    try:
        with open(requirement_path, 'r', encoding='utf-8') as f:
            content = f.read().lower()
        
        if 'github' in content or 'repository' in content or 'pull request' in content:
            return 'github'
        elif 'spreadsheet' in content or 'workbook' in content or 'worksheet' in content:
            return 'spreadsheet'
        else:
            return 'unknown'
    except Exception as e:
        print(f"[ARC-Hackathon] Warning: Could not detect task type: {e}")
        return 'unknown'

def extract_seed_data(requirement_path):
    """从需求文件中提取种子数据"""
    seed_data = {}
    
    try:
        with open(requirement_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 account 相关种子数据（更精确的匹配）
        account_pattern = r"account\s+[`']([a-zA-Z0-9_-]+)[`']"
        email_pattern = r"email\s+[`']([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})[`']"
        password_pattern = r"password\s+[`']([A-Za-z0-9!@#$%^&*()_+\-=]+)[`']"
        
        accounts = re.findall(account_pattern, content, re.IGNORECASE)
        emails = re.findall(email_pattern, content, re.IGNORECASE)
        passwords = re.findall(password_pattern, content, re.IGNORECASE)
        
        if accounts:
            seed_data['accounts'] = list(set(accounts))
        if emails:
            seed_data['emails'] = list(set(emails))
        if passwords:
            seed_data['passwords'] = list(set(passwords))
        
        # 提取 workbook 相关种子数据
        workbook_pattern = r"workbook\s+[`']([A-Za-z0-9\s]+)[`']"
        worksheet_pattern = r"worksheet\s+[`']([A-Za-z0-9\s]+)[`']"
        
        workbooks = re.findall(workbook_pattern, content, re.IGNORECASE)
        worksheets = re.findall(worksheet_pattern, content, re.IGNORECASE)
        
        if workbooks:
            seed_data['workbooks'] = list(set([w.strip() for w in workbooks]))
        if worksheets:
            seed_data['worksheets'] = list(set([w.strip() for w in worksheets]))
        
        # 提取 organization 相关种子数据
        org_pattern = r"organization\s+[`']([A-Za-z0-9\s]+)[`']"
        orgs = re.findall(org_pattern, content, re.IGNORECASE)
        if orgs:
            seed_data['organizations'] = list(set([o.strip() for o in orgs]))
        
        # 提取 repository 相关种子数据
        repo_pattern = r"repository\s+[`']([A-Za-z0-9\s-]+)[`']"
        repos = re.findall(repo_pattern, content, re.IGNORECASE)
        if repos:
            seed_data['repositories'] = list(set([r.strip() for r in repos]))
        
        # 提取 branch 相关种子数据
        branch_pattern = r"branch(?:es)?\s+[`']([A-Za-z0-9\s-]+)[`']"
        branches = re.findall(branch_pattern, content, re.IGNORECASE)
        if branches:
            seed_data['branches'] = list(set([b.strip() for b in branches]))
        
        # 提取 cell 相关种子数据
        cell_pattern = r"cell\s+([A-Z]+\d+)\s+(?:value\s+)?[`']([^`']+)[`']"
        cells = re.findall(cell_pattern, content, re.IGNORECASE)
        if cells:
            seed_data['cells'] = {cell[0]: cell[1] for cell in cells}
        
    except Exception as e:
        print(f"[ARC-Hackathon] Warning: Could not extract seed data: {e}")
    
    return seed_data

def save_seed_data(output_dir, seed_data):
    """保存种子数据到输出目录"""
    output_path = Path(output_dir)
    seed_file = output_path / 'seed_data.json'
    
    try:
        output_path.mkdir(parents=True, exist_ok=True)
        with open(seed_file, 'w', encoding='utf-8') as f:
            json.dump(seed_data, f, indent=2, ensure_ascii=False)
        print(f"[ARC-Hackathon] Seed data saved to {seed_file}")
    except Exception as e:
        print(f"[ARC-Hackathon] Warning: Could not save seed data: {e}")

def optimize_for_task(task_type, seed_data):
    """根据任务类型和种子数据优化配置"""
    if task_type == 'github':
        print("[ARC-Hackathon] Optimizing for GitHub task...")
        os.environ['ARC_FOCUS'] = 'backend'
        
        # 设置 GitHub 特定的种子数据
        if seed_data.get('accounts'):
            os.environ['ARC_SEED_ACCOUNTS'] = ','.join(seed_data['accounts'])
        if seed_data.get('emails'):
            os.environ['ARC_SEED_EMAILS'] = ','.join(seed_data['emails'])
        if seed_data.get('passwords'):
            os.environ['ARC_SEED_PASSWORDS'] = ','.join(seed_data['passwords'])
            
    elif task_type == 'spreadsheet':
        print("[ARC-Hackathon] Optimizing for Spreadsheet task...")
        os.environ['ARC_FOCUS'] = 'frontend'
        
        # 设置 Spreadsheet 特定的种子数据
        if seed_data.get('workbooks'):
            os.environ['ARC_SEED_WORKBOOKS'] = ','.join(seed_data['workbooks'])
        if seed_data.get('worksheets'):
            os.environ['ARC_SEED_WORKSHEETS'] = ','.join(seed_data['worksheets'])
    else:
        print("[ARC-Hackathon] Using default settings...")

def inject_seed_data(output_dir, seed_data, task_type):
    """将种子数据注入到生成的应用中"""
    output_path = Path(output_dir)
    
    if task_type == 'github':
        inject_github_seed_data(output_path, seed_data)
    elif task_type == 'spreadsheet':
        inject_spreadsheet_seed_data(output_path, seed_data)

def inject_github_seed_data(output_path, seed_data):
    """注入 GitHub 种子数据"""
    backend_path = output_path / 'backend'
    
    # 创建种子数据初始化脚本
    seed_script = '''const db = require('./database');

// 种子数据初始化
async function seedDatabase() {
    console.log('[Seed] Initializing seed data...');
    
    const accounts = %s;
    const emails = %s;
    const passwords = %s;
    
    // 创建种子账户
    for (let i = 0; i < accounts.length; i++) {
        const account = accounts[i];
        const email = emails[i] || `${account}@example.test`;
        const password = passwords[0] || 'Valid-password-123!';
        
        try {
            await db.run(
                'INSERT OR IGNORE INTO users (username, email, password) VALUES (?, ?, ?)',
                [account, email, password]
            );
            console.log(`[Seed] Created account: ${account}`);
        } catch (err) {
            console.log(`[Seed] Account ${account} already exists or error: ${err.message}`);
        }
    }
    
    console.log('[Seed] Seed data initialization completed');
}

module.exports = { seedDatabase };
''' % (
        json.dumps(seed_data.get('accounts', [])),
        json.dumps(seed_data.get('emails', [])),
        json.dumps(seed_data.get('passwords', []))
    )
    
    seed_file = backend_path / 'src' / 'seed.js'
    try:
        with open(seed_file, 'w', encoding='utf-8') as f:
            f.write(seed_script)
        print(f"[ARC-Hackathon] GitHub seed script created: {seed_file}")
    except Exception as e:
        print(f"[ARC-Hackathon] Warning: Could not create seed script: {e}")

def inject_spreadsheet_seed_data(output_path, seed_data):
    """注入 Spreadsheet 种子数据"""
    backend_path = output_path / 'backend'
    
    # 创建种子数据初始化脚本
    seed_script = '''const db = require('./database');

// 种子数据初始化
async function seedDatabase() {
    console.log('[Seed] Initializing seed data...');
    
    const workbooks = %s;
    const worksheets = %s;
    
    // 创建种子工作簿
    for (const workbookName of workbooks) {
        try {
            await db.run(
                'INSERT OR IGNORE INTO workbooks (name) VALUES (?)',
                [workbookName]
            );
            console.log(`[Seed] Created workbook: ${workbookName}`);
            
            // 获取工作簿ID
            const workbook = await db.get(
                'SELECT id FROM workbooks WHERE name = ?',
                [workbookName]
            );
            
            if (workbook) {
                // 创建默认工作表
                for (const sheetName of worksheets) {
                    await db.run(
                        'INSERT OR IGNORE INTO worksheets (workbook_id, name) VALUES (?, ?)',
                        [workbook.id, sheetName]
                    );
                    console.log(`[Seed] Created worksheet: ${sheetName} in ${workbookName}`);
                }
            }
        } catch (err) {
            console.log(`[Seed] Workbook ${workbookName} error: ${err.message}`);
        }
    }
    
    console.log('[Seed] Seed data initialization completed');
}

module.exports = { seedDatabase };
''' % (
        json.dumps(seed_data.get('workbooks', [])),
        json.dumps(seed_data.get('worksheets', []))
    )
    
    seed_file = backend_path / 'src' / 'seed.js'
    try:
        with open(seed_file, 'w', encoding='utf-8') as f:
            f.write(seed_script)
        print(f"[ARC-Hackathon] Spreadsheet seed script created: {seed_file}")
    except Exception as e:
        print(f"[ARC-Hackathon] Warning: Could not create seed script: {e}")

def validate_output(output_dir):
    """P0: 验证输出是否有效"""
    output_path = Path(output_dir)
    
    # 检查基本目录结构
    backend_dir = output_path / 'backend'
    frontend_dir = output_path / 'frontend'
    
    if not backend_dir.exists():
        print("[ARC-Hackathon] Validation failed: backend directory missing")
        return False
    
    if not frontend_dir.exists():
        print("[ARC-Hackathon] Validation failed: frontend directory missing")
        return False
    
    # 检查后端入口文件
    backend_src = backend_dir / 'src' / 'index.js'
    if not backend_src.exists():
        # 尝试其他可能的入口文件
        alt_entries = list(backend_dir.glob('**/index.js')) + list(backend_dir.glob('**/app.js'))
        if not alt_entries:
            print("[ARC-Hackathon] Validation failed: no backend entry file found")
            return False
    
    # 检查前端文件
    frontend_files = list(frontend_dir.glob('**/*.html')) + list(frontend_dir.glob('**/*.tsx')) + list(frontend_dir.glob('**/*.jsx'))
    if not frontend_files:
        print("[ARC-Hackathon] Validation failed: no frontend files found")
        return False
    
    print(f"[ARC-Hackathon] Output validation passed")
    return True

def install_dependencies():
    """P0: Install required dependencies if not present."""
    import subprocess
    
    required_packages = ['colorama', 'pyyaml', 'pydantic', 'openai', 'tiktoken']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"[ARC-Hackathon] Installing missing dependencies: {missing_packages}")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing_packages, 
                         capture_output=True, check=True)
            print("[ARC-Hackathon] Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"[ARC-Hackathon] Warning: Failed to install dependencies: {e}")

if __name__ == '__main__':
    main()
