pragma solidity ^0.7.0;

interface CrossChainDataFeed {
	function getSlotData(uint256 chainid, address slotOwner, bytes32 slotKey) external view returns (bytes memory slotData);
	function crossChainCall(uint256 chainid, address to, uint256 gasLimit, bytes memory data) external;
}