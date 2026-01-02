"""ProofPack setup - Receipts all the way down."""
from setuptools import setup, find_packages

setup(
    name="proofpack",
    version="2.0.0",
    description="ProofPack: Receipts all the way down",
    packages=find_packages(exclude=["proofpack-test", "proofpack-test.*"]),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
        ],
        "graph": [
            "networkx>=3.0",
        ],
        "mcp": [
            "mcp>=0.1",
        ],
    },
    entry_points={
        "console_scripts": [
            "proof=proofpack_cli.main:cli",
        ],
    },
)
