// SPDX-License-Identifier: MIT
pragma solidity 0.8.26;

/**
 * @title IsBaoSynth
 * @notice Interface for the sBaoSynth contract, defining the structure and functions for a synthetic BAO token wrapper.
 * @dev This interface outlines the core functionality for depositing revenue, managing weekly revenue, and handling administrative tasks.
 */
interface IsBaoSynth {
    /*//////////////////////////////////////////////////////////////////////////
                                EVENTS/ERRORS
    //////////////////////////////////////////////////////////////////////////*/

    /// @notice Thrown when an attempt is made to sweep the contract's underlying asset
    error CannotSweepAsset();

    /// @notice Thrown when the initializer doesn't have enough of the given synth in their balance
    error InsufficientShares();

    /// @notice Thrown when attempting to initialize with zero minimum shares
    error ZeroShares();

    /// @notice Thrown when attempting to set a new owner to the zero address
    error OwnerIsZeroAddress();

    /**
     * @notice Emitted when revenue is deposited into the contract
     * @param caller The address of the user depositing revenue
     * @param amount The amount of the synth being deposited as revenue
     */
    event RevenueDeposited(address indexed caller, uint256 amount);

    /**
     * @notice Emitted when tokens are swept from the contract
     * @param token The address of the token being swept
     * @param amount The amount of tokens swept
     * @param to The address receiving the swept tokens
     */
    event Swept(address token, uint256 amount, address to);

    /**
     * @notice Emitted when the minimum shares are withdrawn from the contract
     * @param to The address receiving the minimum shares
     * @param amount The amount of minimum shares withdrawn
     */
    event MinSharesWithdrawn(address to, uint256 amount);

    /*//////////////////////////////////////////////////////////////////////////
                                    FUNCTIONS
    //////////////////////////////////////////////////////////////////////////*/

    /**
     * @notice Allows users to deposit BaoSynth as revenue
     * @dev This function should not be exposed directly to a UI due to potential loss risks
     * @param amount The amount of BaoSynth to deposit as revenue
     */
    function depositRevenue(uint256 amount) external;

    /**
     * @notice Retrieves the revenue for a specific week
     * @param week The week number to query revenue for
     * @return The amount of revenue for the specified week
     */
    function weeklyRevenue(uint256 week) external view returns (uint256);

    /**
     * @notice Allows governance to sweep any ERC20 token from the contract
     * @dev This function cannot be used to sweep the underlying BaoSynth asset
     * @param token The address of the ERC20 token to sweep
     * @param amount The amount of tokens to sweep
     * @param to The recipient address for the swept tokens
     */
    function sweep(address token, uint256 amount, address to) external;

    /**
     * @notice Calculates the current exchange rate between total assets and total shares
     * @dev This rate represents the value of one share in terms of assets
     * @return The current asset-to-share exchange rate, scaled to 1e18
     */
    function assetToShareRate() external view returns (uint256);

    /*//////////////////////////////////////////////////////////////////////////
                                    STRUCTS
    //////////////////////////////////////////////////////////////////////////*/

    /// @notice Struct containing important storage values for the sBaoSynth contract
    struct SBaoSynthStorage {
        mapping(uint256 => uint256) weeklyRevenue;
        uint256 minShares;
    }
}
