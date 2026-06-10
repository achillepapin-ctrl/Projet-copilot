import psutil
import time
import csv
import sys
from datetime import datetime

scenario = sys.argv[1] if len(sys.argv) > 1 else "inconnu"
output = f"/home/wifi/copilot/analysis/results/cpu_{scenario}.csv"

with open(output, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "cpu_global_%", "ram_utilisee_mo",
                     "ram_pct", "cpu_camion_%", "cpu_voiture_%",
                     "mem_camion_mo", "mem_voiture_mo"])

    print(f"Monitoring démarré → {output}")
    print("Ctrl+C pour arrêter")

    while True:
        ts = datetime.now().strftime("%H:%M:%S")
        cpu_g = psutil.cpu_percent(interval=1)
        ram   = psutil.virtual_memory()

        cpu_c = mem_c = cpu_v = mem_v = 0.0

        for proc in psutil.process_iter(['name', 'cmdline', 'cpu_percent', 'memory_info']):
            try:
                cmd = " ".join(proc.info['cmdline'] or [])
                if "camion.py" in cmd:
                    cpu_c = proc.info['cpu_percent']
                    mem_c = proc.info['memory_info'].rss / 1024 / 1024
                elif "voiture.py" in cmd:
                    cpu_v = proc.info['cpu_percent']
                    mem_v = proc.info['memory_info'].rss / 1024 / 1024
            except Exception:
                pass

        writer.writerow([ts, cpu_g,
                         round(ram.used/1024/1024, 1), ram.percent,
                         cpu_c, cpu_v,
                         round(mem_c, 1), round(mem_v, 1)])
        f.flush()
