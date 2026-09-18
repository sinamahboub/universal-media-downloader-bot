import os
import sys
import signal
from pathlib import Path
from typing import Optional

from core.config import settings
from core.logger import StructuredLogger

logger = StructuredLogger(component="lock")


class SingleInstanceLock:
    def __init__(self, lock_file_path: Optional[Path] = None) -> None:
        self.lock_file_path = lock_file_path or Path("bot.lock")
        self.pid: Optional[int] = None
        self._owns_lock = False

    def _is_pid_running(self, pid: int) -> bool:
        try:
            if sys.platform == "win32":
                import subprocess
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return str(pid) in result.stdout
            else:
                os.kill(pid, 0)
                return True
        except (OSError, ProcessLookupError):
            return False
        except Exception as exc:
            logger.warning("pid_check_failed", pid=pid, error=str(exc))
            return False

    def acquire(self) -> bool:
        try:
            if self.lock_file_path.exists():
                try:
                    existing_pid = int(self.lock_file_path.read_text().strip())
                    self.pid = existing_pid

                    if self._is_pid_running(existing_pid):
                        logger.error(
                            "instance_already_running",
                            pid=existing_pid,
                            lock_path=str(self.lock_file_path)
                        )
                        print(f"❌ Another instance is already running (PID: {existing_pid})")
                        print(f"   Lock file: {self.lock_file_path}")
                        print("   If you're sure no other instance is running, delete the lock file:")
                        print(f"   del {self.lock_file_path}")
                        sys.exit(1)
                    else:
                        logger.warning(
                            "stale_lock_file_removed",
                            pid=existing_pid,
                            lock_path=str(self.lock_file_path)
                        )
                        self.lock_file_path.unlink()

                except (ValueError, OSError) as exc:
                    logger.warning("invalid_lock_file", error=str(exc))
                    try:
                        self.lock_file_path.unlink()
                    except OSError:
                        pass

            current_pid = os.getpid()
            self.lock_file_path.write_text(str(current_pid))
            self.pid = current_pid
            self._owns_lock = True

            logger.info("lock_acquired", pid=current_pid, lock_path=str(self.lock_file_path))
            return True

        except OSError as exc:
            logger.error("lock_acquisition_failed", error=str(exc))
            print(f"❌ Failed to create lock file: {exc}")
            sys.exit(1)

    def release(self) -> None:
        if self._owns_lock and self.lock_file_path.exists():
            try:
                self.lock_file_path.unlink()
                logger.info("lock_released", pid=self.pid, lock_path=str(self.lock_file_path))
            except OSError as exc:
                logger.error("lock_release_failed", pid=self.pid, error=str(exc))

        self._owns_lock = False
        self.pid = None

    def __enter__(self) -> "SingleInstanceLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


class LockManager:
    def __init__(self) -> None:
        self._locks: list = []
        self._shutdown_registered = False

    def register_lock(self, lock) -> None:
        self._locks.append(lock)
        if not self._shutdown_registered:
            self._register_shutdown_handler()
            self._shutdown_registered = True

    def _register_shutdown_handler(self) -> None:
        def signal_handler(signum, frame):
            logger.info("shutdown_signal_received", signal=signum)
            self.release_all()
            sys.exit(0)
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            if sys.platform != "win32":
                signal.signal(signal.SIGABRT, signal_handler)
        except Exception as exc:
            logger.warning("shutdown_handler_failed", error=str(exc))

    def release_all(self) -> None:
        logger.info("releasing_all_locks", lock_count=len(self._locks))
        for lock in self._locks:
            try:
                lock.release()
            except Exception as exc:
                logger.error("lock_release_error", error=str(exc))
        self._locks.clear()


lock_manager = LockManager()


def ensure_single_instance(lock_file=None):
    lock = SingleInstanceLock(lock_file)
    lock_manager.register_lock(lock)
    lock.acquire()
    return lock
