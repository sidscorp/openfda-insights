#!/usr/bin/env python3
"""
Setup script for Enhanced FDA Explorer
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="enhanced-fda-explorer",
    version="1.0.0",
    author="Dr. Sidd Nambiar",
    author_email="sidd.nambiar@example.com",
    description="Next-generation FDA medical device data exploration platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/siddnambiar/enhanced-fda-explorer",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Healthcare Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=0.991",
            "pre-commit>=2.20.0",
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.2.0",
            "sphinx-autodoc-typehints>=1.19.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "fda-explorer=enhanced_fda_explorer.cli:main",
            "fda-server=enhanced_fda_explorer.server:main",
            "fda-web=enhanced_fda_explorer.web:main",
        ],
    },
    include_package_data=True,
    package_data={
        "enhanced_fda_explorer": ["config/*.yaml", "templates/*.html", "static/*"],
    },
)