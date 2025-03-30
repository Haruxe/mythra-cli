// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract VulnerableBank {
    mapping(address => uint256) public balances;

    // Users can deposit ETH
    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }

    // Obvious reentrancy vulnerability
    function withdraw(uint256 _amount) public {
        require(balances[msg.sender] >= _amount, "Insufficient balance");

        // ❌ Sends funds before updating state
        (bool sent, ) = msg.sender.call{value: _amount}("");
        require(sent, "Failed to send Ether");

        balances[msg.sender] -= _amount;
    }

    // ❌ No access control — anyone can kill the contract
    function kill() public {
        selfdestruct(payable(msg.sender));
    }

    // ❌ Integer underflow (before Solidity 0.8)
    function unsafeSubtract(uint256 a, uint256 b) public pure returns (uint256) {
        return a - b;
    }
}
