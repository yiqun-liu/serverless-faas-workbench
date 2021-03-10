# Resource Monitor

A simple resource utilization monitor module.

## Motivation

Monitor the resource utilization, specially from a cloud hypervisor's perspective. Since that we do not have access to the platform but we do have access to workload source code, we try to emulate the monitor process, using a thread running in user space.

## Monitor

At current stage we consider hardware resource consumption and cloud service invocations.

Hardware resources are monitored automatically, through `psutil` package, which extracts most information from `/proc/pid/` directory.

For Cloud services, the workload function has to explicitly call methods of this module and record the activity.

## Limitations

* network information tracked is limited (only information about sockets)
* the thread might slow down some workloads significantly
* fine-grained instrument codes need to be inserted into function source code, manually

## Useful References

[psutil document](https://psutil.readthedocs.io/en/latest/)