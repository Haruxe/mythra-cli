from setuptools import setup, find_packages

setup(
    name="mythra",
    version="0.1.0",
    description="Solidity gas optimization analyzer using LLMs",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="haruxe",
    author_email="haruxe@proton.me",
    url="https://github.com/Haruxe/mythra-cli",
    packages=find_packages(),
    install_requires=[
        "typer",
        "requests",
        "rich",
        "questionary",
        "openai",
        "anthropic",
        "google-generativeai",
        "python-dotenv",
    ],
    entry_points={"console_scripts": ["mythra = mythra.cli:app"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
)
