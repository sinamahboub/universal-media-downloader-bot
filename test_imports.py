"""
Test all module imports and basic functionality.
"""

import sys
import traceback

print("=" * 60)
print("IMPORT VALIDATION TEST")
print("=" * 60)

test_results = []

# Test 1: Core modules
print("\n[1] Testing Core Modules...")
try:
    from core.config import settings
    from core.logger import StructuredLogger, log_download_job_event
    from core.exceptions import (
        DownloaderError,
        URLValidationError,
        PlatformNotSupportedError,
        MediaExtractionError,
    )
    print("  ✓ Core modules imported successfully")
    test_results.append(("Core modules", True))
except Exception as e:
    print(f"  ✗ Core modules failed: {e}")
    traceback.print_exc()
    test_results.append(("Core modules", False))

# Test 2: Infrastructure modules
print("\n[2] Testing Infrastructure Modules...")
try:
    from infrastructure.queue import AsyncDownloadQueue, DownloadJob, JobStatus
    from infrastructure.storage import StorageManager, FileInfo
    from infrastructure.cache import AsyncCache
    print("  ✓ Infrastructure modules imported successfully")
    test_results.append(("Infrastructure modules", True))
except Exception as e:
    print(f"  ✗ Infrastructure modules failed: {e}")
    traceback.print_exc()
    test_results.append(("Infrastructure modules", False))

# Test 3: Downloader modules
print("\n[3] Testing Downloader Modules...")
try:
    from bot.downloader import (
        BaseDownloader,
        DownloadOptions,
        MediaMetadata,
        PlatformType,
        MediaType,
        DownloaderFactory,
        YouTubeDownloader,
        SoundCloudDownloader,
        InstagramDownloader,
    )
    print("  ✓ Downloader modules imported successfully")
    test_results.append(("Downloader modules", True))
except Exception as e:
    print(f"  ✗ Downloader modules failed: {e}")
    traceback.print_exc()
    test_results.append(("Downloader modules", False))

# Test 4: Service modules
print("\n[4] Testing Service Modules...")
try:
    from bot.services import URLParserService, MediaDownloadService
    print("  ✓ Service modules imported successfully")
    test_results.append(("Service modules", True))
except Exception as e:
    print(f"  ✗ Service modules failed: {e}")
    traceback.print_exc()
    test_results.append(("Service modules", False))

# Test 5: Handler modules
print("\n[5] Testing Handler Modules...")
try:
    from bot.handlers import MessageHandler, CallbackQueryHandler
    print("  ✓ Handler modules imported successfully")
    test_results.append(("Handler modules", True))
except Exception as e:
    print(f"  ✗ Handler modules failed: {e}")
    traceback.print_exc()
    test_results.append(("Handler modules", False))

# Test 6: Keyboard modules
print("\n[6] Testing Keyboard Modules...")
try:
    from bot.keyboards import format_keyboard, quality_keyboard, cancel_keyboard
    print("  ✓ Keyboard modules imported successfully")
    test_results.append(("Keyboard modules", True))
except Exception as e:
    print(f"  ✗ Keyboard modules failed: {e}")
    traceback.print_exc()
    test_results.append(("Keyboard modules", False))

# Test 7: Middleware modules
print("\n[7] Testing Middleware Modules...")
try:
    from bot.middlewares import AuthMiddleware, RateLimitMiddleware
    print("  ✓ Middleware modules imported successfully")
    test_results.append(("Middleware modules", True))
except Exception as e:
    print(f"  ✗ Middleware modules failed: {e}")
    traceback.print_exc()
    test_results.append(("Middleware modules", False))

# Test 8: Config validation
print("\n[8] Testing Config Validation...")
try:
    print(f"  - TELEGRAM_BOT_TOKEN set: {bool(settings.TELEGRAM_BOT_TOKEN)}")
    print(f"  - APP_ENV: {settings.APP_ENV}")
    print(f"  - MAX_FILE_SIZE_MB: {settings.MAX_FILE_SIZE_MB}")
    print(f"  - TEMP_STORAGE_PATH: {settings.TEMP_STORAGE_PATH}")
    print(f"  - TEMP_STORAGE exists: {settings.TEMP_STORAGE_PATH.exists()}")
    print("  ✓ Config validation passed")
    test_results.append(("Config validation", True))
except Exception as e:
    print(f"  ✗ Config validation failed: {e}")
    traceback.print_exc()
    test_results.append(("Config validation", False))

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
    print("\n✓ ALL TESTS PASSED - System ready for runtime testing")
    sys.exit(0)
else:
    print(f"\n✗ {total - passed} TEST(S) FAILED - Fix required before runtime")
    sys.exit(1)
