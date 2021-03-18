# Resource Monitor

A simple resource utilization monitor module.

## Motivation

Monitor the resource utilization, specially from a cloud hypervisor's perspective. Given that we do not have access to the platform, but we do have access to workload source code, we try to emulate the monitor process, using a thread running in user space.

## Metrics

Here we list the some of the metrics we are most interested in. Some fine-grained information which is not accessible to the platform-side monitor is intentionally ignored

* processor
  * CPU time
  * CPU percentage
  * thread information
* memory
  * physical memory in-use
  * virtual memory in-use
  * number of dirty pages
* disk
  * number of I/O operations (read and write)
  * number of bytes transferred (read and write)
* network
  * socket state related to the process (UDP / TCP, which state it is in if it is TCP)
  * number of bytes uploaded as file
  * number of bytes downloaded as file
* cloud services
  * number of cloud service API access

## Implementation

Hardware resources are monitored automatically: per-process information is available at `/proc/pid/` directory. A monitor thread periodically samples such information (through `psutil` package, which is a neat wrapper of these system information.)

For Cloud services and network usage, per-process information is not exposed by the operating system. The workload function has to explicitly call methods of our module and record the utilization.

## Usage

structure the directory: follow the [official guideline](https://cloud.google.com/functions/docs/writing/specifying-dependencies-python) and add `psutil` in top-level `requirements.txt`

```
xxx-function/
├── main.py
├── requirements.txt
└── resource_monitor
    ├── __init__.py
    └── resource_monitor.py
```

wrap the main function handler with instrument code to enable the monitor thread

```python
def function_handler(request):
    import resource_monitor as monitor
    monitor_thread = monitor.ResourceMonitorThread(0.5, 0.1, output=True)
    monitor_thread.start()
    
    # original code
    
    monitor_thread.signal_terminate()
    monitor_thread.join()
```

manually invoke monitor's record method to keep track of network activity (upload and download) and cloud service invocations

```python
# original code
blob.download_to_filename(download_path)

# instrument code
monitor_thread.record_service_invocation()
monitor_thread.record_download(os.path.getsize(download_path))
```

By default, the record will be serialized as JSON and written to standard output. It is also accessible through `ResourceMonitorThread.summary`.

Our local test, [monitor-test.py](monitor-test.py) could serve as an example.

## Limitations

* network information tracked is limited (only information about sockets)
* the thread might slow down some workloads significantly
* fine-grained instrument codes need to be inserted into function source code, manually
* monitor methods are not thread-safe: need caller-side synchronization if used to monitor multi-threaded program

## Experiences

* we have to put `requirements.txt` in the top-level directory; putting it within the module turns out not to work
* the runtime environment is "clean": we get very clean memory data, and all `pid`s allocated are small integers; however, we cannot fetch the context switch information

## Useful References

[psutil document](https://psutil.readthedocs.io/en/latest/)