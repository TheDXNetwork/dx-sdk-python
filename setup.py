import setuptools


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="DX.py",
    version="0.3.1",
    description="Python SDK for the DX Network, the world's first real-time marketplace for structured data",
    url="https://dx.network",
    author="The DX Network",
    author_email="info@dx.network",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    packages=setuptools.find_packages(),
    install_requires=[
        "web3",
        "eth_keyfile",
        "eth_keys",
        "eth_abi",
        "requests",
        "pygments",
        "asn1",
        "python-dateutil"
    ]
)
