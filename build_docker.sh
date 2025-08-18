#!/usr/bin/env bash
set -euo pipefail

CURRENT_TIME=$(date +%Y-%m-%dT%H:%M:%S)

IMAGE_NAME="${IMAGE_NAME:-managedfiletransfer/prefect-managedfiletransfer:local-dev}"

docker build -f Dockerfile -t $IMAGE_NAME .

# check the exit code
if [ $? -ne 0 ]; then
    echo "Docker build failed"
    exit 1
fi

ELAPSED_TIME=$(($(date +%s) - $(date -d "$CURRENT_TIME" +%s)))

echo "All tasks passed successfully in $ELAPSED_TIME seconds!"
# to run this:
printf "\nRun container with:\n  $ docker run --rm -it -p 4200:4200 $IMAGE_NAME\n\n"