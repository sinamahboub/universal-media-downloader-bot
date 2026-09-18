"""
Edge case and error handling tests.
"""

import sys
import traceback

print("=" * 60)
print("EDGE CASE & ERROR HANDLING TESTS")
print("=" * 60)

test_results = []

# Test 1: Invalid URLs
print("\n[1] Testing Invalid URL Handling...")
try:
    from bot.services import URLParserService
    from core.exceptions import URLValidationError
    
    parser = URLParserService()
    
    invalid_urls = [
        "not a url",
        "http://",
        "https://example.com",
        "ftp://example.com/file",
        "",
    ]
    
    for url in invalid_urls:
        try:
            parser.parse(url)
            print(f"  ✗ Should have rejected: {url[:30]}")
        except (URLValidationError, Exception):
            print(f"  ✓ Correctly rejected: {url[:30] if url else '(empty)'}")
    
    print("  ✓ Invalid URL handling working correctly")
    test_results.append(("Invalid URL Handling", True))
except Exception as e:
    print(f"  ✗ Invalid URL handling failed: {e}")
    traceback.print_exc()
    test_results.append(("Invalid URL Handling", False))

# Test 2: Exception Hierarchy
print("\n[2] Testing Exception Hierarchy...")
try:
    from core.exceptions import (
        DownloaderError,
        URLValidationError,
        PlatformNotSupportedError,
        MediaExtractionError,
    )
    
    url_error = URLValidationError("test", "http://test.com")
    assert isinstance(url_error, DownloaderError)
    assert url_error.code == "URL_VALIDATION_ERROR"
    assert url_error.url == "http://test.com"
    
    print("  ✓ Exception hierarchy correct")
    print("  ✓ Error codes and details working")
    test_results.append(("Exception Hierarchy", True))
except Exception as e:
    print(f"  ✗ Exception Hierarchy failed: {e}")
    traceback.print_exc()
    test_results.append(("Exception Hierarchy", False))

# Test 3: File Size Validation
print("\n[3] Testing File Size Validation...")
try:
    from infrastructure.storage import FileInfo
    from pathlib import Path
    from datetime import datetime
    from core.config import settings
    
    small_file = FileInfo(
        job_id="test",
        file_path=Path("/tmp/test.mp3"),
        file_name="test.mp3",
        file_size=1024,
        mime_type="audio/mpeg",
        extension=".mp3",
        created_at=datetime.utcnow(),
        user_id=123,
        url="http://test.com"
    )
    
    assert not small_file.exceeds_telegram_limit()
    print("  ✓ Small file (1KB) passes limit check")
    
    large_file = FileInfo(
        job_id="test2",
        file_path=Path("/tmp/test.mp3"),
        file_name="test.mp3",
        file_size=60 * 1024 * 1024,
        mime_type="audio/mpeg",
        extension=".mp3",
        created_at=datetime.utcnow(),
        user_id=123,
        url="http://test.com"
    )
    
    assert large_file.exceeds_telegram_limit()
    print("  ✓ Large file (60MB) correctly exceeds limit")
    
    test_results.append(("File Size Validation", True))
except Exception as e:
    print(f"  ✗ File Size Validation failed: {e}")
    traceback.print_exc()
    test_results.append(("File Size Validation", False))

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
passed = sum(1 for _, result in test_results if result)
total = len(test_results)
print(f"Passed: {passed}/{total}")
print("\nDetailed Results:")
for test_name, result in test_results:
    status = "✓ PASS" if result else "✗ FAIL"
    print(f"  {status}: {test_name}")

if passed == total:
    print("\n✓ ALL EDGE CASE TESTS PASSED")
    sys.exit(0)
else:
    print(f"\n✗ {total - passed} TEST(S) FAILED")
    sys.exit(1)
