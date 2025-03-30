// SPDX-License-Identifier: MIT
pragma solidity 0.8.26;

import {IsBaoSynth} from "./interfaces/IsBaoSynth.sol";

import {ERC4626Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC20/extensions/ERC4626Upgradeable.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

import {BaoOwnable} from "@bao/BaoOwnable.sol";

/**
 * @title sBaoSynth
 * @dev Auto-compounding ERC4626 wrapper for sBao* synthetic tokens.
 * @author Bao Finance
 * @custom:security-contact immunefi.com/bug-bounty/baofinance
 * WARNING: This vault is safe as collateral but NOT as a borrowable asset.
 * Do not use in protocols where sudden large value increases could be risky.
 */
//slither-disable-next-line naming-convention
contract sBaoSynth is IsBaoSynth, ERC4626Upgradeable, UUPSUpgradeable, BaoOwnable {
    using SafeERC20 for IERC20;

    /// @notice The duration of one revenue period, set to 7 days
    uint256 private constant PERIOD = 7 days;

    /// @notice Precision factor for share calculations, equal to 1 ether (1e18)
    uint256 private constant SHARE_PRECISION = 1 ether;

    /*//////////////////////////////////////////////////////////////////////////
                               INTERNAL DATA
    //////////////////////////////////////////////////////////////////////////*/

    /**
     * @dev keccak256(abi.encode(uint256(keccak256("bao.storage.sBaoSynth")) - 1)) & ~bytes32(uint256(0xff));
     */
    bytes32 private constant SBAOSYNTHS = 0x2a0a4f18e92346647b28b178305e236e1a4a051a6459d8e156d492b387236500;

    /*//////////////////////////////////////////////////////////////////////////
                               CONSTRUCTOR/INITIALIZER
    //////////////////////////////////////////////////////////////////////////*/

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @dev Initializes contract
     * @param owner_ Owner address
     * @param minShares_ Min locked shares
     * @param baosynth_ Underlying token address
     * @param name_ Token name
     * @param symbol_ Token symbol
     * @custom:important Deployer must approve proxy for minShares_ of underlying token
     * @custom:important Deployer needs enough underlying tokens to mint minShares_
     */
    function initialize(
        address owner_,
        uint256 minShares_,
        address baosynth_,
        string memory name_,
        string memory symbol_
    ) external initializer {
        if (owner_ == address(0)) {
            revert OwnerIsZeroAddress();
        }
        if (minShares_ == 0) {
            revert ZeroShares();
        }
        if (IERC20(baosynth_).balanceOf(msg.sender) < minShares_) {
            revert InsufficientShares();
        }

        _initializeOwner(owner_);
        __UUPSUpgradeable_init();
        __ERC20_init(name_, symbol_);
        __ERC4626_init(IERC20(baosynth_));

        SBaoSynthStorage storage s = _getSBaoSynthStorage();
        s.minShares = minShares_;
        _deposit(msg.sender, owner_, minShares_, minShares_);
    }

    /*//////////////////////////////////////////////////////////////////////////
                                  PUBLIC FUNCTIONS
    //////////////////////////////////////////////////////////////////////////*/

    /// @inheritdoc IsBaoSynth
    function depositRevenue(uint256 amount_) external {
        IERC20 baosynth = IERC20(asset());

        // Use max balance if amount_ is max uint256
        if (amount_ == type(uint256).max) {
            amount_ = baosynth.balanceOf(msg.sender);
        }

        // Transfer tokens to contract
        baosynth.safeTransferFrom(msg.sender, address(this), amount_);

        // Update weekly revenue
        SBaoSynthStorage storage s = _getSBaoSynthStorage();
        s.weeklyRevenue[block.timestamp / PERIOD] += amount_;

        emit RevenueDeposited(msg.sender, amount_);
    }

    /*//////////////////////////////////////////////////////////////////////////
                                  PROTECTED FUNCTIONS
    //////////////////////////////////////////////////////////////////////////*/

    /// @inheritdoc IsBaoSynth
    function sweep(address token_, uint256 amount_, address to_) external onlyOwner {
        if (asset() == token_) {
            revert CannotSweepAsset();
        }

        if (amount_ == type(uint256).max) {
            amount_ = IERC20(token_).balanceOf(address(this));
        }

        IERC20(token_).safeTransfer(to_, amount_);

        emit Swept(token_, amount_, to_);
    }

    /// @inheritdoc IsBaoSynth
    function assetToShareRate() external view returns (uint256 rate_) {
        uint256 totalShares = IERC20(address(this)).totalSupply();
        uint256 totalAssetBalance = totalAssets();

        // Calculate rate, scaled by 1e18. totalShares > 0 due to minShares.
        rate_ = (totalAssetBalance * SHARE_PRECISION) / totalShares;
    }

    /// @inheritdoc IsBaoSynth
    function weeklyRevenue(uint256 week_) public view returns (uint256 revenue_) {
        SBaoSynthStorage storage s = _getSBaoSynthStorage();
        revenue_ = s.weeklyRevenue[week_];
    }

    /**
     * @notice Calculates the total assets controlled by the contract.
     * @dev Weekly revenue is distributed linearly over the following week.
     * This function accounts for the gradual distribution of the previous week's revenue
     * and excludes the current week's revenue from the total.
     * @return totalAssets_ The total assets in the contract, adjusted for revenue distribution.
     */
    function totalAssets() public view override returns (uint256 totalAssets_) {
        uint256 currentPeriod = block.timestamp / PERIOD;
        // slither-disable-next-line weak-prng
        uint256 timeElapsed = block.timestamp % PERIOD;
        SBaoSynthStorage storage s = _getSBaoSynthStorage();

        // Check if currentPeriod is zero to avoid edge cases
        // This is used for test cases when testing against a pristine EVM
        // slither-disable-start incorrect-equality
        // slither-disable-next-line timestamp
        if (currentPeriod == 0) {
            // slither-disable-end incorrect-equality
            return ERC4626Upgradeable.totalAssets();
        }

        // Calculate remaining revenue from last week
        uint256 remainingLastRevenue = (s.weeklyRevenue[currentPeriod - 1] * (PERIOD - timeElapsed)) / PERIOD;

        // Exclude undistributed revenue from total assets
        totalAssets_ = ERC4626Upgradeable.totalAssets() - remainingLastRevenue - s.weeklyRevenue[currentPeriod];
    }

    /*//////////////////////////////////////////////////////////////////////////
                                  INTERNAL FUNCTIONS
    //////////////////////////////////////////////////////////////////////////*/

    /**
     * @dev Retrieves a reference to the contract's storage structure
     * @return s A storage reference to the SBaoSynthStorage struct
     */
    function _getSBaoSynthStorage() internal pure returns (SBaoSynthStorage storage s) {
        assembly {
            s.slot := SBAOSYNTHS
        }
    }

    /**
     * @dev Authorization check for contract upgrades
     * @param newImplementation Address of the new implementation
     */
    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}
}
