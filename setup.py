"""ProofPack setup - Receipts all the way down."""
from setuptools import setup, find_packages

setup(
    name="proofpack",
    version="1.0.0",
    description="ProofPack: Receipts all the way down",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
    ],
    entry_points={
        "console_scripts": [
            "proof=proofpack_cli.main:cli",
        ],
    },
)
