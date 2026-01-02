"""ProofPack setup - Receipts all the way down.

Note: This file exists for backwards compatibility.
      The primary build configuration is in pyproject.toml.
"""
from setuptools import setup, find_packages

setup(
    name="proofpack",
    version="0.3.2",
    description="ProofPack: Receipts-native accountability infrastructure",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
        "blake3>=0.3.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "ruff>=0.1.0",
        ],
        "graph": [
            "networkx>=3.0",
        ],
        "mcp": [
            "mcp>=0.1",
        ],
        "enterprise": [
            "pandas>=2.0.0",
            "matplotlib>=3.7.0",
            "numpy>=1.24.0",
            "scipy>=1.10.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "proofpack=proofpack.cli.main:cli",
            "proof=proofpack.cli.main:cli",  # legacy alias
        ],
    },
)
