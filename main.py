#!/usr/bin/env python3
"""
定制版 ARC Agent - 针对比赛需求优化
支持 GitHub 和 Spreadsheet 任务

修复内容：
- P0: 正确的退出码和错误处理
- P1: 移除强制 --clean，支持断点恢复
- P1: 保留图片引用结构
"""
import os
import sys
import glob
import json
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
    
    # 根据任务类型优化配置
    optimize_for_task(task_type)
    
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

def optimize_for_task(task_type):
    """根据任务类型优化配置"""
    if task_type == 'github':
        print("[ARC-Hackathon] Optimizing for GitHub task...")
        os.environ['ARC_FOCUS'] = 'backend'
    elif task_type == 'spreadsheet':
        print("[ARC-Hackathon] Optimizing for Spreadsheet task...")
        os.environ['ARC_FOCUS'] = 'frontend'
    else:
        print("[ARC-Hackathon] Using default settings...")

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

if __name__ == '__main__':
    main()

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
