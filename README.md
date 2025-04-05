# Mythra

A Solidity gas optimization analyzer powered by LLMs.

## Installation

```bash
pip install mythra
```

## Usage

```bash
# Analyze a single file
mythra path/to/file.sol

# Analyze all Solidity files in a directory
mythra path/to/directory/

# Analyze using a specific model
mythra path/to/file.sol --model gpt-4o

# Save results to a JSON file
mythra path/to/file.sol --output results.json
```

## Features

- Analyzes Solidity smart contracts for gas optimization opportunities
- Supports multiple LLM providers (OpenAI, Anthropic, Google)
- Interactive model selection
- Detailed optimization suggestions with safety rationales

## Requirements

- Python 3.8+
- API key for at least one of the supported LLM providers

## Contributing

Mythra is in its early stages and actively seeking contributors! The project has a modular architecture designed for customization and extension.

### Areas for Improvement

- **LLM Prompt Engineering**: Help refine the prompts to get better gas optimization suggestions
- **New LLM Providers**: Add support for additional LLM providers and models
- **UI Improvements**: Enhance the CLI interface and output formatting
- **Gas Optimization Rules**: Add built-in rules for common gas optimizations
- **Testing**: Create test cases and benchmarks for optimization accuracy
- **Documentation**: Improve documentation and examples
- **Web Interface**: Develop a web interface for the tool

### Getting Started with Development

1. Clone the repository:
   ```bash
   git clone https://github.com/Haruxe/mythra-cli.git
   cd mythra
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. Create a `.env` file with your API keys:
   ```
   OPENAI_API_KEY=your_openai_key
   ANTHROPIC_API_KEY=your_anthropic_key
   GOOGLE_API_KEY=your_google_key
   ```

4. Run the tool on a test file:
   ```bash
   python -m mythra path/to/test.sol
   ```

### Project Structure

- `mythra/cli.py`: Command-line interface
- `mythra/analyzer.py`: Core analysis orchestration
- `mythra/llm.py`: LLM API interactions
- `mythra/display.py`: Output formatting
- `mythra/config.py`: Configuration and constants
- `mythra/file_utils.py`: File handling utilities

### Customization Options

Mythra is designed to be highly customizable:

- **Custom Prompts**: Modify `create_gas_optimization_prompt()` in `llm.py` to customize how the tool interacts with LLMs
- **New LLM Providers**: Extend the `call_llm_api()` function to support additional providers
- **Output Formats**: Customize the display logic in `display.py`
- **Analysis Pipeline**: Modify the analysis workflow in `analyzer.py`

### Contribution Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

All contributions, big or small, are welcome!

## License

MIT
