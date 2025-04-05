import re
import sys
from pathlib import Path
from typing import Dict, List, Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.padding import Padding
from rich.text import Text
from rich.rule import Rule
from rich.theme import Theme
from rich.box import ROUNDED

# Create a custom theme for consistent, clean styling
custom_theme = Theme(
    {
        "info": "dim cyan",
        "success": "green",
        "warning": "yellow",
        "error": "bold red",
        "highlight": "bold cyan",
        "muted": "dim",
        "title": "bold blue",
        "subtitle": "blue",
        "code_title": "bold cyan",
        "optimization": "magenta",
        "gas_saved": "green",
        "file": "cyan",
        "line": "dim",
    }
)

console = Console(highlight=False, theme=custom_theme)


def display_results(results: List[Dict[str, Any]], file_path: str, model_used: str):
    """Displays the analysis results for a single file in a more readable format."""
    file_name = Path(file_path).name

    # Create a clean header for the file
    console.rule(f"[title]Analysis: [file]{file_name}[/file][/title]")

    # Show a subtle model indicator
    console.print(f"[muted]Model: {model_used}[/muted]", justify="right")

    if not results:
        console.print(
            Padding(
                "[success]✓ No gas optimizations found[/success]",
                (1, 0, 1, 2),
            )
        )
        return

    # Show optimization count
    console.print(
        Padding(
            f"[optimization]Found {len(results)} potential optimization{'s' if len(results) > 1 else ''}[/optimization]",
            (1, 0, 1, 2),
        )
    )

    # --- Summary Table ---
    summary_table = Table(
        show_header=True,
        header_style="subtitle",
        box=ROUNDED,
        expand=False,
        padding=(0, 1),
    )
    summary_table.add_column("#", style="muted", width=3, justify="right")
    summary_table.add_column("Lines", style="line", width=10, justify="right")
    summary_table.add_column("Description", style="highlight", min_width=40, ratio=2)
    summary_table.add_column("Gas Saved", style="gas_saved", width=20, ratio=1)

    # Sort by line number
    results.sort(key=lambda x: x.get("start_line") or sys.maxsize)

    for idx, opt in enumerate(results):
        line_range = "N/A"
        if opt.get("start_line") is not None:
            line_range = str(opt["start_line"])
            if opt.get("end_line") is not None and opt["end_line"] != opt["start_line"]:
                line_range += f"-{opt['end_line']}"

        summary_table.add_row(
            str(idx + 1),
            line_range,
            opt.get("description", "N/A"),
            opt.get("estimated_gas_saved") or "N/A",
        )

    console.print(Padding(summary_table, (1, 2, 2, 2)))

    # --- Detailed Findings ---
    console.print(Padding("[subtitle]Details:[/subtitle]", (1, 0, 1, 2)))

    for idx, opt in enumerate(results):
        # Create a panel for each optimization
        panel_title = f"[code_title]Optimization #{idx + 1}[/code_title]"

        # Prepare content for the panel
        panel_content = []

        # Description
        panel_content.append(Text(opt.get("description", "N/A"), style="highlight"))

        # Line numbers
        line_range = "N/A"
        if opt.get("start_line") is not None:
            line_range = str(opt["start_line"])
            if opt.get("end_line") is not None and opt["end_line"] != opt["start_line"]:
                line_range += f"-{opt['end_line']}"
        panel_content.append(
            Text.assemble(
                Text("Lines: ", style="muted"), Text(line_range, style="line")
            )
        )

        # Gas saved
        gas_saved = opt.get("estimated_gas_saved")
        if gas_saved:
            panel_content.append(
                Text.assemble(
                    Text("Gas saved: ", style="muted"),
                    Text(gas_saved, style="gas_saved"),
                )
            )

        # Safety rationale
        safety_rationale = opt.get("safety_rationale")
        if safety_rationale:
            panel_content.append(Text("Safety:", style="muted"))
            panel_content.append(Padding(Text(safety_rationale), (0, 0, 1, 2)))

        # Suggested change
        suggestion_text = opt.get("suggested_change", "").strip()
        if suggestion_text:
            # Try to detect code blocks in markdown format
            code_pattern = re.compile(r"```(?:(\w+)\n)?(.*?)```", re.DOTALL)
            code_match = code_pattern.search(suggestion_text)

            lexer = "solidity"  # Default
            code_to_highlight = suggestion_text  # Default to full text

            if code_match:
                lang_hint = (
                    code_match.group(1) or ""
                ).lower()  # Detected language hint
                code_to_highlight = code_match.group(2).strip()  # Extracted code

                if lang_hint in ["yul", "assembly"]:
                    lexer = "yul"  # Use 'yul' lexer for both
                elif lang_hint == "diff":
                    lexer = "diff"
                elif lang_hint in ["sol", "solidity"]:
                    lexer = "solidity"
                # If lang_hint is something else or empty, check content
                elif any(
                    line.strip().startswith(("-", "+", "@"))
                    for line in code_to_highlight.splitlines()
                ):
                    lexer = "diff"
                elif "assembly {" in code_to_highlight:  # Basic check for Yul block
                    lexer = "yul"
                else:
                    lexer = "solidity"  # Fallback if hint wasn't specific enough

            # If no markdown block, try basic heuristics on the whole suggestion
            elif suggestion_text.strip().startswith("assembly {"):
                lexer = "yul"
                code_to_highlight = suggestion_text  # Highlight the whole thing
            elif any(
                line.strip().startswith(("-", "+", "@"))
                for line in suggestion_text.splitlines()
            ):
                lexer = "diff"
                code_to_highlight = suggestion_text
            elif suggestion_text.strip().startswith(
                (
                    "//",
                    "contract ",
                    "function ",
                    "modifier ",
                    "event ",
                    "struct ",
                    "library ",
                    "import ",
                    "pragma ",
                )
            ):
                lexer = "solidity"
                code_to_highlight = suggestion_text
            else:
                # If it doesn't look like code, treat as plain text
                lexer = None
                code_to_highlight = suggestion_text

            panel_content.append(Text("Suggested Change:", style="muted"))  # Label
            if lexer and code_to_highlight:
                # Use detected lexer
                syntax = Syntax(
                    code_to_highlight,
                    lexer,
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                    background_color="default",
                )
                panel_content.append(
                    Padding(syntax, (0, 0, 0, 2))
                )  # Indent suggestion slightly
            else:
                # Render as plain text in a panel if no lexer determined
                panel_content.append(
                    Padding(
                        Panel(code_to_highlight, border_style="dim", expand=False),
                        (0, 0, 0, 2),
                    )
                )

        # Create and display the panel with all content
        optimization_panel = Panel(
            Group(*panel_content),
            title=panel_title,
            border_style="subtitle",
            padding=(1, 2),
            expand=False,
        )
        console.print(Padding(optimization_panel, (0, 2, 1, 2)))
