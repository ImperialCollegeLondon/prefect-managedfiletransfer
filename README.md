# Prefect Managed File Transfer

<p align="center">
    <!--- Insert a cover image here -->
    <!--- <br> -->
    <a href="https://pypi.python.org/pypi/prefect-managedfiletransfer/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-managedfiletransfer?color=0052FF&labelColor=090422"></a>
    <a href="https://github.com/ImperialCollegeLondon/prefect-managedfiletransfer/" alt="Stars">
        <img src="https://img.shields.io/github/stars/ImperialCollegeLondon/prefect-managedfiletransfer?color=0052FF&labelColor=090422" /></a>
    <a href="https://pypistats.org/packages/prefect-managedfiletransfer/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-managedfiletransfer?color=0052FF&labelColor=090422" /></a>
    <a href="https://github.com/ImperialCollegeLondon/prefect-managedfiletransfer/pulse" alt="Activity">
        <img src="https://img.shields.io/github/commit-activity/m/ImperialCollegeLondon/prefect-managedfiletransfer?color=0052FF&labelColor=090422" /></a>
    <br>
</p>

Turn a prefect.io server into a managed file transfer solution. UI and Programatic creation of cron style jobs (aka Flows!) to upload and download files easily between servers. Support local, SFTP remotes plus any Cloud storage supported by rclone -  so thats aws, azure, google, sharepoint, and [many more](https://rclone.org/overview/) out of the box.

Using prefect for managed file transfer means retries, logging, multi node and [high availability](https://docs.prefect.io/v3/advanced/self-hosted) come as standard - turning prefect into a reliable enterprise ready file transfer solution. 

This package is not the fastest solution to move files around, but it prioritises reliability and ease of use, making it an excellent choice for replacing both quick cron job copy scripts and enterprise managed file transfer appliances.

Key features

- Copy, move, and delete files between almost any storage system easily.
- Reliable file operations with checksumming, file size checking etc.
- Smart and safe moving - settings to allow/block overwriting and to only copy files if they are new or changed.
- Unzip/Untar compressed folders after downloading them.
- Repath files as you move them.
- Complex filtering and ordering of files - by path, age, size etc. Pattern matching with regular expressions.
- Leverage Prefect.IO built in scheduling and orchestration capabilities:
    - Transfer files on complex cron schedules
    - notifications on success/failure - slack, email, etc
    - Highly available server architecture - database server + multi-node workers and front ends.
- Available as a [PyPi package](https://pypi.org/project/prefect-managedfiletransfer/) for integration into existing self hosted and cloud prefect deployments, and as a [docker image/appiance](https://hub.docker.com/r/managedfiletransfer/prefect-managedfiletransfer/tags)

Example use cases:

- Once per day SSH into my database server and copy the latest *.bkup file to a central storage location.
- Monitor a local network share directory for new files and automatically upload them to a cloud storage bucket.
- Schedule a weekly job to synchronize files between two remote servers.
- Move log files from a SSH available web server older than 30 days to a cold storage location, then delete the originals.
- Copy file yyyy-MM-dd.zip from a remote server, where yyyy-MM-dd matches todays date, to a local directory and then unzip it.
- Download any file in an S3 bucket larger than 1GB and store it in a local directory.
- Delete temporary files older than 7 days from a remote server to free up disk space.

Visit the full docs [here](https://imperialcollegelondon.github.io/prefect-managedfiletransfer).

### Installation - Local

Install `prefect-managedfiletransfer` with `pip`. (Requires an installation of Python 3.10+.)

```bash
pip install prefect-managedfiletransfer
# or 
uv add prefect-managedfiletransfer
```

We recommend using a Python virtual environment manager such as uv, pipenv, conda or virtualenv.

In one (venv) terminal start a prefect server with logs enabled

```bash
export PREFECT_LOGGING_LEVEL="INFO"
export PREFECT_LOGGING_EXTRA_LOGGERS="prefect_managedfiletransfer"
prefect server start
# OR uv run prefect server start
```

There are many ways to manage infrastructure and code with prefect - here we demonstate starting a local worker:

```bash
export PREFECT_API_URL=http://127.0.0.1:4200/api
# or perhaps export PREFECT_API_URL=http://host.docker.internal:4200/api
export PREFECT_LOGGING_EXTRA_LOGGERS="prefect_managedfiletransfer"
export PREFECT_LOGGING_LEVEL="INFO"
# [Optional] add all logs: export PREFECT_LOGGING_ROOT_LEVEL="INFO"


prefect worker start --pool 'default-pool' --type process

# OR add a worker with config to spawn containers that can talk to the server API:
PREFECT_API_URL=http://host.docker.internal:4200/api uv run prefect worker start --pool 'default-pool' --type=docker  

```
    
Install the blocks using the prefect CLI

```bash
prefect block register -m prefect_managedfiletransfer
```

And then deploy the flows. 

```bash
# deploy the flows to run locally
python -m prefect_managedfiletransfer.deploy --local

# OR deploy to run with a docker image - see deploy.py
python -m prefect_managedfiletransfer.deploy --docker

# or a version of the above using uv run:
uv run python -m prefect_managedfiletransfer.deploy --local
uv run python -m prefect_managedfiletransfer.deploy --docker
```

Visit the server UI http://localhost:4200.
1. Create 2 blocks, one source and one destination
2. On the deployments page start a `transfer_files_flow`. Configure your flow run to copy/move files between the 2 blocks.

Visit the full docs [here](https://imperialcollegelondon.github.io/prefect-managedfiletransfer). Note this a work in progress auto generated documentation site so it is not perfect.

### Installation - docker

Run prefect managed file transfer in a docker container, like an applicance. See [Docker hub for a list of images](https://hub.docker.com/r/managedfiletransfer/prefect-managedfiletransfer/tags)
 

Note this is ephemeral - prefect has lots of docs on how to setup a database server with it.

```bash
# run prefect server in a self-removing container port-forwarded to your local machine’s 4200 port:
docker run --rm -it -p 4200:4200 managedfiletransfer/prefect-managedfiletransfer:latest
```

### Components

**Flows**

- transfer_files_flow - a fully featured flow for transferring files between different storage locations. Supports copy and move modes.
- upload_file_flow - a flow for uploading a file to a remote server. Supports pattern matching by date.
- delete_files_flow - a flow for deleting files from a remote server based on pattern matching and filtering.

**Blocks**

- ServerWithBasicAuthBlock - A block for connecting to a server using basic authentication.
- ServerWithPublicKeyAuthBlock - A block for connecting to a server using public key authentication.
- RCloneConfigFileBlock - A block for managing RClone configuration files.

**Tasks**

- list_remote_files_task - A task for listing files in a remote directory.
- download_file_task - A task for downloading a single file from a remote server.
- upload_file_task - A task for uploading a single file to a remote server.
- delete_file_task - A task for deleting a single file from a remote server.

![Screenshot of transfer files flow](docs/img/transfer_files_screengrab.png)

### Feedback

If you encounter any bugs while using `prefect-managedfiletransfer`, feel free to open an issue in the [prefect-managedfiletransfer](https://github.com/ImperialCollegeLondon/prefect-managedfiletransfer) repository.


Feel free to star or watch [`prefect-managedfiletransfer`](https://github.com/ImperialCollegeLondon/prefect-managedfiletransfer) for updates too!

### Contributing

If you'd like to help contribute to fix an issue or add a feature to `prefect-managedfiletransfer`, please [propose changes through a pull request from a fork of the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

Here are the steps:

1. [Fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository)
2. [Clone the forked repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository)
3. Install the repository and its dependencies:
```
# install uv first, then
uv sync
```

You can also access all the prefect CLI tooling inside a uv managed venv
```
uv venv
source .venv/bin/activate
prefect server start
```

4. Make desired changes
5. Add tests
6. Insert an entry to [CHANGELOG.md](https://github.com/ImperialCollegeLondon/prefect-managedfiletransfer/blob/main/CHANGELOG.md)
7. Install `pre-commit` to perform quality checks prior to commit:
```
pre-commit install
```
8. use the build script to run all the checks and tests:

```
./build.sh
```
9. Use `./run_local.sh` to deploy a local prefect server, worker, and UI to test your changes
10. `git commit`, `git push`, and create a pull request
