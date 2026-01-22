"""Basic tests for core security modules."""

import asyncio
from src.security import (
    CodeSecurityScanner,
    InputValidator,
)
from src.utils import seconds_to_human, render_bar


def test_code_scanner_accepts_safe_code():
    """Test code scanner accepts safe code."""
    scanner = CodeSecurityScanner()
    
    safe_code = """
import asyncio
import logging

async def main():
    logging.info("Hello")
    await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
"""
    
    is_safe, msg = scanner.scan_code(safe_code)
    assert is_safe, f"Safe code rejected: {msg}"
    print("✅ Code scanner accepts safe code")


def test_code_scanner_rejects_dangerous_code():
    """Test code scanner rejects dangerous code."""
    scanner = CodeSecurityScanner()
    
    dangerous_code = "import os; os.system('whoami')"
    
    is_safe, msg = scanner.scan_code(dangerous_code)
    assert not is_safe, "Dangerous code not rejected"
    assert "os" in msg or "forbidden" in msg.lower(), f"Wrong error: {msg}"
    print("✅ Code scanner rejects dangerous code")


def test_input_validator():
    """Test input validator."""
    validator = InputValidator()
    
    # Valid cases
    assert validator.validate_username("testuser"), "Valid username rejected"
    assert validator.validate_bot_name("My Bot 123"), "Valid bot name rejected"
    assert validator.validate_bot_id("123"), "Valid bot ID rejected"
    assert validator.validate_github_url("https://github.com/user/repo"), "Valid GitHub URL rejected"
    
    # Invalid cases
    assert not validator.validate_username("abc"), "Too short username accepted"
    assert not validator.validate_github_url("http://github.com/user/repo"), "HTTP URL accepted"
    
    print("✅ Input validator works correctly")


def test_time_helpers():
    """Test time formatting utilities."""
    
    # Test seconds_to_human
    assert seconds_to_human(60) == "1m", f"Got: {seconds_to_human(60)}"
    assert seconds_to_human(3600) == "1h", f"Got: {seconds_to_human(3600)}"
    assert seconds_to_human(86400) == "1d", f"Got: {seconds_to_human(86400)}"
    assert seconds_to_human(90061) == "1d 1h 1m 1s"
    
    # Test render_bar
    bar = render_bar(50)
    assert "50%" in bar, f"Percentage not in bar: {bar}"
    assert "█" in bar, f"No full bar character: {bar}"
    
    print("✅ Time helpers work correctly")


if __name__ == "__main__":
    print("\n🧪 Running basic tests...\n")
    
    try:
        test_code_scanner_accepts_safe_code()
        test_code_scanner_rejects_dangerous_code()
        test_input_validator()
        test_time_helpers()
        
        print("\n✅ All tests passed!\n")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        exit(1)
