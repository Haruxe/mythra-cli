from pathlib import Path
from typing import List
from rich.console import Console

console = Console(highlight=False, theme=None)


def find_solidity_files(path_pattern: str) -> List[Path]:
    """Finds Solidity files based on a path or glob pattern."""
    base_path = Path(".")
    try:
        if "*" in path_pattern or "?" in path_pattern or "[" in path_pattern:
            # Handle glob patterns relative to the current directory or absolute paths
            if Path(path_pattern).is_absolute():
                # Use Path().glob for absolute paths to avoid joining with base_path
                files = list(Path().glob(path_pattern))
            else:
                # Use base_path.glob for relative paths
                files = list(base_path.glob(path_pattern))
        else:
            input_path = Path(path_pattern)
            if not input_path.exists():
                console.print(
                    f"[bold red]Error:[/bold red] Input path does not exist: [yellow]{path_pattern}[/yellow]"
                )
                return []
            if input_path.is_file():
                if input_path.suffix.lower() == ".sol":
                    files = [input_path]
                else:
                    console.print(
                        f"[bold yellow]Warning:[/bold yellow] Input file is not a .sol file: [yellow]{input_path}[/yellow]"
                    )
                    files = []
            elif input_path.is_dir():
                # Recursively find all .sol files in the directory
                files = list(input_path.rglob("*.sol"))
            else:
                console.print(
                    f"[bold red]Error:[/bold red] Input path is neither a file nor a directory: [yellow]{path_pattern}[/yellow]"
                )
                return []

        # Filter one last time to ensure only files with .sol suffix are included
        sol_files = [f for f in files if f.is_file() and f.suffix.lower() == ".sol"]

        if not sol_files:
            console.print(
                f"[yellow]No .sol files found matching pattern:[/yellow] [cyan]{path_pattern}[/cyan]"
            )

        return sol_files
    except Exception as e:
        console.print(f"[bold red]Error finding Solidity files:[/bold red] {e}")
        return []
