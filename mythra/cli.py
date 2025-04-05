import typer
import asyncio
import questionary
from rich.console import Console
from typing import Optional, Annotated
from pathlib import Path

# Import necessary components from other modules
from .config import SUPPORTED_MODELS
from .analyzer import run_analysis

app = typer.Typer(
    name="mythra-gas",
    help="Mythra Gas Optimizer CLI - Analyzes Solidity files or directories for gas optimizations using LLMs.",
    add_completion=False,
)
console = Console(highlight=False, theme=None)


# --- Synchronous Command Entry Point ---
@app.command()
def analyze(
    target_path: Annotated[
        str,
        typer.Argument(
            help="Path to a Solidity file, directory, or a glob pattern (e.g., './contracts/**/*.sol'). Enclose globs in quotes.",
        ),
    ],
    model_name: Annotated[
        Optional[str],
        typer.Option(
            "--model",
            "-m",
            help=f"LLM model to use for analysis. If omitted, you will be prompted.",
            rich_help_panel="Model Selection",
        ),
    ] = None,
    openai_api_key: Annotated[
        Optional[str],
        typer.Option(
            "--openai-key",
            help="OpenAI API Key. Overrides OPENAI_API_KEY env var.",
            envvar="OPENAI_API_KEY",  # Use standard env var name
            rich_help_panel="API Keys",
        ),
    ] = None,
    google_api_key: Annotated[
        Optional[str],
        typer.Option(
            "--google-key",
            help="Google API Key. Overrides GOOGLE_API_KEY env var.",
            envvar="GOOGLE_API_KEY",  # Use standard env var name
            rich_help_panel="API Keys",
        ),
    ] = None,
    anthropic_api_key: Annotated[
        Optional[str],
        typer.Option(
            "--anthropic-key",
            help="Anthropic API Key. Overrides ANTHROPIC_API_KEY env var.",
            envvar="ANTHROPIC_API_KEY",  # Use standard env var name
            rich_help_panel="API Keys",
        ),
    ] = None,
    output_file: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            file_okay=True,
            dir_okay=False,
            writable=True,
            resolve_path=True,
            help="Path to save the aggregated analysis results as a JSON file.",
            rich_help_panel="Output Options",
        ),
    ] = None,
):
    """
    Analyzes Solidity files found in the target path/pattern for gas optimizations.
    """
    # --- Handle Model Selection Synchronously FIRST ---
    selected_model_name = model_name
    if selected_model_name is None:
        console.print(
            "[bold yellow]Model not specified. Please select a model:[/bold yellow]"
        )

        # Use questionary for a nice interactive selection
        try:
            # Group models by provider for better organization
            openai_models = [m for m in SUPPORTED_MODELS if m.startswith("gpt-")]
            anthropic_models = [m for m in SUPPORTED_MODELS if m.startswith("claude-")]
            gemini_models = [m for m in SUPPORTED_MODELS if m.startswith("gemini-")]

            # Create choices with provider grouping
            choices = []
            if openai_models:
                choices.append(questionary.Separator("--- OpenAI Models ---"))
                choices.extend(openai_models)
            if anthropic_models:
                choices.append(questionary.Separator("--- Anthropic Models ---"))
                choices.extend(anthropic_models)
            if gemini_models:
                choices.append(questionary.Separator("--- Google Models ---"))
                choices.extend(gemini_models)

            # Show the interactive selection
            selected_model_name = questionary.select(
                "Select a model to use:",
                choices=choices,
                default=SUPPORTED_MODELS[0] if SUPPORTED_MODELS else None,
            ).ask()

            if not selected_model_name:  # User pressed Ctrl+C in questionary
                console.print(
                    "[bold yellow]Model selection cancelled. Exiting.[/bold yellow]"
                )
                raise typer.Exit(code=1)

        except Exception as e:
            # Fallback to simple prompt if questionary fails for any reason
            console.print(
                f"[yellow]Interactive selection failed ({str(e)}). Falling back to text prompt.[/yellow]"
            )
            choices_str = ", ".join(SUPPORTED_MODELS)
            console.print(f"Available models: {choices_str}")

            selected_model_name = typer.prompt(
                "Enter the model name to use",
                default=SUPPORTED_MODELS[0] if SUPPORTED_MODELS else None,
                show_default=True,
            )

        if selected_model_name not in SUPPORTED_MODELS:
            console.print(
                f"[bold red]Error:[/bold red] Unsupported model specified: [yellow]{selected_model_name}[/yellow]"
            )
            console.print(f"Supported models are: {', '.join(SUPPORTED_MODELS)}")
            raise typer.Exit(code=1)

        console.print(f"Using selected model: [cyan]{selected_model_name}[/cyan]")
    elif selected_model_name not in SUPPORTED_MODELS:
        console.print(
            f"[bold red]Error:[/bold red] Unsupported model specified: [yellow]{selected_model_name}[/yellow]"
        )
        console.print(f"Supported models are: {', '.join(SUPPORTED_MODELS)}")
        raise typer.Exit(code=1)

    # Create a new event loop and run the async analysis function in it
    try:
        # Create a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Run the async function from the analyzer module
        loop.run_until_complete(
            run_analysis(
                target_path=target_path,
                model_name=selected_model_name,  # Pass the selected model name
                openai_api_key=openai_api_key,
                google_api_key=google_api_key,
                anthropic_api_key=anthropic_api_key,
                output_file=output_file,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Analysis interrupted by user.[/bold yellow]")
        raise typer.Exit(code=130)  # Standard exit code for SIGINT
    except Exception as e:
        console.print(f"\n[bold red]Error during analysis:[/bold red] {e}")
        # Consider adding traceback here for debugging if needed
        # import traceback
        # traceback.print_exc()
        raise typer.Exit(code=1)
    finally:
        # Clean up the event loop
        if "loop" in locals() and loop.is_running():
            loop.stop()
        if "loop" in locals():
            loop.close()
            asyncio.set_event_loop(None)


# --- Main Execution Guard ---
if __name__ == "__main__":
    app()
