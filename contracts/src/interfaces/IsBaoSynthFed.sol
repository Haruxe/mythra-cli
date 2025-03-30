// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

/**
 * @title IsBaoSynthFed
 * @notice Interface for the sBaoSynthFed contract, defining the structure and events.
 */
interface IsBaoSynthFed {
    /*//////////////////////////////////////////////////////////////////////////
                                EVENTS/ERRORS
    //////////////////////////////////////////////////////////////////////////*/

    /**
     * @notice Emitted when the supply is expanded
     * @param amount The amount of tokens minted
     */
    event Expansion(uint256 amount);

    /**
     * @notice Emitted when the supply is contracted
     * @param amount The amount of tokens burned
     */
    event Contraction(uint256 amount);

    /// @notice Thrown when the contraction amount exceeds the current supply
    error AmountTooLarge();

    /// @notice Thrown when minting cTokens fails
    error CTokenMintFailed();

    /// @notice Thrown when redeeming cTokens fails
    error CTokenRedeemFailed();

    /// @notice Thrown when attempting to sweep a protected token
    error CannotSweepProtectedToken();

    /// @notice Thrown when attempting to change chair if there is already an address set use revokeAndAssignChair
    error ChairAlreadySet();

    /// @notice Thrown when new address is the zero address
    error ZeroAddressNotAllowed();

    /*//////////////////////////////////////////////////////////////////////////
                                    FUNCTIONS
    //////////////////////////////////////////////////////////////////////////*/

    /**
     * @notice Expands the supply by minting new tokens
     * @param amount The amount to mint
     */
    function expansion(uint256 amount) external;

    /**
     * @notice Contracts the supply by burning tokens
     * @param amount The amount to burn
     */
    function contraction(uint256 amount) external;

    /**
     * @notice Allows the current chair to revoke his own role
     */
    function revokeChair() external;

    /**
     * @notice Removes the current governance address and sets a new governance address
     * @param newGov_ The new governance address
     */
    function revokeAndAssignGov(address newGov_) external;

    /**
     * @notice Removes the current chair address and sets a new chair address
     * @param newChair_ The new chair address
     */
    function revokeAndAssignChair(address newChair_) external;

    /**
     * @notice Sweeps other tokens except for the underlying and cToken
     * @param token The token address to sweep
     * @param amount The amount of tokens to sweep
     */
    function sweep(address token, uint256 amount) external;

    /**
     * @notice Takes profit and deposits it into sBaoSynth
     */
    function takeProfit() external;

    /**
     * @notice Returns the total assets held by the contract
     * @return The total asset amount
     */
    function totalAssets() external returns (uint256);
}
