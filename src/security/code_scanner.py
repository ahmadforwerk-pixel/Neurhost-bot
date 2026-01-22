"""Code security scanning for malicious Python code."""

import ast
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class CodeSecurityScanner:
    """
    Detect obviously malicious Python code using AST analysis.
    
    NOT a full sandbox - catches common attacks but requires Docker isolation.
    """
    
    # Forbidden module imports
    DANGEROUS_MODULES = {
        'os', 'sys', 'subprocess', 'socket', 'urllib', 'urllib.request',
        '__builtin__', '__main__', 'importlib', 'types', 'inspect',
        'multiprocessing', 'threading', 'concurrent.futures',
    }
    
    # Forbidden function calls
    DANGEROUS_FUNCTIONS = {
        'eval', 'exec', 'compile', '__import__', 'open',
    }
    
    # Allowed networking modules
    ALLOWED_NETWORKING = {
        'requests', 'aiohttp', 'httpx', 'urllib3',
        'telegram', 'telegram.ext',
    }
    
    # Whitelisted modules for Telegram bots
    SAFE_MODULES = {
        'telegram', 'logging', 'json', 'datetime', 'time', 're',
        'asyncio', 'aiohttp', 'requests', 'random', 'math', 'hashlib',
        'collections', 'itertools', 'functools', 'operator', 'string',
        'uuid', 'base64', 'enum', 'typing', 'dataclasses',
    }
    
    def scan_code(self, code: str) -> Tuple[bool, str]:
        """
        Scan code for security issues.
        
        Args:
            code: Python source code to scan
        
        Returns:
            (is_safe: bool, violation_message: str)
        
        Examples:
            >>> scanner = CodeSecurityScanner()
            >>> safe, msg = scanner.scan_code("import os")
            >>> print(f"Safe: {safe}, Msg: {msg}")
            Safe: False, Msg: Forbidden import: os
        """
        
        # Parse code
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            # Syntax errors prevent execution, so they're safe
            return False, f"Syntax error (code won't run): {e}"
        
        violations = []
        
        # Walk AST checking for violations
        for node in ast.walk(tree):
            
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    violation = self._check_import(module_name)
                    if violation:
                        violations.append(violation)
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    violation = self._check_import(module_name)
                    if violation:
                        violations.append(violation)
            
            # Check function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.DANGEROUS_FUNCTIONS:
                        violations.append(f"Forbidden function: {node.func.id}()")
            
            # Check dangerous attribute access patterns
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    if node.value.id in self.DANGEROUS_MODULES:
                        if node.attr in {'system', 'popen', 'run', 'call'}:
                            violations.append(
                                f"Forbidden: {node.value.id}.{node.attr}()"
                            )
        
        if violations:
            # Return first 3 violations
            return False, "; ".join(violations[:3])
        
        return True, ""
    
    def _check_import(self, module_name: str) -> str:
        """Check if import is allowed."""
        
        # Explicitly dangerous
        if module_name in self.DANGEROUS_MODULES:
            return f"Forbidden import: {module_name}"
        
        # Reject socket/ssl/http
        if module_name in {'socket', 'ssl', 'http'}:
            return f"Forbidden import: {module_name}"
        
        # Allow whitelisted
        if module_name in self.SAFE_MODULES or module_name in self.ALLOWED_NETWORKING:
            return ""
        
        # Whitelist approach: reject unknown
        return f"Unknown module (not whitelisted): {module_name}"
