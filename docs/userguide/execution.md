# Concurrent and Distributed Execution

Every tool and workflow step runs as a task. A task starts as soon as the results it needs are ready. Tasks that don't depend on each other run concurrently, without waiting for each other. Within one process, tasks that draw figures take turns, because matplotlib's plotting is not thread-safe. With `LocalDaskExecutor` and `scheduler=processes`, or with a Dask cluster, each worker process draws on its own, so plots run in parallel.

The *executor* decides where the tasks run. The same options work in the GUI (`flimanalyzer`) and in [batch mode](/userguide/batch) (`flimbatch`).

| Executor | Option | Tasks run | Needs |
|---|---|---|---|
| Threads (default) | `-e LocalExecutor` | as threads in the FLIMAnalyzer process, on one computer | nothing extra |
| Dask on one computer | `-e LocalDaskExecutor` | in a local Dask cluster, as processes or threads | the `dask` extra |
| Dask cluster | `-e DaskExecutor` | on the workers of an existing Dask cluster, also on other computers | the `dask` extra |

Executor options are given with `--execargs`, as `name=value` pairs separated by commas.

## Threads (default)

By default, up to one task per CPU core runs at a time. To change that number:

```
flimanalyzer --execargs="num_workers=4"
```

`num_workers=1` runs one task at a time. Prefect's `PREFECT_TASKS_RUNNER_THREAD_POOL_MAX_WORKERS` setting, if set, is used as the default.

## Dask on one computer

Install the Dask support first: `uv sync --extra dask` (or `pip install "flimanalyzer[dask]"`). Then start a local Dask cluster with, for example, 8 worker processes:

```
flimanalyzer -e LocalDaskExecutor --execargs="scheduler=processes,num_workers=8"
```

Set `num_workers` to about the number of CPU cores. With `scheduler=threads`, the workers run as threads instead of processes.

## Dask cluster

To use a Dask cluster that is already running, give the address of its scheduler:

```
flimanalyzer -e DaskExecutor --execargs="address=tcp://<scheduler-host>:8786"
```

The workers must have the same FLIMAnalyzer version installed as the computer that starts the run.

## Limiting tasks of one kind

Prefect can limit how many tasks with a given *tag* run at the same time ([tag concurrency limits](https://docs.prefect.io/v3/develop/task-run-limits)), whichever executor is used. The limits are set on the Prefect server.

Every task is tagged with the name of its tool as shown in the menu, for example `Autoencoder: Train` (not the name of its Python class). That holds whether the tool runs on its own or as a step of a workflow. Workflow steps can carry more tags, for example the parameters of a training run in FLIM Data Augmentation Tuning; these also name the folders their results are saved in. The Prefect UI shows each task's tags.

A limit on a tool's name therefore applies to every run of that tool. For example, to let only one autoencoder training run at a time, also inside workflows:

```
prefect concurrency-limit create "Autoencoder: Train" 1
```

`prefect concurrency-limit ls` lists the limits, and `prefect concurrency-limit delete <tag>` removes one.

## Batch mode on an HPC cluster (Slurm)

On a computing cluster, `flimbatch` runs inside a Slurm job. Use as many workers as cores the job gets.

### With the Docker image (Apptainer)

Most clusters run containers with [Apptainer](https://apptainer.org/docs/user/latest/docker_and_oci.html). Convert the published image into an Apptainer image file once:

```
apptainer pull flimanalyzer.sif docker://ghcr.io/uvakcci/flimanalyzer:latest-cpu
```

`apptainer run` starts `flimbatch` in the image. Apptainer makes your home folder and the current folder available inside the container, so paths relative to the current folder work as they are. A job script for one computer (node) of the cluster:

```
#!/bin/bash
#SBATCH --job-name=flimbatch
#SBATCH --partition=<cluster_partition>
#SBATCH --nodes=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=02:00:00

apptainer run flimanalyzer.sif \
    -i data/ -o results/ -c settings.json --run "Basic FLIRR Analysis" \
    --execargs="num_workers=${SLURM_CPUS_PER_TASK}" --no-prefect-server
```

Submit it with `sbatch`. The published images don't include Dask, so they use the default executor (threads). Replace `<cluster_partition>` with a partition of your cluster (`--partition` or `-p`; `sinfo` lists them), and adjust the other `#SBATCH` lines (cores, memory, time, and an account if your cluster requires one) to your data and cluster.

### Across several nodes (Dask)

To spread the tasks over several nodes, install FLIMAnalyzer with the Dask support in a Python environment on the cluster, together with [dask-jobqueue](https://jobqueue.dask.org/en/latest/generated/dask_jobqueue.SLURMCluster.html), which starts Dask workers as Slurm jobs. In Python:

```python
from dask_jobqueue import SLURMCluster

cluster = SLURMCluster(
    queue="<cluster_partition>", cores=16, memory="32 GB", walltime="02:00:00"
)
cluster.scale(jobs=4)  # 4 Slurm jobs with Dask workers
print(cluster.scheduler_address)
```

While this Python session runs, start `flimbatch` from the same environment with the printed address:

```
flimbatch -i data/ -o results/ -c settings.json --run "Basic FLIRR Analysis" \
    -e DaskExecutor --execargs="address=<printed address>" --no-prefect-server
```

`queue` is the Slurm partition. `SLURMCluster` also takes an `account` and other Slurm options (`job_extra_directives`); see the dask-jobqueue documentation.
