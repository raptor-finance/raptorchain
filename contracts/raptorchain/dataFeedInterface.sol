pragma solidity ^0.7.0;

interface CrossChainDataFeed {
	function getSlotData(uint256 chainid, address slotOwner, bytes32 slotKey) external view returns (bytes memory slotData);
}