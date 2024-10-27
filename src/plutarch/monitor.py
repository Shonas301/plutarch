from time import sleep

import psutil
from tqdm import tqdm


def monitor_stats():
    with (
        tqdm(total=100, desc="cpu%", position=0, leave=True) as cpubar,
        tqdm(total=100, desc="ram%", position=1, leave=True) as rambar,
    ):
        while True:
            rambar.n = psutil.virtual_memory().percent
            cpubar.n = psutil.cpu_percent()
            rambar.update()
            cpubar.update()
            sleep(1)
