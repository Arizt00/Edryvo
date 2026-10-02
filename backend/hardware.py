"""Read-only, opt-in operating-system metrics. No drivers or elevated writes."""
from __future__ import annotations
import os
import platform
import shutil
import subprocess
import threading
import time


class HardwareMonitor:
    def __init__(self,prefs):
        self.prefs=prefs;self.lock=threading.Lock();self.last=0;self.cached={};self.gpu_time=0;self.gpu_cache=None
        try:
            import psutil
            self.ps=psutil;self.process=psutil.Process();psutil.cpu_percent(None);self.process.cpu_percent(None)
        except ImportError:self.ps=None;self.process=None
    def sample(self):
        base={'enabled':self.prefs.get('hardware.enabled'),'system':platform.system(),'machine':platform.machine(),
              'logicalCores':os.cpu_count(),'psutil':self.ps is not None,'source':'Sistema operativo · solo lectura'}
        if not base['enabled']:return base
        with self.lock:
            now=time.monotonic()
            if now-self.last<.7:return {**base,**self.cached}
            metrics={}
            if self.ps:
                memory=self.ps.virtual_memory();proc=self.process.memory_info()
                metrics={'cpuPercent':self.ps.cpu_percent(None),'memoryPercent':memory.percent,'memoryUsed':memory.used,
                    'memoryTotal':memory.total,'processRSS':proc.rss,'processCPU':self.process.cpu_percent(None),'timestamp':time.time()}
                try:
                    battery=self.ps.sensors_battery()
                    if battery:metrics['battery']={'percent':battery.percent,'plugged':battery.power_plugged}
                except (OSError,AttributeError):pass
            else:
                metrics['note']='Instala psutil para leer CPU, RAM y consumo del proceso.'
            if self.prefs.get('hardware.gpu'):
                if now-self.gpu_time>10:
                    exe=shutil.which('nvidia-smi');self.gpu_time=now;self.gpu_cache=None
                    if exe:
                        try:
                            r=subprocess.run([exe,'--query-gpu=name,utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                            if r.returncode==0:
                                self.gpu_cache=[dict(zip(('name','utilization','memoryUsedMiB','memoryTotalMiB'),[p.strip() for p in row.split(',')])) for row in r.stdout.splitlines()[:8]]
                        except (OSError,subprocess.SubprocessError):pass
                metrics['gpus']=self.gpu_cache;metrics['gpuSource']='nvidia-smi (si está disponible)'
            self.cached=metrics;self.last=now
            return {**base,**metrics}
