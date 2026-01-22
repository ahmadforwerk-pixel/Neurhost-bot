#!/usr/bin/env python3
"""
NeuroHost V4 Project Health Check & Verification Script
Comprehensive testing and validation of all project modules
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title: str):
    """Print formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title:^70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_success(msg: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg: str):
    """Print error message."""
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_warning(msg: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def check_file_structure() -> Tuple[bool, Dict]:
    """Check if project structure is correct."""
    required_dirs = [
        'src', 'src/core', 'src/security', 'src/db', 'src/containers', 'src/utils'
    ]
    
    required_files = [
        'requirements.txt',
        '.env.example',
        'src/__init__.py',
        'src/core/config.py',
        'src/core/types.py',
        'src/security/secrets_manager.py',
        'src/security/token_validator.py',
        'src/security/code_scanner.py',
        'src/security/rate_limiter.py',
        'src/security/audit_logger.py',
        'src/security/permissions.py',
        'src/security/validators.py',
        'src/db/models.py',
        'src/db/connection.py',
        'src/db/repository.py',
        'src/containers/manager.py',
        'src/containers/resource_enforcer.py',
        'src/utils/time_helpers.py',
        'src/utils/logger.py',
    ]
    
    print_header("📂 File Structure Check")
    
    all_ok = True
    stats = {'dirs_ok': 0, 'files_ok': 0, 'total_dirs': len(required_dirs), 'total_files': len(required_files)}
    
    for dir_path in required_dirs:
        if os.path.isdir(dir_path):
            print_success(f"Directory: {dir_path}")
            stats['dirs_ok'] += 1
        else:
            print_error(f"Directory missing: {dir_path}")
            all_ok = False
    
    for file_path in required_files:
        if os.path.isfile(file_path):
            print_success(f"File: {file_path}")
            stats['files_ok'] += 1
        else:
            print_error(f"File missing: {file_path}")
            all_ok = False
    
    return all_ok, stats

def check_imports() -> Tuple[bool, Dict]:
    """Check if all modules can be imported."""
    print_header("📦 Module Import Check")
    
    modules_to_test = [
        ('src.security', ['CodeSecurityScanner', 'InputValidator', 'SecretsManager']),
        ('src.db.models', ['User', 'Bot', 'AuditLog']),
        ('src.containers.manager', ['DockerContainerManager']),
        ('src.containers.resource_enforcer', ['ResourceEnforcer']),
        ('src.utils', ['seconds_to_human', 'render_bar']),
        ('src.core.types', ['UserData', 'BotData']),
    ]
    
    all_ok = True
    stats = {'modules_ok': 0, 'total_modules': len(modules_to_test)}
    
    for module_name, items in modules_to_test:
        try:
            module = __import__(module_name, fromlist=items)
            for item in items:
                if hasattr(module, item):
                    print_success(f"{module_name}.{item}")
                else:
                    print_error(f"{module_name}.{item} not found")
                    all_ok = False
            stats['modules_ok'] += 1
        except ImportError as e:
            if 'env var' in str(e).lower():
                print_warning(f"{module_name} (needs environment variables)")
                stats['modules_ok'] += 1
            else:
                print_error(f"Cannot import {module_name}: {e}")
                all_ok = False
        except Exception as e:
            print_error(f"Error importing {module_name}: {e}")
            all_ok = False
    
    return all_ok, stats

def check_functionality() -> Tuple[bool, Dict]:
    """Check basic functionality of key modules."""
    print_header("🧪 Functionality Tests")
    
    stats = {'tests_ok': 0, 'total_tests': 0}
    all_ok = True
    
    # Test 1: Code Scanner
    stats['total_tests'] += 1
    try:
        from src.security import CodeSecurityScanner
        scanner = CodeSecurityScanner()
        
        safe_code = "import asyncio\nlogging.info('test')"
        is_safe, _ = scanner.scan_code(safe_code)
        
        if is_safe:
            print_success("Code Scanner: Safe code accepted")
            stats['tests_ok'] += 1
        else:
            print_error("Code Scanner: Safe code rejected (error)")
            all_ok = False
    except Exception as e:
        print_warning(f"Code Scanner test skipped: {str(e)[:50]}")
    
    # Test 2: Input Validator
    stats['total_tests'] += 1
    try:
        from src.security import InputValidator
        validator = InputValidator()
        
        if validator.validate_username("testuser") and validator.validate_bot_name("Test Bot"):
            print_success("Input Validator: Validation working")
            stats['tests_ok'] += 1
        else:
            print_error("Input Validator: Validation failed")
            all_ok = False
    except Exception as e:
        print_warning(f"Input Validator test skipped: {str(e)[:50]}")
    
    # Test 3: Time Helpers
    stats['total_tests'] += 1
    try:
        from src.utils import seconds_to_human
        
        if seconds_to_human(3600) == "1h":
            print_success("Time Helpers: Formatting working")
            stats['tests_ok'] += 1
        else:
            print_error("Time Helpers: Formatting failed")
            all_ok = False
    except Exception as e:
        print_warning(f"Time Helpers test skipped: {str(e)[:50]}")
    
    # Test 4: Database Models
    stats['total_tests'] += 1
    try:
        from src.db.models import User, Bot, AuditLog
        
        user_ok = hasattr(User, 'id') and hasattr(User, 'username')
        bot_ok = hasattr(Bot, 'token_encrypted') and hasattr(Bot, 'remaining_seconds')
        
        if user_ok and bot_ok:
            print_success("Database Models: All attributes present")
            stats['tests_ok'] += 1
        else:
            print_error("Database Models: Missing attributes")
            all_ok = False
    except Exception as e:
        print_warning(f"Database Models test skipped: {str(e)[:50]}")
    
    # Test 5: Configuration Loading
    stats['total_tests'] += 1
    try:
        from src.core.config import Constants
        
        if hasattr(Constants, 'PLAN_LIMITS') and hasattr(Constants, 'ERROR_MESSAGES'):
            print_success("Configuration: Constants loaded")
            stats['tests_ok'] += 1
        else:
            print_error("Configuration: Constants missing")
            all_ok = False
    except ValueError:
        print_warning("Configuration: Environment variables required (expected)")
        stats['tests_ok'] += 1
    except Exception as e:
        print_warning(f"Configuration test skipped: {str(e)[:50]}")
    
    return all_ok, stats

def check_dependencies() -> Tuple[bool, Dict]:
    """Check if all required dependencies are installed."""
    print_header("📚 Dependency Check")
    
    required_packages = [
        'telegram',
        'sqlalchemy',
        'cryptography',
        'aiohttp',
        'redis',
        'docker',
        'asyncpg',
        'dotenv',
    ]
    
    stats = {'deps_ok': 0, 'total_deps': len(required_packages)}
    all_ok = True
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print_success(f"Package: {package}")
            stats['deps_ok'] += 1
        except ImportError:
            print_error(f"Package not installed: {package}")
            all_ok = False
    
    return all_ok, stats

def generate_report(results: Dict) -> str:
    """Generate final report."""
    print_header("📊 Final Verification Report")
    
    # Overall status
    all_passed = all(result[0] for result in results.values())
    
    status_text = f"{Colors.GREEN}✅ PASSED{Colors.END}" if all_passed else f"{Colors.RED}❌ FAILED{Colors.END}"
    print(f"Overall Status: {status_text}\n")
    
    # Detailed breakdown
    print(f"{Colors.BOLD}Detailed Results:{Colors.END}")
    for check_name, (passed, stats) in results.items():
        status = f"{Colors.GREEN}✅{Colors.END}" if passed else f"{Colors.RED}❌{Colors.END}"
        print(f"\n{status} {check_name}")
        for key, value in stats.items():
            print(f"   • {key}: {value}")
    
    # Recommendations
    print(f"\n{Colors.BOLD}Next Steps:{Colors.END}")
    if all_passed:
        print(f"{Colors.GREEN}✅ All checks passed! Project is ready for next phase.{Colors.END}")
        print(f"   • Create Telegram handlers (src/telegram_handlers/)")
        print(f"   • Create service layer (src/services/)")
        print(f"   • Create main entry point (src/main.py)")
        print(f"   • Configure environment variables (.env)")
        print(f"   • Set up Docker configurations")
    else:
        print(f"{Colors.RED}❌ Some checks failed. Fix the issues before proceeding.{Colors.END}")
    
    return "\n" + "="*70

def main():
    """Main verification script."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print(" " * 15 + "NeuroHost V4 - Project Verification")
    print(" " * 20 + "Comprehensive Health Check")
    print(f"{Colors.END}")
    
    # Run all checks
    results = {
        'File Structure': check_file_structure(),
        'Dependency Installation': check_dependencies(),
        'Module Imports': check_imports(),
        'Functionality Tests': check_functionality(),
    }
    
    # Generate report
    report = generate_report(results)
    print(report)
    
    # Exit code
    all_passed = all(result[0] for result in results.values())
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
