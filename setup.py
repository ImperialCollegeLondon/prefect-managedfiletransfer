from setuptools import find_packages, setup

import versioneer

with open("requirements.txt") as install_requires_file:
    install_requires = install_requires_file.read().strip().split("\n")

with open("requirements-dev.txt") as dev_requires_file:
    dev_requires = dev_requires_file.read().strip().split("\n")

with open("README.md") as readme_file:
    readme = readme_file.read()

setup(
    name="prefect-managedfiletransfer",
    description="Upload and download files easily between Local/SFTP/Cloud storage using rclone",
    license="Apache License 2.0",
    author="Alastair Crabtree",
    author_email="a.crabtree@imperial.ac.uk",
    keywords="prefect",
    url="https://github.com/ImperialCollegeLondon/prefect-managedfiletransfer",
    long_description=readme,
    long_description_content_type="text/markdown",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    packages=find_packages(exclude=("tests", "docs")),
    python_requires=">=3.10",
    install_requires=install_requires,
    extras_require={"dev": dev_requires},
    entry_points={
        "prefect.collections": [
            "prefect_managedfiletransfer = prefect_managedfiletransfer",
        ]
    },
    classifiers=[
        "Natural Language :: English",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
    ],
)
