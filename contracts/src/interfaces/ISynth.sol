// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/// @dev Defines an interface for a Synth token that extends IERC20 with minting and burning capabilities.
interface ISynth is IERC20 {
    /*//////////////////////////////////////////////////////////////////////////
                                  FUNCTIONS
    //////////////////////////////////////////////////////////////////////////*/

    /// @notice Mints new tokens to a specified address.
    /// @param to The address to mint the tokens to.
    /// @param amount The amount of tokens to mint.
    function mint(address to, uint256 amount) external;

    /// @notice Burns tokens from the caller's account.
    /// @param amount The amount of tokens to burn.
    function burn(uint256 amount) external;
}
