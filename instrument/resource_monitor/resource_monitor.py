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


''' we use information wrapped by psutil. However psutil uses `namedtuple` extensively, which could not be extensively,
so we define our own wrapper to do this job
'''


def to_thread_dict(x): return {'id': x[0], 'user_time': x[1], 'system_time': x[2]}


def extract_cpu_info(raw_sample):
    cpu_times = dict()
    cpu_times['user'] = raw_sample['cpu_times'][0]
    cpu_times['system'] = raw_sample['cpu_times'][1]
    cpu_times['children_user'] = raw_sample['cpu_times'][2]
    cpu_times['children_system'] = raw_sample['cpu_times'][3]
    cpu_times['iowait'] = raw_sample['cpu_times'][4]

    threads = [to_thread_dict(t) for t in raw_sample['threads']]

    return {'cpu_percent': raw_sample['cpu_percent'],
            'cpu_times': cpu_times,
            'num_threads': raw_sample['num_threads'],
            'threads': threads}


def extract_mem_info(raw_sample):
    return {'memory_percent': raw_sample['memory_percent'],
            'rss': raw_sample['memory_full_info'][0],
            'vms': raw_sample['memory_full_info'][1],
            'shared': raw_sample['memory_full_info'][2],
            'text': raw_sample['memory_full_info'][3],
            'lib': raw_sample['memory_full_info'][4],
            'data': raw_sample['memory_full_info'][5],
            'dirty': raw_sample['memory_full_info'][6],
            'uss': raw_sample['memory_full_info'][7],
            'pss': raw_sample['memory_full_info'][8],
            'swap': raw_sample['memory_full_info'][9]}


def extract_disk_info(raw_sample):
    return {'num_fds': raw_sample['num_fds'],
            'read_count': raw_sample['io_counters'][0],
            'write_count': raw_sample['io_counters'][1],
            'read_bytes': raw_sample['io_counters'][2],
            'write_bytes': raw_sample['io_counters'][3],
            'read_chars': raw_sample['io_counters'][4],
            'write_chars': raw_sample['io_counters'][5]}


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
        sample['cpu'] = extract_cpu_info(raw_sample)
        sample['memory'] = extract_mem_info(raw_sample)
        sample['disk'] = extract_disk_info(raw_sample)
        sample['network'] = {'session': list(map(lambda x: x.status, raw_sample['connections'])),
                             'download': self.bytes_download,
                             'upload': self.bytes_upload}
        sample['cloud-service-trigger'] = self.cloud_service_invocation_count
        sample['elapsed_time'] = time.time() - self.create_time

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
