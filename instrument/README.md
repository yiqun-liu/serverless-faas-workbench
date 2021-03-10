# Resource Monitor

A simple resource utilization monitor module.

## Motivation

Monitor the resource utilization, specially from a cloud hypervisor's perspective. Since that we do not have access to the platform but we do have access to workload source code, we try to emulate the monitor process, using a thread running in user space.

## Monitor

At current stage we consider hardware resource consumption and cloud service invocations.

Hardware resources are monitored automatically, through `psutil` package, which extracts most information from `/proc/pid/` directory.

For Cloud services, the workload function has to explicitly call methods of this module and record the activity.

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



## Limitations

* network information tracked is limited (only information about sockets)
* the thread might slow down some workloads significantly
* fine-grained instrument codes need to be inserted into function source code, manually

## Experiences

* we have to put `requirements.txt` in the top-level directory; putting it within the module turns out not to work
* the runtime environment is "clean": we get very clean memory data, and all `pid`s allocated are small integers; however, we cannot fetch the context switch information

## Useful References

[psutil document](https://psutil.readthedocs.io/en/latest/)