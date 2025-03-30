from setuptools import setup, find_packages

setup(
    name="mythra",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "typer",
        "requests",
        "rich",
    ],
    entry_points={
        "console_scripts": [
            "mythra = mythra.cli:app"  # ⬅️ this should be main now, not app
        ]
    },
)
