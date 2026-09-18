import sys
import subprocess
import platform

print("=" * 60)
print("ENVIRONMENT DETECTION")
print("=" * 60)
print(f"Python Version: {sys.version}")
print(f"Platform: {platform.system()} {platform.release()}")
print(f"Architecture: {platform.machine()}")
print(f"Working Directory: {sys.path[0]}")
print()

# Check pip packages
print("Checking installed packages...")
try:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "list"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        packages = result.stdout.split('\n')
        print(f"Total packages installed: {len(packages) - 2}")
        
        # Check critical packages
        critical = ['python-telegram-bot', 'yt-dlp', 'pydantic', 'structlog', 'sentry-sdk']
        print("\nCritical packages:")
        for pkg in critical:
            found = any(pkg.lower() in line.lower() for line in packages)
            status = "✓" if found else "✗"
            print(f"  {status} {pkg}")
    else:
        print(f"Error checking packages: {result.stderr}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
