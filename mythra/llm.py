import asyncio
import json
import re
from typing import Dict, List, Optional, Any, Tuple

import typer
from rich.console import Console

# LLM Client Libraries
from openai import (
    AsyncOpenAI,
    RateLimitError as OpenAIRateLimitError,
    APIError as OpenAIAPIError,
    APIConnectionError as OpenAIAPIConnectionError,
    BadRequestError as OpenAIBadRequestError,
    AuthenticationError as OpenAIAuthenticationError,
)
import google.generativeai as genai
from google.api_core.exceptions import (
    ResourceExhausted as GeminiResourceExhausted,
    GoogleAPIError as GeminiAPIError,
    ClientError as GeminiClientError,
    NotFound as GeminiNotFound,
    PermissionDenied as GeminiPermissionDenied,
)
from anthropic import (
    AsyncAnthropic,
    RateLimitError as AnthropicRateLimitError,
    APIError as AnthropicAPIError,
    APIConnectionError as AnthropicAPIConnectionError,
    BadRequestError as AnthropicBadRequestError,
    AuthenticationError as AnthropicAuthenticationError,
)

# Import config values
from .config import (
    GEMINI_MODELS,
    OPENAI_MODELS,
    ANTHROPIC_MODELS,
    DEFAULT_GOOGLE_API_KEY,
    DEFAULT_OPENAI_API_KEY,
    DEFAULT_ANTHROPIC_API_KEY,
    LLM_TIMEOUT,
    LLM_MAX_RETRIES,
    LLM_RETRY_DELAY_BASE,
)

console = Console(highlight=False, theme=None)


def parse_llm_json_output(llm_output: str) -> List[Dict[str, Any]]:
    """Attempts to parse JSON suggestions from the LLM response string."""
    suggestions = []
    try:
        # Try parsing the whole string as JSON first
        data = json.loads(llm_output)
        if isinstance(data, list):
            suggestions = data
        elif (
            isinstance(data, dict)
            and "optimizations" in data
            and isinstance(data["optimizations"], list)
        ):
            suggestions = data["optimizations"]
        else:
            console.print(
                f"[yellow]Warning:[/yellow] Parsed JSON but root is not a list or expected dict structure"
            )
            # Fallback to regex if initial parse fails structure check

    except json.JSONDecodeError:
        console.print(
            f"[yellow]Warning:[/yellow] LLM output was not valid JSON. Attempting regex extraction."
        )
        # Regex to find JSON objects within ```json ... ``` blocks or standalone
        json_pattern = re.compile(
            r"```(?:json)?\s*(\[.*?\])\s*```|(?<!`)(\[(?:[^\[\]]|\[[^\[\]]*\])*\])(?!`)",
            re.DOTALL | re.MULTILINE,
        )
        matches = json_pattern.findall(llm_output)

        if matches:
            for match_group in matches:
                json_str = next(
                    (m for m in match_group if m), None
                )  # Find the non-empty capture group
                if json_str:
                    try:
                        # Basic validation: must start with [ and end with ]
                        if json_str.strip().startswith(
                            "["
                        ) and json_str.strip().endswith("]"):
                            parsed_list = json.loads(json_str)
                            if isinstance(parsed_list, list):
                                suggestions.extend(parsed_list)
                                console.print(
                                    f"[green]Successfully extracted {len(parsed_list)} suggestions via regex.[/green]"
                                )
                                # Don't break here, maybe there are multiple valid lists? Aggregate them.
                            else:
                                console.print(
                                    f"[yellow]Warning:[/yellow] Regex found JSON, but it's not a list"
                                )
                        else:
                            console.print(
                                f"[yellow]Warning:[/yellow] Regex found potential JSON list, but structure seems invalid"
                            )
                    except json.JSONDecodeError:
                        console.print(
                            f"[yellow]Warning:[/yellow] Regex found potential JSON, but failed to parse"
                        )
        else:
            console.print(
                f"[bold red]Error:[/bold red] Failed to parse LLM output as JSON and no JSON list found via regex."
            )

    # Basic validation of list items
    validated_suggestions = []
    for item in suggestions:
        if (
            isinstance(item, dict)
            and "description" in item
            and "suggested_change" in item
            and "safety_rationale" in item
        ):
            # Ensure lines are ints or None
            item["start_line"] = (
                int(item["start_line"])
                if isinstance(item.get("start_line"), (int, float, str))
                and str(item.get("start_line")).isdigit()
                else None
            )
            item["end_line"] = (
                int(item["end_line"])
                if isinstance(item.get("end_line"), (int, float, str))
                and str(item.get("end_line")).isdigit()
                else None
            )
            validated_suggestions.append(item)
        else:
            console.print(
                f"[yellow]Warning:[/yellow] Skipping invalid suggestion structure in parsed list"
            )

    return validated_suggestions


def create_gas_optimization_prompt(solidity_code: str, file_name: Optional[str]) -> str:
    """Creates the detailed prompt for the LLM."""
    context_fn = f" for the file '{file_name}'" if file_name else ""

    # Define example JSON objects using triple quotes to avoid escaping issues
    standard_example = """
{
  "description": "Cache storage variable `owner` in memory within the loop",
  "suggested_change": "// Original:\\n// for (uint i = 0; i < addresses.length; i++) {\\n//   require(msg.sender == owner, \\\"Not owner\\\");\\n//   ...\\n// }\\n\\n// Optimized:\\naddress cachedOwner = owner;\\nfor (uint i = 0; i < addresses.length; i++) {\\n  require(msg.sender == cachedOwner, \\\"Not owner\\\");\\n  ...\\n}",
  "estimated_gas_saved": "Saves significant gas (reduces SLOAD operations inside loop)",
  "safety_rationale": "Caching the storage variable `owner` in memory (`cachedOwner`) is safe because `owner` is not modified within the loop. This avoids repeated SLOAD opcodes (which are expensive) without changing the access control logic. Assumes standard Solidity behavior.",
  "start_line": 45,
  "end_line": 50
}
"""

    safe_unchecked_example = """
{
  "description": "Use unchecked math for counter increments in for-loop",
  "suggested_change": "// Original:\\n// for (uint256 i = 0; i < length; i++) {\\n//   // loop body\\n// }\\n\\n// Optimized:\\nfor (uint256 i = 0; i < length;) {\\n  // loop body\\n  unchecked { ++i; }\\n}",
  "estimated_gas_saved": "Saves ~30-40 gas per loop iteration",
  "safety_rationale": "This optimization is safe because the loop counter `i` starts at 0 and is only incremented by 1 each iteration. The loop terminates when `i` reaches `length`. Since `i` will always be less than `length` (which is bounded by array size) and increments by only 1, it's mathematically impossible for `i` to overflow a uint256 which can hold values up to 2^256-1 (far larger than any practical array length). This is NOT safe because of access control, but because of the mathematical properties of the operation itself.",
  "start_line": 120,
  "end_line": 122
}
"""

    assembly_example = """
{
  "description": "Use Yul assembly for efficient copying of bytes array",
  "suggested_change": "```solidity\\n// Original (example):\\n// function copyBytes(bytes memory _source) internal pure returns (bytes memory) {\\n//     bytes memory target = new bytes(_source.length);\\n//     for (uint i = 0; i < _source.length; i++) {\\n//         target[i] = _source[i];\\n//     }\\n//     return target;\\n// }\\n\\n// Optimized (using assembly):\\nfunction copyBytesAssembly(bytes memory _source) internal pure returns (bytes memory target) {\\n    assembly {\\n        target := mload(0x40) // Get free memory pointer\\n        let len := mload(_source) // Get source length\\n        mstore(target, len) // Store length in target\\n        let mc := add(target, 0x20) // Target content pointer\\n        let sc := add(_source, 0x20) // Source content pointer\\n\\n        // Copy 32 bytes at a time\\n        for { let i := 0 } lt(i, len) { i := add(i, 32) } {\\n            mstore(add(mc, i), mload(add(sc, i)))\\n        }\\n\\n        // Update free memory pointer - ensure allocation is multiple of 32\\n        let newFreePtr := add(target, add(0x20, and(add(len, 31), not(31))))\\n        mstore(0x40, newFreePtr)\\n    }\\n}\\n```",
  "estimated_gas_saved": "Significant gas savings for large byte arrays compared to Solidity loop",
  "safety_rationale": "This Yul assembly code performs a memory-to-memory copy. It's safe because: 1. It correctly reads the length from the source array. 2. It allocates memory using the free memory pointer (0x40) and stores the length correctly in the target array. 3. It copies data in 32-byte chunks, handling potential overlaps correctly within the loop structure. 4. It correctly updates the free memory pointer afterwards, ensuring proper memory management and preventing corruption of subsequent memory allocations. This implementation avoids the per-byte bounds checking and overhead of the Solidity loop. Assumes standard EVM memory layout.",
  "start_line": 70,
  "end_line": 85
}
"""

    # Main prompt with references to the examples
    prompt = f"""
Analyze the following Solidity smart contract code{context_fn} for potential gas optimizations.

**Your Task:**
1.  Identify specific areas in the code where gas usage can be reduced **without changing the core logic or introducing security vulnerabilities.** Focus on safe, commonly accepted optimizations, **but also consider advanced techniques where appropriate and demonstrably safe.**
2.  **Advanced Techniques:** Where significant gas can be saved safely, consider suggesting optimizations involving:
    *   **Yul/Assembly:** For low-level operations (e.g., memory management, specific math operations) if it provides a clear benefit and can be implemented safely.
    *   **Bit Shifting/Masking:** For efficient packing/unpacking of data or calculations.
    *   **Custom Memory Allocation:** If standard methods are inefficient for a specific use case (use with extreme caution).
    *   Other low-level optimizations applicable to the EVM.
3.  For each optimization found, provide the following details in a JSON list format. Each item in the list should be a JSON object with these exact keys:
    *   `"description"`: (string) A clear explanation of the gas optimization technique (e.g., "Use immutable variable", "Cache storage variable in memory", "Optimize loop", "Use calldata instead of memory", "Use assembly for efficient memory copy").
    *   `"suggested_change"`: (string) The specific code modification required. Show the relevant original lines commented out and the new lines below them, or provide a clear textual description of the change. Use standard markdown for code blocks (e.g., ```solidity ... ``` or ```yul ... ```) if helpful within the string.
    *   `"estimated_gas_saved"`: (string | null) An estimate of the gas savings (e.g., "Saves ~100 gas per call", "Reduces deployment cost significantly", "Minor savings", "Significant savings via assembly"). Use null if estimation is not feasible or highly variable.
    *   `"safety_rationale"`: (string) **Crucially, explain in detail why this change is safe.** Confirm that it does not alter the contract's intended external behavior, introduce reentrancy risks, overflow/underflow issues (especially with assembly/unchecked math), access control problems, memory corruption, or other vulnerabilities. State clearly if the optimization relies on specific Solidity version behavior or optimizer settings. **For assembly suggestions, this rationale is paramount.**
    *   `"start_line"`: (integer | null) The approximate starting line number in the original code where the suggested change applies. Use null if not applicable to a specific line.
    *   `"end_line"`: (integer | null) The approximate ending line number in the original code where the suggested change applies. Use null if not applicable to a specific line range.

**IMPORTANT SAFETY CONSTRAINTS:**

1. **NEVER suggest using `unchecked` blocks for arithmetic operations solely because they are "protected by access control" or "called only by admin/owner".** Access control is not a sufficient safety mechanism for arithmetic operations. Each `unchecked` block must be mathematically proven safe based on the operation itself.

2. **For `unchecked` math operations**, you must demonstrate that:
   * For additions: It's mathematically impossible to overflow (e.g., proven bounds on inputs, or the sum is always less than max uint256)
   * For subtractions: It's mathematically impossible to underflow (e.g., proven that a ≥ b before a - b)
   * For multiplications: It's mathematically impossible to overflow (e.g., proven bounds on inputs)
   * For divisions: It's mathematically impossible to divide by zero (e.g., explicit checks)

3. **For assembly code**, you must explain exactly how memory safety, type safety, and control flow safety are maintained.

4. **For any optimization that removes checks**, you must provide a mathematical or logical proof of why those checks are redundant, not just state that they're unlikely to be triggered.

**Example JSON Objects:**

*Standard Optimization:*
{standard_example}

*Safe Unchecked Math Example:*
{safe_unchecked_example}

*Advanced Optimization (Assembly Example):*
{assembly_example}

**Important Constraints:**
*   **SAFETY IS PARAMOUNT:** Only suggest optimizations that are **demonstrably safe** and do not change the contract's intended external behavior or security posture. **Provide a detailed safety rationale for every suggestion, especially for assembly.** If unsure about safety, do not suggest the optimization.
*   **Output Format:** Respond ONLY with a single JSON list containing the optimization objects as described above. Do not include any introductory text, explanations outside the JSON structure, code block markers like ```json at the start/end of the entire response, or concluding remarks. If no safe optimizations are found, respond with an empty JSON list `[]`.

**Solidity Code to Analyze:**
```solidity
{solidity_code}
```

Respond ONLY with the JSON list of optimizations:
"""
    return prompt


async def call_llm_api(
    client_type: str, api_key: str, model_name: str, prompt: str
) -> Optional[str]:
    """Calls the appropriate LLM API using the provided key, with retry logic."""
    console.print(f"[info]Calling {client_type} model...[/info]", end="")

    # Define retryable exceptions for each client type
    retryable_exceptions = (
        # OpenAI
        OpenAIRateLimitError,
        OpenAIAPIError,
        OpenAIAPIConnectionError,
        # Gemini (using google.api_core.exceptions)
        GeminiResourceExhausted,
        GeminiAPIError,
        # Anthropic
        AnthropicRateLimitError,
        AnthropicAPIError,
        AnthropicAPIConnectionError,
        # General asyncio timeout
        asyncio.TimeoutError,
    )
    # Define non-retryable authentication/permission errors
    auth_exceptions = (
        OpenAIAuthenticationError,
        GeminiPermissionDenied,
        AnthropicAuthenticationError,
    )
    # Define non-retryable bad request errors (often invalid model or prompt issues)
    bad_request_exceptions = (
        OpenAIBadRequestError,
        GeminiClientError,
        GeminiNotFound,
        AnthropicBadRequestError,
    )

    try:
        for attempt in range(LLM_MAX_RETRIES + 1):
            try:
                if client_type == "openai":
                    client = AsyncOpenAI(api_key=api_key, timeout=LLM_TIMEOUT)
                    response = await client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert Solidity gas optimization assistant.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.1,  # Low temperature for more deterministic responses
                        max_tokens=4000,  # Adjust based on expected response size
                    )
                    if response.choices and response.choices[0].message.content:
                        return response.choices[0].message.content
                    else:
                        console.print(
                            "[bold red]Error:[/bold red] OpenAI response structure unexpected or content missing."
                        )
                        return None  # Indicate failure

                elif client_type == "gemini":
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(model_name)
                    response = await model.generate_content_async(
                        [prompt],
                        generation_config={
                            "temperature": 0.1,
                            "max_output_tokens": 8192,
                        },
                    )
                    if response.text:
                        return response.text
                    else:
                        console.print(
                            "[bold red]Error:[/bold red] Gemini response structure unexpected or content missing."
                        )
                        return None  # Indicate failure

                elif client_type == "anthropic":
                    client = AsyncAnthropic(api_key=api_key, timeout=LLM_TIMEOUT)
                    response = await client.messages.create(
                        model=model_name,
                        max_tokens=4000,
                        system="You are an expert Solidity gas optimization assistant.",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                    )
                    if (
                        response.content
                        and isinstance(response.content, list)
                        and response.content[0].text
                    ):
                        return response.content[0].text
                    else:
                        console.print(
                            "[bold red]Error:[/bold red] Anthropic response structure unexpected or content missing."
                        )
                        return None  # Indicate failure

                break  # If we get here, the call succeeded

            except retryable_exceptions as e:
                if attempt < LLM_MAX_RETRIES:
                    wait_time = LLM_RETRY_DELAY_BASE * (
                        2**attempt
                    )  # Exponential backoff
                    console.print(
                        f"[warning]Retrying LLM call ({attempt + 1}/{LLM_MAX_RETRIES}) after {wait_time}s[/warning]"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    console.print(
                        f"[error]Error:[/error] LLM call failed after {LLM_MAX_RETRIES} retries: {e}"
                    )
                    return None

    except auth_exceptions as auth_err:
        console.print(
            f"[error]Authentication Error ({client_type}):[/error] {auth_err}"
        )
        raise typer.Exit(code=1)
    except bad_request_exceptions as bad_req_err:
        console.print(
            f"[error]Bad Request Error ({client_type}):[/error] {bad_req_err}"
        )
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(
            f"[error]Unexpected error during LLM API call ({client_type}):[/error] {e}"
        )
        raise typer.Exit(code=1)

    # Should not be reached if retry logic works, but as a fallback
    console.print(
        f"[error]LLM call failed after {LLM_MAX_RETRIES} retries for {client_type} model {model_name}.[/error]"
    )
    return None


def get_client_details_for_model(
    model_name: str,
    openai_key: Optional[str],
    google_key: Optional[str],
    anthropic_key: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Determines the client type, the API key to use, and the validated model name."""
    model_name_lower = model_name.lower()
    client_type = None
    key_to_use = None
    validated_model_name = model_name  # Start with original name

    if any(prefix in model_name_lower for prefix in GEMINI_MODELS):
        client_type = "gemini"
        key_to_use = google_key or DEFAULT_GOOGLE_API_KEY
        # Gemini might need the 'models/' prefix, ensure it's there if not provided
        if not model_name.startswith("models/"):
            validated_model_name = f"models/{model_name}"
            console.print(
                f"[dim]Prepended 'models/' to Gemini model name: {validated_model_name}[/dim]"
            )

    elif any(prefix in model_name_lower for prefix in OPENAI_MODELS):
        client_type = "openai"
        key_to_use = openai_key or DEFAULT_OPENAI_API_KEY

    elif any(prefix in model_name_lower for prefix in ANTHROPIC_MODELS):
        client_type = "anthropic"
        key_to_use = anthropic_key or DEFAULT_ANTHROPIC_API_KEY
    else:
        console.print(
            f"[bold red]Error:[/bold red] Unsupported or unknown model name prefix: {model_name}"
        )
        raise ValueError(f"Unsupported or unknown model name: {model_name}")

    if not key_to_use:
        console.print(
            f"[bold red]Error:[/bold red] {client_type.capitalize()} model '{model_name}' requested, but no API key provided or found in environment."
        )
        raise ValueError(
            f"API key required for {client_type.capitalize()} model '{model_name}', but none was provided or found in environment."
        )

    console.print(f"[dim]Using {client_type} model: {validated_model_name}[/dim]")
    return client_type, key_to_use, validated_model_name
