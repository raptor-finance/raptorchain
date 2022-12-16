pragma solidity 0.7.0;
// SPDX-License-Identifier: Unlicensed


// this is RaptorChain data feed
// basically, it's supposed to store immutable (only write-able once) slots of data, in order to pass them to RaptorChain
// since they can't change after being written, it allows simpler management on raptorchain-side

contract DataFeed {
	struct Slot {
		address owner;
		bytes32 key;
		bytes data;
		uint256 timestamp;
		bool written;
	}
	
	mapping (address => mapping (bytes32 => Slot)) public slots;
	
	event SlotWritten(address indexed slotOwner, bytes32 indexed slotKey, bytes data);
	
	function isWritten(address owner, bytes32 key) public view returns (bool) {
		return slots[owner][key].written;
	}
	
	function getSlotData(address owner, bytes32 key) public view returns (bytes memory) {
		return slots[owner][key].data;
	}
	
	function writeSlot(bytes32 key, bytes memory slotData) public {
		require(!isWritten(msg.sender, key), "ALREADY_WRITTEN");
		Slot memory newSlot = Slot({ owner: msg.sender, key: key, data: slotData, timestamp: block.timestamp , written: true });
		slots[msg.sender][key] = newSlot;
		emit SlotWritten(msg.sender, key, slotData);
	}
}