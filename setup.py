"""
Setup script for API Test Generator System.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = requirements_file.read_text(encoding="utf-8").strip().split("\n")
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith("#")]

setup(
    name="api-test-generator",
    version="1.0.0",
    description="Multi-agent system for generating JUnit 4 + Rest Assured integration tests",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="API Test Generator Team",
    author_email="team@api-test-generator.com",
    url="https://github.com/api-test-generator/api-test-generator",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=requirements,
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "api-test-generator=main:cli_main",
            "atg=main:cli_main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Code Generators",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Java",
        "Operating System :: OS Independent",
    ],
    keywords="api testing junit rest-assured openapi swagger code-generation multi-agent",
    project_urls={
        "Bug Reports": "https://github.com/api-test-generator/api-test-generator/issues",
        "Source": "https://github.com/api-test-generator/api-test-generator",
        "Documentation": "https://api-test-generator.readthedocs.io/",
    },
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.991",
            "pre-commit>=2.20.0",
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
            "myst-parser>=0.18.0",
        ],
    },
)

