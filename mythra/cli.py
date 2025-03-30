import typer
import requests
import os
from rich.console import Console
from rich.text import Text

app = typer.Typer()
console = Console()

def find_solidity_files(base_path="."):
    sol_files = []
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".sol") and not file.startswith("I") and "interface" not in root.lower():
                sol_files.append(os.path.join(root, file))
    return sol_files

@app.command()
def run():
    print("Starting Mythra audit...\n")

    sol_files = find_solidity_files()
    if not sol_files:
        print("⚠️  No Solidity files found.")
        raise typer.Exit()

    sources = []
    for path in sol_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            sources.append({
                "path": path,
                "content": content
            })
        except Exception as e:
            print(f"❌ Failed to read {path}: {e}")

    print(f"📦 Sending {len(sources)} file(s) to Mythra server...")
    try:
        res = requests.post("http://localhost:8000/analyze", json={"contracts": sources})
        res.raise_for_status()
        report = res.json()

        severity_colors = {
            "critical": "bold red",
            "high": "red",
            "medium": "yellow",
            "low": "cyan",
            "gas": "blue",
            "unspecified": "magenta",
            "error": "bold white on red"
        }

        for result in report.get("results", []):
            print()  # space between files
            console.rule(f"[bold]📄 {result['file']}[/bold]")

            vulns = result.get("vulnerabilities", [])
            if not vulns:
                console.print("[green]✓ No vulnerabilities found[/green]")
            else:
                for v in vulns:
                    sev = v.get("severity", "unspecified").lower()
                    color = severity_colors.get(sev, "white")
                    title = v.get("title", "Unknown issue")
                    line = v.get("line", "N/A")
                    fix = v.get("fix", None)

                    # Print main vulnerability line
                    msg = Text(f" - [{sev.upper()}] {title} (line {line})", style=color)
                    console.print(msg)

                    # Optional fix suggestion
                    if fix:
                        console.print(Text(f"   💡 Fix: {fix}", style="dim"))

        print("\n✅ Done.")
    except Exception as e:
        print(f"❌ Failed to fetch audit result: {e}")
