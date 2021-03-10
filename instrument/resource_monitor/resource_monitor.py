"""Resource monitor module emulates hypervisor's monitor on general hardware resources."""

import time
import psutil
import json
import threading

# keys to monitor (provided by psutil)
# 'num_ctx_switches' would be useful but seems not to be supported by GCP
cpu_keys = ['cpu_percent', 'cpu_times', 'threads', 'num_threads']
memory_keys = ['memory_percent', 'memory_full_info']
disk_keys = ['num_fds', 'io_counters']
session_keys = ['connections']
key_set = cpu_keys + memory_keys + disk_keys + session_keys


class ResourceMonitorThread(threading.Thread):
    """A resource monitor thread which runs in parallel with the function.

    This thread is used to mimic the system profiling from hypervisor's or platform's perspective.
    Therefore, fine-grained information is dropped intentionally.

    * Hardware resources are tracked automatically through /proc/pid/*, exposed by Linux (based on psutil).
    * Cloud resources consumption is tracked manually. i.e. monitored function has to report consumption to the thread.
    """

    def __init__(self, sample_interval_second, signal_interval_second=None, output=True):
        """Constructor of the monitor Thread object
        * sample interval decides the frequency at which we sample resource utilization
        * signal interval decides how often the monitor thread checks "termination" signal;
          it is expected that signal interval should divide sample interval
        * output decides whether the samples are printed to STDIO (useful for debugging)
        """
        super(ResourceMonitorThread, self).__init__(name='monitor')

        # initialize state
        self.sample_interval_second = sample_interval_second
        if signal_interval_second is None:
            self.signal_interval_second = sample_interval_second
        else:
            self.signal_interval_second = signal_interval_second
        self.output = output
        self.summary = str()

        # construct monitor object
        self.process_util = psutil.Process()

        # note: no need for synchronization: there is only one modifier
        self.cloud_service_invocation_count = 0
        self.bytes_download = 0
        self.bytes_upload = 0
        self.create_time = self.process_util.create_time()

        # the aggregated results
        self.records = list()

        # prepare for running
        self._running = True

    def record_service_invocation(self):
        self.cloud_service_invocation_count += 1

    def record_download(self, num_bytes):
        self.bytes_download += num_bytes

    def record_upload(self, num_bytes):
        self.bytes_upload += num_bytes

    def signal_terminate(self):
        self._running = False

    def sample_utilization(self):
        raw_sample = self.process_util.as_dict(key_set)

        sample = dict()
        sample['cpu'] = {key: raw_sample[key] for key in cpu_keys}
        sample['cpu']['elapsed_time'] = time.time() - self.create_time
        sample['memory'] = {key: raw_sample[key] for key in memory_keys}
        sample['disk'] = {key: raw_sample[key] for key in disk_keys}
        sample['network'] = {
            'session': list(map(lambda x: x.status, raw_sample['connections'])),
            'download': self.bytes_download,
            'upload': self.bytes_upload
        }
        sample['cloud-service-trigger'] = self.cloud_service_invocation_count

        return sample

    def run(self):
        elapsed = 0

        while self._running:
            if elapsed >= self.sample_interval_second:
                self.records.append(self.sample_utilization())
                elapsed = 0

            time.sleep(self.signal_interval_second)
            elapsed += self.signal_interval_second

    def join(self, timeout=None):
        """override Thread.join()
        1. block caller until the thread terminates
        2. do final sampling (useful if the function duration is so short that we has not do sampling even once)
        3. log the samples
        """
        self.summary = dict(
            runtime_samples=self.records,
            final_sample=self.sample_utilization()
        )

        super().join(timeout=timeout)

        if self.output:
            print(json.dumps(self.summary))
