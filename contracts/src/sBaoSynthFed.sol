// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./interfaces/ICErc20.sol";
import "./interfaces/IsBaoSynth.sol";
import "./interfaces/ISynth.sol";
import "./interfaces/IsBaoSynthFed.sol";

import {BaoOwnableRoles} from "@bao/BaoOwnableRoles.sol";

/**
 * @title sBaoSynthFed
 * @dev Contract for managing the supply of sBaoSynth tokens through expansion and contraction.
 * This contract interacts with a cToken market to manage the underlying assets.
 * WARNING: This contract holds significant control over the sBaoSynth supply. Ensure proper
 * access controls and careful management of the chair and governance roles.
 * @custom:security-contact immunefi.com/bug-bounty/baofinance/
 */
// slither-disable-next-line naming-convention lowercase s is a better description of the tokens all starting with "s"
contract sBaoSynthFed is IsBaoSynthFed, BaoOwnableRoles, ReentrancyGuard {
    ICErc20 public immutable ctoken;
    IsBaoSynth public immutable sbaosynth;
    ISynth public immutable underlying;
    address public chair;
    address public gov;
    uint256 public supply;

    using SafeERC20 for IERC20;

    /*//////////////////////////////////////////////////////////////////////////
                                   ROLE CONSTANTS
    //////////////////////////////////////////////////////////////////////////*/

    uint256 public constant ROLE_GOVERNOR = 1 << 0;
    uint256 public constant ROLE_CHAIR = 1 << 1;

    /*//////////////////////////////////////////////////////////////////////////
                               CONSTRUCTOR/INITIALIZER
    //////////////////////////////////////////////////////////////////////////*/

    /**
     * @dev Initializes the contract with core components and roles
     * @param ctoken_ cToken market contract
     * @param sbaosynth_ sBaoSynth token contract
     * @param underlying_ Underlying Synth token
     * @param chair_ Address with expansion/contraction authority
     * @param gov_ Governance address for admin functions
     */
    constructor(ICErc20 ctoken_, IsBaoSynth sbaosynth_, ISynth underlying_, address chair_, address gov_) {
        if (gov_ == address(0)) {
            revert ZeroAddressNotAllowed();
        }
        if (chair_ == address(0)) {
            revert ZeroAddressNotAllowed();
        }

        // Set the core contract addresses
        ctoken = ctoken_;
        sbaosynth = sbaosynth_;
        underlying = underlying_;

        // Approve the cToken to spend the underlying synth tokens
        IERC20(underlying).forceApprove(address(ctoken), type(uint256).max);

        // Initialize the contract owner
        _initializeOwner(msg.sender);

        // Assign roles to governance and chair addresses
        _grantRoles(gov_, ROLE_GOVERNOR);
        _grantRoles(chair_, ROLE_CHAIR);

        // Set the chair and governance addresses
        gov = gov_;
        chair = chair_;
    }

    /*//////////////////////////////////////////////////////////////////////////
                                  CHAIR FUNCTIONS
    //////////////////////////////////////////////////////////////////////////*/

    /// @inheritdoc IsBaoSynthFed
    function expansion(uint256 amount) external onlyOwnerOrRoles(ROLE_CHAIR) nonReentrant {
        // Increase the tracked supply
        supply += amount;

        // Mint new underlying tokens to this contract
        underlying.mint(address(this), amount);

        // Deposit the newly minted tokens into the cToken market
        if (ctoken.mint(amount, false) != 0) revert CTokenMintFailed();

        emit Expansion(amount);
    }

    /// @inheritdoc IsBaoSynthFed
    function contraction(uint256 amount) external onlyOwnerOrRoles(ROLE_CHAIR) nonReentrant {
        if (amount > supply) revert AmountTooLarge();

        // Decrease the tracked supply
        supply -= amount;

        // Redeem underlying tokens from the cToken market
        if (ctoken.redeemUnderlying(amount) != 0) revert CTokenRedeemFailed();

        // Burn the redeemed underlying tokens
        underlying.burn(amount);

        emit Contraction(amount);
    }

    /// @inheritdoc IsBaoSynthFed
    function revokeChair() external onlyOwnerOrRoles(ROLE_CHAIR) {
        _removeRoles(chair, ROLE_CHAIR);
        chair = address(0);
    }

    /*//////////////////////////////////////////////////////////////////////////
                                  ADMIN FUNCTIONS
    //////////////////////////////////////////////////////////////////////////*/

    /// @inheritdoc IsBaoSynthFed
    function revokeAndAssignGov(address newGov_) external onlyOwnerOrRoles(ROLE_GOVERNOR) {
        if (newGov_ == address(0)) {
            revert ZeroAddressNotAllowed(); // Revert if newGov_ is zero
        }

        _removeRoles(gov, ROLE_GOVERNOR);
        _grantRoles(newGov_, ROLE_GOVERNOR);
        gov = newGov_;
    }

    /// @inheritdoc IsBaoSynthFed
    function revokeAndAssignChair(address newChair_) external onlyOwnerOrRoles(ROLE_GOVERNOR) {
        if (newChair_ == address(0)) {
            revert ZeroAddressNotAllowed(); // Revert if newChair_ is zero
        }

        _removeRoles(chair, ROLE_CHAIR);
        _grantRoles(newChair_, ROLE_CHAIR);
        chair = newChair_;
    }

    /// @inheritdoc IsBaoSynthFed
    function sweep(address token, uint256 amount) external onlyOwnerOrRoles(ROLE_GOVERNOR) {
        if (address(underlying) == token || address(ctoken) == token) revert CannotSweepProtectedToken();
        IERC20(token).safeTransfer(gov, amount);
    }

    /*//////////////////////////////////////////////////////////////////////////
                                  PUBLIC FUNCTIONS
    //////////////////////////////////////////////////////////////////////////*/

    /// @inheritdoc IsBaoSynthFed
    function takeProfit() external nonReentrant {
        // Calculate total underlying balance including cTokens
        uint256 existingUnderlyingBalance = underlying.balanceOf(address(this));
        uint256 underlyingBalanceFromCToken = ctoken.balanceOfUnderlying(address(this));
        uint256 totalUnderlyingBalance = underlyingBalanceFromCToken + existingUnderlyingBalance;

        // Calculate profit as the excess over the tracked supply
        uint256 profit = totalUnderlyingBalance > supply ? totalUnderlyingBalance - supply : 0;

        if (profit > 0) {
            // Calculate how much needs to be redeemed from cTokens
            uint256 redeemableFromCToken = underlyingBalanceFromCToken > supply
                ? underlyingBalanceFromCToken - supply
                : 0;

            if (redeemableFromCToken > 0) {
                // Redeem the necessary amount from cTokens
                if (ctoken.redeemUnderlying(redeemableFromCToken) != 0) revert CTokenRedeemFailed();
            }

            // Approve and deposit the profit into sBaoSynth
            IERC20(underlying).forceApprove(address(sbaosynth), profit);
            sbaosynth.depositRevenue(profit);
        }
    }

    /// @inheritdoc IsBaoSynthFed
    function totalAssets() external nonReentrant returns (uint256) {
        // Sum of underlying balance in this contract and in the cToken market
        return ctoken.balanceOfUnderlying(address(this)) + underlying.balanceOf(address(this));
    }
}
