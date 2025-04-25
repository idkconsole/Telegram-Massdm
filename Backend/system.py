import psutil
import time
import platform
from datetime import datetime
import socket
import json
import os
from typing import Dict, Any, Optional

class SystemMonitor:
    default_host = "8.8.8.8"
    default_port = 53
    default_timeout = 3
    data_file = "diagnostics/system_data.json"
    byte_units = ['B', 'KB', 'MB', 'GB', 'TB']

    def __init__(self):
        self.os_type: str = platform.system()
        self.data_file: str = self.data_file

    def get_cpu_usage(self) -> float:
        return psutil.cpu_percent(interval=1)

    def get_memory_usage(self) -> Dict[str, Any]:
        memory = psutil.virtual_memory()
        return {
            'total': self._convert_bytes(memory.total),
            'available': self._convert_bytes(memory.available),
            'percent': memory.percent,
            'used': self._convert_bytes(memory.used)
        }

    def get_disk_space(self) -> Dict[str, Dict[str, Any]]:
        partitions = {}
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partitions[partition.mountpoint] = {
                    'total': self._convert_bytes(usage.total),
                    'used': self._convert_bytes(usage.used),
                    'free': self._convert_bytes(usage.free),
                    'percent': usage.percent
                }
            except Exception:
                continue
        return partitions

    def get_network_latency(self, host: str = default_host, port: int = default_port, timeout: int = default_timeout) -> Optional[float]:
        try:
            start_time = time.time()
            with socket.create_connection((host, port), timeout=timeout):
                end_time = time.time()
            return round((end_time - start_time) * 1000, 2)
        except (socket.timeout, socket.error):
            return None

    @classmethod
    def _convert_bytes(cls, bytes_value: int) -> str:
        for unit in cls.byte_units:
            if bytes_value < 1024:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024

    def get_all_metrics(self) -> Dict[str, Any]:
        timestamp = datetime.now().isoformat()
        return {
            'timestamp': timestamp,
            'metrics': {
                'cpu_usage': self.get_cpu_usage(),
                'memory_usage': self.get_memory_usage(),
                'disk_space': self.get_disk_space(),
                'network_latency': self.get_network_latency()
            }
        }

    def save_to_json(self, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        try:
            with open(self.data_file, 'r+') as file:
                try:
                    file_data = json.load(file)
                except json.JSONDecodeError:
                    file_data = {}
                file_data.update(data)
                file.seek(0)
                file.truncate()
                json.dump(file_data, file, indent=4)
        except IOError:
            pass