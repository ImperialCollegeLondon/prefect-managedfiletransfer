#!/bin/bash

uv sync
if [ $? -ne 0 ]; then
    echo "Failed to deploy application"
    exit 1
fi

./prefect_managedfiletransfer/run_as_standalone_server.sh