// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

interface ICErc20 {
    /*//////////////////////////////////////////////////////////////////////////
                                  FUNCTIONS
    //////////////////////////////////////////////////////////////////////////*/

    /// @notice Mints new tokens.
    /// @param amount The amount of tokens to mint.
    /// @param fresh Indicates whether the minting is fresh or not.
    /// @return A status code indicating success or failure.
    function mint(uint256 amount, bool fresh) external returns (uint256);

    /// @notice Redeems tokens for the underlying asset.
    /// @param amount The amount of the underlying asset to redeem.
    /// @return A status code indicating success or failure.
    function redeemUnderlying(uint256 amount) external returns (uint256);

    /// @notice Gets the balance of the underlying asset for the specified owner.
    /// @param owner The address of the token owner.
    /// @return The balance of the underlying asset.
    function balanceOfUnderlying(address owner) external returns (uint256);
}
