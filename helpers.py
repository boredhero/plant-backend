import time
from threading import Lock


class Singleton(type):
    """
    Thread-safe Singleton metaclass using double-checked locking pattern.
    Uses separate locks per class to prevent deadlock when one singleton creates another.
    Safe for use with Gunicorn gthread workers where multiple threads
    may attempt to instantiate the same class concurrently.
    Pattern explanation:
    1. Fast path (unlocked): Check if instance exists - handles 99.9% of calls
    2. Slow path (locked): Only lock when instance doesn't exist
    3. Double-check (locked): Verify no other thread created it while we waited for lock
    4. Per-class locks: Prevents deadlock when singleton A creates singleton B during init
    """
    _instances = {}
    _locks = {}  # Separate lock for each singleton class
    def __call__(cls, *args, **kwargs):
        # Fast path: instance already exists (no lock needed)
        if cls not in cls._instances:
            # Get or create lock for this specific class
            if cls not in cls._locks:
                cls._locks[cls] = Lock()
            # Slow path: need to create instance (acquire lock for THIS class only)
            with cls._locks[cls]:
                # Double-check: another thread might have created it while we waited
                if cls not in cls._instances:
                    instance = super(Singleton, cls).__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]


def get_unix_timestamp():
    return int(time.time())
