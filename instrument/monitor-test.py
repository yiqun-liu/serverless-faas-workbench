"""
A simple local test script for resource monitor
"""

import resource_monitor as monitor
from multiprocessing import Process, Queue
import os
import time
import json

# test configurations
# limit the log entries to the stressed resources
STRIP_DOWN = True
# results displayed in JSON format
JSON_OUTPUT = False

SEPARATOR = '*' * 40 + '\n'


def file_io_test(q, num_bytes_to_write):

    monitor_thread = monitor.ResourceMonitorThread(0.5, 0.1, output=False)
    monitor_thread.start()

    begin = time.time()

    to_write = str(bytearray(num_bytes_to_write))
    with open('/tmp/file-io-test.txt', 'w') as file:
        file.write(to_write)

    duration = time.time() - begin

    monitor_thread.signal_terminate()
    monitor_thread.join()

    # focus on disks
    summary = monitor_thread.summary
    if STRIP_DOWN:
        summary['runtime_samples'] = list(map(lambda x: x['disk'], summary['runtime_samples']))
        summary['final_sample'] = summary['final_sample']['disk']
    if JSON_OUTPUT:
        summary = json.dumps(summary, indent=2)

    digest = 'FILE-IO TEST\n' \
             + SEPARATOR + \
             'process-id: %s\n' \
             'bytes to write: %d\n' \
             '"time" library measured execution time: %f s\n' \
             'logs: %s' % (os.getpid(), num_bytes_to_write, duration, summary)

    q.put(digest)


def execution_time_test(q, expect_time_second):
    monitor_thread = monitor.ResourceMonitorThread(0.5, 0.1, output=False)
    monitor_thread.start()

    begin = time.time()

    time.sleep(expect_time_second)

    duration = time.time() - begin

    monitor_thread.signal_terminate()
    monitor_thread.join()

    summary = monitor_thread.summary
    if STRIP_DOWN:
        # focus on cpu
        summary['runtime_samples'] = list(map(lambda x: x['cpu'], summary['runtime_samples']))
        summary['final_sample'] = summary['final_sample']['cpu']
    if JSON_OUTPUT:
        summary = json.dumps(summary, indent=2)

    digest = 'EXECUTION TIME TEST (WITH IDLE PROCESSOR)\n' \
             + SEPARATOR + \
             'process-id: %s\n' \
             'expect execution time (wall-clock time): %f s\n' \
             '"time" library measured execution time: %f s\n' \
             'logs: %s' % (os.getpid(), expect_time_second, duration, summary)

    q.put(digest)


def cpu_usage_test(q, min_time_second):
    monitor_thread = monitor.ResourceMonitorThread(0.5, 0.1, output=False)
    monitor_thread.start()

    begin = time.time()

    while time.time() - monitor_thread.create_time < min_time_second:
        j = 0
        for _ in range(100000):
            j += 1

    duration = time.time() - begin

    monitor_thread.signal_terminate()
    monitor_thread.join()

    summary = monitor_thread.summary
    if STRIP_DOWN:
        # focus on cpu
        summary['runtime_samples'] = list(map(lambda x: x['cpu'], summary['runtime_samples']))
        summary['final_sample'] = summary['final_sample']['cpu']
    if JSON_OUTPUT:
        summary = json.dumps(summary, indent=2)

    digest = 'EXECUTION TIME TEST (WITH BUSY PROCESSOR)\n' \
             + SEPARATOR + \
             'process-id: %s\n' \
             'min execution time (wall-clock time): %f s\n' \
             '"time" library measured execution time: %f s\n' \
             'logs: %s' % (os.getpid(), min_time_second, duration, summary)

    q.put(digest)


def mem_usage_test(q, num_bytes_to_allocate, min_time_second):
    monitor_thread = monitor.ResourceMonitorThread(0.5, 0.1, output=False)
    monitor_thread.start()

    begin = time.time()

    keep_memory = bytearray(num_bytes_to_allocate)
    time.sleep(min_time_second)

    duration = time.time() - begin

    monitor_thread.signal_terminate()
    monitor_thread.join()

    # focus on memory
    summary = monitor_thread.summary
    if STRIP_DOWN:
        summary['runtime_samples'] = list(map(lambda x: x['memory'], summary['runtime_samples']))
        summary['final_sample'] = summary['final_sample']['memory']
    if JSON_OUTPUT:
        summary = json.dumps(summary, indent=2)

    digest = 'MEMORY USAGE TEST\n' \
             + SEPARATOR + \
             'process-id: %s\n' \
             'expected memory usage: %d\n' \
             'min execution time (wall-clock time): %f s\n' \
             '"time" library measured execution time: %f s\n' \
             'logs: %s' % (os.getpid(), len(keep_memory), min_time_second, duration, summary)

    q.put(digest)


if __name__ == '__main__':
    print('test started.\n')

    queue = Queue()
    processes = [
        Process(target=file_io_test, args=(queue, 256 * 1024,)),
        Process(target=execution_time_test, args=(queue, 4,)),
        Process(target=execution_time_test, args=(queue, 2,)),
        Process(target=cpu_usage_test, args=(queue, 2)),
        Process(target=mem_usage_test, args=(queue, 128 * 1024 * 1024, 2,)),
    ]

    for p in processes:
        p.start()

    for i in range(len(processes)):
        print(queue.get())
        print('')

    queue.close()

    for p in processes:
        p.join()

    print('test completed.\n')
