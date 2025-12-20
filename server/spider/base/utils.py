import time
import random

def random_delay(min_sec: int = 1, max_sec: int = 3):
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)