#!/bin/bash

#export PREFECT_LOGGING_LEVEL="INFO"
# export PREFECT_LOGGING_ROOT_LEVEL="INFO"
export PREFECT_LOGGING_EXTRA_LOGGERS="prefect_managedfiletransfer"

prefect config set PREFECT_SERVER_API_HOST=0.0.0.0
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api

echo "Starting Prefect server... as managed file transfer applicance"

# Start the first process
prefect server start &
pidServer=$!

# wait for the server to start - prefect can be slow
sleep 15

# Start the worker process
prefect worker start --pool 'default-pool' --type process &
pidWorker=$!

# Deploy our app
uv run --no-editable prefect block register -m prefect_managedfiletransfer
if [ $? -ne 0 ]; then
    echo "Failed to register blocks"
    exit 1
fi
uv run --no-editable python -m prefect_managedfiletransfer.deploy --local
if [ $? -ne 0 ]; then
    echo "Failed to deploy application"
    exit 1
fi

# Wait for any process to exit
wait -n $pidServer $pidWorker

# Exit with status of process that exited first
exit $?