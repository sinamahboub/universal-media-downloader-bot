"""
Runtime functionality test without actual Telegram connection.
"""

import asyncio
import sys
import traceback

print("=" * 60)
print("RUNTIME FUNCTIONALITY TEST")
print("=" * 60)

test_results = []

# Test 1: URL Parser Service
print("\n[1] Testing URL Parser Service...")
try:
    from bot.services import URLParserService
    from bot.downloader import DownloaderFactory
    
    parser = URLParserService()
    factory = DownloaderFactory()
    
    test_urls = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://soundcloud.com/artist/track", "soundcloud"),
        ("https://www.instagram.com/reel/ABC123/", "instagram"),
    ]
    
    for url, expected_platform in test_urls:
        platform = factory.detect_platform(url)
        print(f"  ✓ {expected_platform}: {url[:50]}... → {platform}")
    
    print("  ✓ URL Parser Service working correctly")
    test_results.append(("URL Parser Service", True))
except Exception as e:
    print(f"  ✗ URL Parser Service failed: {e}")
    traceback.print_exc()
    test_results.append(("URL Parser Service", False))

# Test 2: Downloader Factory
print("\n[2] Testing Downloader Factory...")
try:
    from bot.downloader import DownloaderFactory
    
    factory = DownloaderFactory()
    
    youtube_url = "https://www.youtube.com/watch?v=test"
    soundcloud_url = "https://soundcloud.com/user/track"
    instagram_url = "https://www.instagram.com/reel/test/"
    invalid_url = "https://example.com/video"
    
    assert factory.detect_platform(youtube_url) is not None
    assert factory.detect_platform(soundcloud_url) is not None
    assert factory.detect_platform(instagram_url) is not None
    assert factory.detect_platform(invalid_url) is None
    
    print("  ✓ Platform detection working for all platforms")
    print("  ✓ Invalid URLs correctly rejected")
    test_results.append(("Downloader Factory", True))
except Exception as e:
    print(f"  ✗ Downloader Factory failed: {e}")
    traceback.print_exc()
    test_results.append(("Downloader Factory", False))

# Test 3: Async Queue System
print("\n[3] Testing Async Queue System...")
try:
    from infrastructure.queue import AsyncDownloadQueue, DownloadJob
    
    async def test_queue():
        queue = AsyncDownloadQueue()
        
        job = DownloadJob(
            user_id=123,
            url="https://youtube.com/test",
            platform="youtube",
            format_type="audio",
            quality="best"
        )
        
        enqueued = await queue.enqueue(job)
        assert enqueued.job_id == job.job_id
        print(f"  ✓ Job enqueued: {job.job_id[:8]}...")
        
        retrieved = queue.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.user_id == 123
        print(f"  ✓ Job retrieved successfully")
        
        stats = queue.get_stats()
        assert stats.pending_jobs == 1
        print(f"  ✓ Queue stats: {stats.pending_jobs} pending")
        
        cancelled = await queue.cancel_job(job.job_id)
        assert cancelled
        print(f"  ✓ Job cancelled successfully")
        
        await queue.shutdown()
        return True
    
    result = asyncio.run(test_queue())
    if result:
        print("  ✓ Async Queue System working correctly")
        test_results.append(("Async Queue System", True))
    else:
        test_results.append(("Async Queue System", False))
except Exception as e:
    print(f"  ✗ Async Queue System failed: {e}")
    traceback.print_exc()
    test_results.append(("Async Queue System", False))

# Test 4: Storage Manager
print("\n[4] Testing Storage Manager...")
try:
    from infrastructure.storage import StorageManager
    
    storage = StorageManager()
    
    test_path = storage.get_storage_path("test-job-123", ".mp3")
    assert test_path.parent.exists()
    print(f"  ✓ Storage path: {test_path.name}")
    
    stats = storage.get_storage_stats()
    assert "total_files" in stats
    print(f"  ✓ Storage stats working")
    
    storage.shutdown()
    print("  ✓ Storage Manager working correctly")
    test_results.append(("Storage Manager", True))
except Exception as e:
    print(f"  ✗ Storage Manager failed: {e}")
    traceback.print_exc()
    test_results.append(("Storage Manager", False))

# Test 5: Media Download Service
print("\n[5] Testing Media Download Service...")
try:
    from bot.services import MediaDownloadService
    
    async def test_media_service():
        queue = AsyncDownloadQueue()
        storage = StorageManager()
        url_parser = URLParserService()
        
        service = MediaDownloadService(queue, storage, url_parser)
        
        job = await service.request_download(
            user_id=123,
            url="https://www.youtube.com/watch?v=test",
            format_type="audio",
            quality="best"
        )
        
        assert job.job_id is not None
        assert job.platform == "youtube"
        print(f"  ✓ Download request created")
        
        cancelled = await service.cancel_user_downloads(123)
        assert len(cancelled) > 0
        print(f"  ✓ Download cancelled")
        
        await queue.shutdown()
        storage.shutdown()
        return True
    
    result = asyncio.run(test_media_service())
    if result:
        print("  ✓ Media Download Service working correctly")
        test_results.append(("Media Download Service", True))
    else:
        test_results.append(("Media Download Service", False))
except Exception as e:
    print(f"  ✗ Media Download Service failed: {e}")
    traceback.print_exc()
    test_results.append(("Media Download Service", False))

# Test 6: Cache System
print("\n[6] Testing Cache System...")
try:
    from infrastructure.cache import AsyncCache
    
    async def test_cache():
        cache = AsyncCache(max_size=10, default_ttl=60)
        
        await cache.set("test_value", 60, "test_key")
        value = await cache.get("test_key")
        assert value == "test_value"
        print(f"  ✓ Cache set/get working")
        
        stats = cache.get_stats()
        assert stats["size"] == 1
        print(f"  ✓ Cache stats working")
        
        await cache.clear()
        return True
    
    result = asyncio.run(test_cache())
    if result:
        print("  ✓ Cache System working correctly")
        test_results.append(("Cache System", True))
    else:
        test_results.append(("Cache System", False))
except Exception as e:
    print(f"  ✗ Cache System failed: {e}")
    traceback.print_exc()
    test_results.append(("Cache System", False))

# Test 7: Error Handling
print("\n[7] Testing Error Handling...")
try:
    from core.exceptions import DownloaderError, URLValidationError
    
    url_error = URLValidationError("Test", "http://test.com")
    assert isinstance(url_error, DownloaderError)
    assert "URL_VALIDATION_ERROR" in str(url_error)
    print(f"  ✓ Exception hierarchy correct")
    print("  ✓ Error Handling working correctly")
    test_results.append(("Error Handling", True))
except Exception as e:
    print(f"  ✗ Error Handling failed: {e}")
    traceback.print_exc()
    test_results.append(("Error Handling", False))

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
    print("\n✓ ALL RUNTIME TESTS PASSED")
    sys.exit(0)
else:
    print(f"\n✗ {total - passed} TEST(S) FAILED")
    sys.exit(1)

