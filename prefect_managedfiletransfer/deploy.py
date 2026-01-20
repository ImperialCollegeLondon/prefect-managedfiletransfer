import importlib
import sys
from prefect import Flow, deploy
from prefect.docker import DockerImage

from prefect_managedfiletransfer import (
    delete_files_flow,
    transfer_files_flow,
    upload_file_flow,
)
import importlib.metadata
import packaging.requirements

from prefect_managedfiletransfer.ServerWithBasicAuthBlock import (
    ServerWithBasicAuthBlock,
)
from prefect_managedfiletransfer.RCloneConfigFileBlock import RCloneConfigFileBlock
from prefect_managedfiletransfer.ServerWithPublicKeyAuthBlock import (
    ServerWithPublicKeyAuthBlock,
)

MODULE_ID = "prefect_managedfiletransfer"


def deploy_flows(
    work_pool_name: str = "default-pool",
    tags: list[str] = ["managed-file-transfer"],
    local: bool = True,
    docker_image: str = "managedfiletransfer/prefect-managedfiletransfer",
    docker_tag: str = "main",  # or local-dev, or latest?
    build: bool = False,
    push: bool = False,
    job_variables: dict[str, str] = None,
):
    """
    Deploy the Prefect flows for the managed file transfer integration. Supports both local code and docker.
    """

    mft_flow = get_all_flows()

    to_be_deployed = []
    job_variables = job_variables or {}
    image = None

    if local:
        build = False
        push = False
    else:
        image = DockerImage(
            name=docker_image,
            tag=docker_tag,
            dockerfile="Dockerfile",
            buildargs={"SOME_AUTH_ARG": ""},
        )
    if build:
        job_variables = {**job_variables, "pip_packages": _get_dependencies()}

    for deployable in mft_flow:
        function_name = deployable.__name__
        deployment_name = deployable.__name__
        path_of_deployable = importlib.resources.files(MODULE_ID).joinpath(
            f"{deployment_name}.py"
        )
        python_entrypoint = f"{path_of_deployable}:{function_name}"

        if local:
            to_be_deployed.append(
                deployable.from_source(
                    source=str(
                        path_of_deployable.parent
                    ),  # code stored in local directory
                    entrypoint=python_entrypoint,
                ).to_deployment(
                    name=deployment_name, tags=tags, job_variables=job_variables
                )
            )
        else:
            to_be_deployed.append(
                deployable.to_deployment(
                    name=deployment_name, tags=tags, job_variables=job_variables
                )
            )

    ids = deploy(
        *to_be_deployed,
        work_pool_name=work_pool_name,
        image=image,
        build=build,
        push=push,
    )

    if len(ids) != len(to_be_deployed):
        print(f"Incomplete deployment: {ids}")
        raise ValueError("Deployment failed")


def register_blocks():
    """
    Register the Prefect blocks for the managed file transfer integration.
    """
    ServerWithBasicAuthBlock.register_type_and_schema()
    ServerWithPublicKeyAuthBlock.register_type_and_schema()
    RCloneConfigFileBlock.register_type_and_schema()


def get_all_flows() -> list[Flow]:
    """
    Return all publically shared flows in the library making custom deployment easier.
    """

    mft_flow: list[Flow] = [transfer_files_flow, upload_file_flow, delete_files_flow]

    return mft_flow


def _get_dependencies():
    rd = importlib.metadata.metadata(MODULE_ID).get_all("Requires-Dist")
    deps = []
    for req in rd:
        req = packaging.requirements.Requirement(req)
        if req.marker is not None and not req.marker.evaluate():
            continue
        deps.append(str(req))

    # hack - some envs this dependency seems to be missing, no idea why
    if "paramiko>=4.0.0" not in deps:
        deps.append("paramiko>=4.0.0")

    return deps


# # deploy the flows to run locally
# python -m prefect_managedfiletransfer.deploy --local

# # OR deploy to run with a docker image - see deploy.py
# python -m prefect_managedfiletransfer.deploy --docker

if __name__ == "__main__":
    local_debug = True

    if len(sys.argv) > 1 and sys.argv[1] == "--docker":
        local_debug = False
    if len(sys.argv) > 1 and sys.argv[1] == "--local":
        local_debug = True

    # TODO: could parse other args and pass them
    register_blocks()
    deploy_flows(local=local_debug)
