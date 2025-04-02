import typer
import requests
import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)
from typing import Dict, List, Optional, Annotated, Any
from pathlib import Path

# Import the scanner functions
from .scanner import (
    find_solidity_files as scanner_find_files,
)  # Use alias to avoid name clash

app = typer.Typer(
    name="mythra",
    help="Mythra Solidity Analyzer CLI - Analyzes Solidity code for vulnerabilities using the Mythra API.",
    add_completion=False,
)
# Keep highlight=False for manual color control
console = Console(highlight=False)

# --- Configuration ---
# You might want to make this configurable via env var or command-line arg
# DEFAULT_API_ENDPOINT = "http://127.0.0.1:8000/analyze"
DEFAULT_API_ENDPOINT = os.environ.get(
    "MYTHRA_API_ENDPOINT", "http://127.0.0.1:8000/analyze"
)


# --- Helper Functions (find_solidity_files, map_vulnerability_to_severity) ---
def map_vulnerability_to_severity(vulnerability_type: str, confidence: float) -> str:
    """Maps vulnerability type and confidence to a severity level (heuristic)."""
    # (Keep existing mapping logic)
    vuln_lower = vulnerability_type.lower()
    if (
        "reentrancy" in vuln_lower
        or "access control" in vuln_lower
        or "delegatecall" in vuln_lower
        or "arbitrary storage" in vuln_lower
        or "oracle manipulation" in vuln_lower
        or "logic error" in vuln_lower
        or "initialization" in vuln_lower
        or "unchecked call return" in vuln_lower
    ):
        return "high"
    if (
        "integer overflow" in vuln_lower
        or "external contract interaction" in vuln_lower
        or "timestamp dependence" in vuln_lower
        or "denial of service" in vuln_lower
        or "dos" in vuln_lower
        or "erc20" in vuln_lower
        or "token standard" in vuln_lower
        or "insufficient input validation" in vuln_lower
    ):
        return "medium"
    if (
        "gas" in vuln_lower
        or "front-running" in vuln_lower
        or "rounding error" in vuln_lower
        or "deprecated" in vuln_lower
        or "event emission" in vuln_lower
        or "visibility" in vuln_lower
    ):
        return "low"
    if vulnerability_type == "High Severity":
        return "high"
    if vulnerability_type == "Medium Severity":
        return "medium"
    if vulnerability_type == "Low Severity":
        return "low"
    if confidence > 0.85:
        return "high"
    if confidence > 0.65:
        return "medium"
    if confidence > 0.4:
        return "low"
    return "unspecified"


def read_file_content(file_path: str) -> Optional[str]:
    """Reads the content of a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Use bold red for Error prefix
        console.print(
            f"   [bold red]Error:[/bold red] File not found: [cyan]{file_path}[/cyan]"
        )
        return None
    except Exception as e:
        console.print(
            f"   [bold red]Error:[/bold red] Failed to read file [cyan]{file_path}[/cyan]: {e}"
        )
        return None


def display_results(results: List[Dict[str, Any]], threshold: float, file_count: int):
    """Displays the analysis results in a formatted table."""
    # Use a subtle color for the rule
    console.rule("[bold blue]Analysis Complete[/]")

    vulnerabilities_found = []
    for file_result in results:
        file_name = file_result.get(
            "file_path", file_result.get("path", "Unknown File")
        )
        findings = file_result.get("findings", [])
        for finding in findings:
            if finding.get("confidence", 0.0) >= threshold:
                vulnerabilities_found.append(
                    {
                        "file": file_name,
                        "vulnerability": finding.get("vulnerability", "Unknown"),
                        "confidence": finding.get("confidence", 0.0),
                        "details": finding.get("details", "N/A"),
                    }
                )

    if not vulnerabilities_found:
        console.print(
            # Use green for success message
            f"[green]Finished.[/green] No vulnerabilities found above the threshold ({threshold:.2f}) in {file_count} file(s)."
        )
        return

    # Use yellow for the count of potential issues
    console.print(
        f"[yellow]Found {len(vulnerabilities_found)} potential vulnerabilities (confidence >= {threshold:.2f}):[/yellow]"
    )

    table = Table(
        title="Potential Vulnerabilities",
        show_header=True,
        header_style="bold magenta",  # Bring back header color
        box=None,
        show_lines=False,
    )
    # Reintroduce column styles
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Vulnerability", style="yellow")
    table.add_column("Confidence", style="bold green", justify="right")
    # table.add_column("Details", style="dim") # Add if details become available

    for vuln in sorted(
        vulnerabilities_found, key=lambda x: (x["file"], -x["confidence"])
    ):
        table.add_row(
            vuln["file"],
            vuln["vulnerability"],
            f"{vuln['confidence']:.2%}",
            # vuln["details"]
        )

    console.print(table)


# --- Typer Command ---
@app.command()
def analyze(
    paths: Annotated[
        Optional[List[str]],
        typer.Argument(
            help="List of Solidity files or directories to analyze. Defaults to current directory if none provided.",
            show_default=False,
        ),
    ] = None,
    api_endpoint: Annotated[
        str, typer.Option("--api", "-a", help="Mythra API endpoint URL.")
    ] = DEFAULT_API_ENDPOINT,
    threshold: Annotated[
        float,
        typer.Option(
            "--threshold",
            "-t",
            min=0.0,
            max=1.0,
            help="Minimum confidence threshold to report vulnerabilities (0.0 to 1.0).",
        ),
    ] = 0.5,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help="Recursively search for .sol files in directories.",
            show_default=False,
        ),
    ] = False,  # <--- CHANGE: Default to non-recursive search
    output_file: Annotated[
        Optional[str],
        typer.Option(
            "--output", "-o", help="Path to save the analysis results (JSON)."
        ),
    ] = None,
):
    """
    Analyzes Solidity files for vulnerabilities using the Mythra API.
    """
    # Use a subtle color for the main title rule
    console.rule("[bold blue]Mythra Solidity Analyzer[/]")
    console.print("Starting analysis...")
    # Keep link style
    console.print(f"Using API endpoint: [link={api_endpoint}]{api_endpoint}[/link]")
    console.print(f"Minimum confidence threshold: {threshold:.2f}")
    # Adjust the print based on the new default
    if recursive:
        console.print(
            "Recursive search: [green]Enabled[/green] (via -r/--recursive flag)"
        )
    else:
        console.print(
            "Recursive search: [yellow]Disabled[/yellow] (default, use -r/--recursive to enable)"
        )

    solidity_files_paths = []
    # Default to current directory '.' if no paths are provided (paths is None)
    target_paths = paths if paths else ["."]

    console.print("\nSearching for Solidity files...")
    for path_arg in target_paths:
        p = Path(path_arg)
        if p.is_file() and p.suffix == ".sol":
            # Check if file already added to avoid duplicates from overlapping inputs
            if p not in solidity_files_paths:
                solidity_files_paths.append(p)
            else:
                console.print(f"[dim]Skipping duplicate file: {p}[/dim]")
        elif p.is_dir():
            if recursive:
                try:
                    # scanner_find_files is already recursive
                    found_files = scanner_find_files(p)
                    # Add only new files
                    new_files_count = 0
                    for f in found_files:
                        if f not in solidity_files_paths:
                            solidity_files_paths.append(f)
                            new_files_count += 1
                    if new_files_count > 0:
                        console.print(
                            f"[dim]Found {new_files_count} file(s) in {p}[/dim]"
                        )
                    elif not found_files:
                        console.print(f"[dim]No .sol files found in {p}[/dim]")

                except (
                    NotADirectoryError
                ):  # Should not happen due to is_dir check, but safe
                    console.print(
                        f"[bold red]Error:[/bold red] Path is not a valid directory: {p}"
                    )
                except Exception as e:
                    console.print(
                        f"[bold red]Error:[/bold red] Failed to scan directory {p}: {e}"
                    )
            else:
                # Find files only in the top-level directory if not recursive
                try:
                    found_files = [f for f in p.glob("*.sol") if f.is_file()]
                    new_files_count = 0
                    for f in found_files:
                        if f not in solidity_files_paths:
                            solidity_files_paths.append(f)
                            new_files_count += 1
                    if new_files_count > 0:
                        console.print(
                            f"[dim]Found {new_files_count} file(s) in top-level of {p}[/dim]"
                        )
                    else:
                        console.print(
                            f"[dim]No .sol files found directly in {p}. Use -r to search subdirectories.[/dim]"
                        )
                except Exception as e:
                    console.print(
                        f"[bold red]Error:[/bold red] Failed to list files in directory {p}: {e}"
                    )

        elif p.is_file() and p.suffix != ".sol":
            console.print(f"[yellow]Skipping non-Solidity file:[/yellow] {p}")
        else:
            # Use yellow for warnings about paths
            console.print(
                f"[yellow]Warning:[/yellow] Path not found or invalid: {path_arg}"
            )

    # Sort paths for consistent order
    solidity_files_paths.sort()

    if not solidity_files_paths:
        console.print(
            "\n[bold red]Error:[/bold red] No Solidity files found to analyze. Exiting."
        )
        raise typer.Exit(code=1)

    console.print(
        f"\nFound [bold]{len(solidity_files_paths)}[/bold] unique file(s) for analysis."
    )

    contracts_data = []
    files_to_process_paths = []  # Store Path objects

    # --- Step 1: Read Solidity Files ---
    with Progress(
        SpinnerColumn(style="blue"),  # Add color to spinner
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,  # Keep transient
    ) as progress:
        read_task = progress.add_task(
            "[cyan]Reading Solidity files...", total=len(solidity_files_paths)
        )
        for file_path_obj in solidity_files_paths:
            file_path_str = str(file_path_obj)
            try:
                content = file_path_obj.read_text(encoding="utf-8")
                if not content.strip():
                    # Use dim style for less important skips
                    console.print(f"[dim]Skipping empty file: {file_path_str}[/dim]")
                    progress.update(read_task, advance=1)
                    continue

                contracts_data.append(
                    {
                        "path": file_path_str,
                        "content": content,
                    }
                )
                files_to_process_paths.append(file_path_obj)
            except FileNotFoundError:
                # Should be rare now, but handle defensively
                console.print(
                    f"[yellow]Skipping missing file: {file_path_str}[/yellow]"
                )
            except UnicodeDecodeError:
                console.print(
                    f"[yellow]Skipping file with encoding error: {file_path_str}[/yellow]"
                )
            except Exception as e:
                console.print(
                    # Use yellow for non-critical read errors
                    f"[yellow]Skipping file due to error reading: {file_path_str} ({e})[/yellow]"
                )
            progress.update(read_task, advance=1)

    if not contracts_data:
        console.print(
            "\n[bold red]Error:[/bold red] Failed to read any valid Solidity files. Exiting."
        )
        raise typer.Exit(code=1)

    # --- Step 2: Send ONE API request ---
    payload = {"contracts": contracts_data}
    analysis_results = []
    error_occurred = False

    console.print(f"\nSending {len(contracts_data)} contract(s) to API for analysis...")
    try:
        response = requests.post(api_endpoint, json=payload, timeout=120)

        if response.status_code == 200:
            try:
                response_data = response.json()
                if "results" in response_data and isinstance(
                    response_data["results"], list
                ):
                    analysis_results = response_data["results"]
                    # Use green for success
                    console.print("[green]Analysis successful.[/green]")
                else:
                    console.print(
                        "[bold red]Error:[/bold red] API response missing 'results' list."
                    )
                    error_occurred = True

            except json.JSONDecodeError:
                console.print(
                    f"[bold red]Error:[/bold red] Invalid JSON response received from the server."
                )
                error_occurred = True

        elif response.status_code == 422:
            try:
                error_detail = response.json().get("detail", "No details provided.")
                # Use bold red for API error prefix
                console.print(
                    f"   [bold red]API Error ({response.status_code} Unprocessable Entity):[/bold red] Validation failed."
                )
                # Add border color back to panel for errors
                console.print(
                    Panel(
                        json.dumps(error_detail, indent=2),
                        title="[red]Validation Error Details[/]",
                        border_style="red",
                    )
                )
            except json.JSONDecodeError:
                console.print(
                    f"   [bold red]API Error ({response.status_code} Unprocessable Entity):[/bold red] Could not decode error details."
                )
            error_occurred = True
        else:
            console.print(
                # Use bold red for API error prefix
                f"   [bold red]API Error ({response.status_code}):[/bold red] {response.text}"
            )
            error_occurred = True

    except requests.exceptions.RequestException as e:
        console.print(
            # Use bold red for Network error prefix
            f"   [bold red]Network Error:[/bold red] Failed to connect to API at {api_endpoint}: {e}"
        )
        error_occurred = True
    except Exception as e:
        console.print(
            # Use bold red for Unexpected error prefix
            f"   [bold red]Unexpected Error during API call:[/bold red] {e}"
        )
        error_occurred = True

    # --- Step 3: Display results ---
    if not error_occurred:
        display_results(analysis_results, threshold, len(files_to_process_paths))

        # --- Step 4: Save results if requested ---
        if output_file:
            console.print(f"\nSaving results to [cyan]{output_file}[/cyan]...")
            try:
                output_data = {
                    "analysis_metadata": {
                        "api_endpoint": api_endpoint,
                        "threshold": threshold,
                        "recursive_search": recursive,
                        "files_analyzed_count": len(files_to_process_paths),
                        "files_analyzed_paths": [
                            str(p) for p in files_to_process_paths
                        ],
                    },
                    "results": analysis_results,
                }
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                # Use green for success
                console.print(f"[green]Results successfully saved.[/green]")
            except IOError as e:
                console.print(
                    f"[bold red]Error:[/bold red] Failed to write output file [cyan]{output_file}[/cyan]: {e}"
                )
            except Exception as e:
                console.print(
                    f"[bold red]Error:[/bold red] An unexpected error occurred while saving results: {e}"
                )

    else:
        # Use red rule for failure
        console.rule("[bold red]Analysis Failed[/bold red]")
        console.print(
            "Please check the errors above and ensure the API server is running correctly."
        )
        raise typer.Exit(code=1)


# --- Main Execution Guard ---
if __name__ == "__main__":
    app()
