import os
import re

def find_solidity_files(base_path="."):
    return [
        os.path.join(root, file)
        for root, _, files in os.walk(base_path)
        for file in files if file.endswith(".sol")
    ]

def parse_solidity_contract(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "path": file_path,
        "contracts": re.findall(r'\\bcontract\\s+(\\w+)', content),
        "functions": re.findall(r'\\bfunction\\s+(\\w+)', content),
        "modifiers": re.findall(r'\\bmodifier\\s+(\\w+)', content),
        "events": re.findall(r'\\bevent\\s+(\\w+)', content)
    }