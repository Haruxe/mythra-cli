import re
from pathlib import Path
from typing import List, TypedDict, Union


# Define a type for the dictionary returned by parse_solidity_contract
class SolidityArtifacts(TypedDict):
    path: str
    contracts: List[str]
    functions: List[str]
    modifiers: List[str]
    events: List[str]


# Pre-compile regex for efficiency
# This pattern looks for keywords followed by an identifier
# \b ensures we match whole words
# (?:...) is a non-capturing group for keywords
# \s+ matches one or more whitespace characters
# (\w+) captures the identifier (name)
SOL_IDENTIFIER_PATTERN = re.compile(r"\b(?:contract|function|modifier|event)\s+(\w+)")
# More specific patterns if needed to avoid false positives (e.g. matching variable names)
# We can refine this later if necessary. For now, let's group findings.
SOL_STRUCTURE_PATTERN = re.compile(r"\b(contract|function|modifier|event)\s+(\w+)")


def find_solidity_files(base_path: Union[str, Path] = ".") -> List[Path]:
    """
    Recursively finds all Solidity (.sol) files within a given base path.

    Args:
        base_path: The directory to start searching from. Defaults to current directory.

    Returns:
        A list of Path objects representing the found Solidity files.
    """
    base_dir = Path(base_path)
    if not base_dir.is_dir():
        raise NotADirectoryError(f"Base path '{base_path}' is not a valid directory.")
    # Use rglob for recursive globbing - simpler than os.walk
    return list(base_dir.rglob("*.sol"))


def parse_solidity_contract(file_path: Union[str, Path]) -> SolidityArtifacts:
    """
    Parses a Solidity file to extract names of contracts, functions, modifiers, and events.

    Args:
        file_path: The path to the Solidity file.

    Returns:
        A dictionary containing the file path and lists of found artifact names.
        Returns a structure with empty lists if the file cannot be read or parsed.
    """
    path_obj = Path(file_path)
    results: SolidityArtifacts = {
        "path": str(path_obj),
        "contracts": [],
        "functions": [],
        "modifiers": [],
        "events": [],
    }

    try:
        # Use pathlib's read_text for cleaner file reading
        content = path_obj.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Warning: File not found: {path_obj}")
        return results  # Return empty structure if file not found
    except IOError as e:
        print(f"Warning: Could not read file {path_obj}: {e}")
        return results  # Return empty structure on read error
    except Exception as e:
        print(f"Warning: An unexpected error occurred while reading {path_obj}: {e}")
        return results  # Catch other potential errors during read

    # Find all matches for the defined structures
    matches = SOL_STRUCTURE_PATTERN.finditer(content)

    for match in matches:
        structure_type = match.group(1)  # e.g., "contract"
        structure_name = match.group(2)  # e.g., "MyContract"

        # Append the name to the corresponding list in the results dictionary
        list_key = f"{structure_type}s"  # e.g., "contracts"
        if list_key in results:
            # Use type assertion for clarity if needed, though dynamic access is fine here
            # cast(List[str], results[list_key]).append(structure_name)
            results[list_key].append(structure_name)

    return results


# Example Usage (optional, could be removed or placed under if __name__ == "__main__":)
# if __name__ == "__main__":
#     sol_files = find_solidity_files(".") # Search in current directory
#     print(f"Found {len(sol_files)} Solidity files:")
#     for sol_file in sol_files:
#         print(f"- {sol_file}")
#         artifacts = parse_solidity_contract(sol_file)
#         print(f"  Contracts: {artifacts['contracts']}")
#         print(f"  Functions: {artifacts['functions']}")
#         print(f"  Modifiers: {artifacts['modifiers']}")
#         print(f"  Events: {artifacts['events']}")
#     print("-" * 20)

#     # Example with a non-existent file
#     parse_solidity_contract("non_existent_file.sol")
#     # Example with a specific directory
#     # try:
#     #     contract_files = find_solidity_files("contracts/src")
#     #     print(f"\nFound {len(contract_files)} files in contracts/src:")
#     #     for f in contract_files:
#     #         print(f"- {f}")
#     # except NotADirectoryError as e:
#     #     print(e)
