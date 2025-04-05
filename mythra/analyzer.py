import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

import typer
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule

# Import necessary functions from other modules
# --- Temporarily simplify this import for debugging ---
# from .llm import (
#     create_gas_optimization_prompt,
#     call_llm_api,
#     parse_llm_json_output,
#     get_client_details_for_model,
# )
from .llm import call_llm_api  # <-- Try importing only this

# --- Add back other imports from .llm later ---
from .llm import (
    create_gas_optimization_prompt,
    parse_llm_json_output,
    get_client_details_for_model,
)

from .display import display_results
from .file_utils import find_solidity_files

console = Console(highlight=False, theme=None)


async def analyze_single_file(
    solidity_code: str,
    model_name: str,
    file_name: Optional[str],
    openai_key: Optional[str],
    google_key: Optional[str],
    anthropic_key: Optional[str],
) -> List[Dict[str, Any]]:
    """Analyzes a single Solidity code string for gas optimizations using the specified LLM."""
    console.print(
        f"Starting analysis for '{file_name or 'source code'}' using model '{model_name}'..."
    )

    # Determine client type, API key, and potentially adjusted model name
    client_type, api_key, validated_model_name = get_client_details_for_model(
        model_name, openai_key, google_key, anthropic_key
    )

    # Create the prompt
    prompt = create_gas_optimization_prompt(solidity_code, file_name)

    # Call the LLM API
    llm_response = await call_llm_api(
        client_type=client_type,
        api_key=api_key,
        model_name=validated_model_name,
        prompt=prompt,
    )

    if llm_response is None:
        console.print(
            f"[bold red]LLM call failed to return content for {file_name} using {model_name}.[/bold red]"
        )
        return []

    # Parse the response
    parsed_suggestions = parse_llm_json_output(llm_response)
    console.print(
        f"Analysis complete for '{file_name}'. Found {len(parsed_suggestions)} valid optimization suggestions."
    )

    return parsed_suggestions


async def run_analysis(
    target_path: str,
    model_name: str,
    openai_api_key: Optional[str],
    google_api_key: Optional[str],
    anthropic_api_key: Optional[str],
    output_file: Optional[Path],
):
    """
    Finds Solidity files, runs analysis asynchronously, displays results, and saves output.
    """
    console.print(f"[info]Using model: [highlight]{model_name}[/highlight][/info]")

    # --- Find Files (Synchronous) ---
    console.print(
        f"[info]Searching for Solidity files in: [file]{target_path}[/file][/info]"
    )
    files_to_analyze = find_solidity_files(target_path)

    if not files_to_analyze:
        console.print("[error]No Solidity files found to analyze.[/error]")
        raise typer.Exit(code=1)

    console.print(
        f"[info]Found [highlight]{len(files_to_analyze)}[/highlight] Solidity files to analyze[/info]"
    )

    # --- Analyze Files (Asynchronous) ---
    all_results = {}  # Store results by file path
    errors_occurred = {}  # Track files with errors
    total_optimizations = 0  # Count total optimizations found
    skipped_files_count = 0  # Count skipped files

    # Create a progress display
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[info]{task.completed}/{task.total}[/info]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        analysis_task_id = progress.add_task(
            "[blue]Analyzing...", total=len(files_to_analyze)
        )

        tasks = []
        file_paths_for_tasks = []  # Keep track of file paths corresponding to tasks

        for file_path in files_to_analyze:
            try:
                solidity_code = file_path.read_text(encoding="utf-8")
                if not solidity_code.strip():
                    errors_occurred[str(file_path)] = "Empty file"
                    skipped_files_count += 1
                    # Update progress immediately for skipped files
                    progress.update(
                        analysis_task_id,
                        completed=skipped_files_count,  # Advance based on skipped count initially
                        description=f"[blue]Skipped empty: [dim]{file_path.name}[/dim]",
                    )
                    continue  # Skip adding a task for this file

                # Create the coroutine for analysis
                coro = analyze_single_file(
                    solidity_code=solidity_code,
                    model_name=model_name,
                    file_name=file_path.name,
                    openai_key=openai_api_key,
                    google_key=google_api_key,
                    anthropic_key=anthropic_api_key,
                )
                tasks.append(coro)  # Append the coroutine
                file_paths_for_tasks.append(file_path)  # Store corresponding path

            except Exception as e:
                errors_occurred[str(file_path)] = f"Read error: {e}"
                skipped_files_count += 1
                # Update progress immediately for read errors
                progress.update(
                    analysis_task_id,
                    completed=skipped_files_count,
                    description=f"[red]Read error: [dim]{file_path.name}[/dim]",
                )
                continue  # Skip adding a task

        # --- Execute tasks concurrently using asyncio.gather ---
        processed_task_count = 0
        if tasks:
            # return_exceptions=True allows gather to complete even if some tasks fail
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # --- Process results from gather ---
            for i, result in enumerate(results):
                file_path = file_paths_for_tasks[i]
                file_path_str = str(file_path)
                file_name = file_path.name
                # Increment progress based on processed tasks + previously skipped files
                current_progress = skipped_files_count + processed_task_count + 1

                if isinstance(result, Exception):
                    # Handle exceptions returned by gather
                    errors_occurred[file_path_str] = f"Analysis error: {result}"
                    progress.update(
                        analysis_task_id,
                        completed=current_progress,
                        description=f"[red]Analysis error: [yellow]{file_name}[/yellow]",
                    )
                elif result is not None:  # Successful analysis run
                    opt_count = len(result)
                    if opt_count > 0:
                        total_optimizations += opt_count
                        all_results[file_path_str] = {"optimizations": result}
                        progress.update(
                            analysis_task_id,
                            completed=current_progress,
                            description=f"[success]Found {opt_count} opts: [file]{file_name}[/file][/success]",
                        )
                    else:
                        all_results[file_path_str] = {"optimizations": []}
                        progress.update(
                            analysis_task_id,
                            completed=current_progress,
                            description=f"[muted]No optimizations: [file]{file_name}[/file][/muted]",
                        )
                else:  # analyze_single_file returned None (explicit failure)
                    errors_occurred[file_path_str] = (
                        "Analysis failed (LLM error or no content)"
                    )
                    progress.update(
                        analysis_task_id,
                        completed=current_progress,
                        description=f"[red]Analysis failed: [yellow]{file_name}[/yellow]",
                    )
                processed_task_count += 1  # Increment count of processed tasks

        # Ensure progress bar completes fully if only skipped files were encountered
        if not tasks and skipped_files_count > 0:
            progress.update(analysis_task_id, completed=len(files_to_analyze))

        # Final progress description
        progress.update(
            analysis_task_id, description="[green]Analysis Complete[/green]"
        )

    # --- Display Combined Results ---
    console.rule("[title]Analysis Summary[/title]")
    console.print(
        f"[info]Processed [highlight]{len(files_to_analyze)}[/highlight] files[/info]"
    )
    console.print(
        f"[info]Found a total of [optimization]{total_optimizations}[/optimization] potential optimizations using [highlight]{model_name}[/highlight][/info]"
    )
    if errors_occurred:
        console.print(
            f"[bold red]Encountered errors/skipped files in {len(errors_occurred)} cases:[/bold red]"
        )
        # Optionally print details of errors here if desired

    # Display individual results
    if all_results:
        console.print("\n--- Detailed Results ---")
        sorted_results = sorted(all_results.items())
        for file_path_str, result_data in sorted_results:
            display_results(
                result_data.get("optimizations", []), file_path_str, model_name
            )

    # --- Save aggregated results if requested ---
    if output_file:
        console.print(f"\nSaving aggregated results to [cyan]{output_file}[/cyan]...")
        try:
            sorted_all_results = dict(sorted(all_results.items()))
            sorted_errors = dict(sorted(errors_occurred.items()))

            output_data = {
                "analysis_metadata": {
                    "cli_command": " ".join(sys.argv),
                    "target_path": target_path,
                    "files_analyzed_count": len(files_to_analyze),
                    "files_with_results_count": len(sorted_all_results),
                    "files_with_errors_count": len(sorted_errors),
                    "model_used": model_name,
                },
                "results_by_file": sorted_all_results,
                "errors_by_file": sorted_errors,
            }
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            console.print(f"[green]Results successfully saved.[/green]")
        except IOError as e:
            console.print(
                f"[bold red]Error:[/bold red] Failed to write output file [cyan]{output_file}[/cyan]: {e}"
            )
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(
                f"[bold red]Error:[/bold red] An unexpected error occurred while saving results: {e}"
            )
            raise typer.Exit(code=1)
