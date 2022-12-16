pragma solidity 0.7.0;
// SPDX-License-Identifier: Unlicensed


// this is RaptorChain data feed
// basically, it's supposed to store immutable (only write-able once) slots of data, in order to pass them to RaptorChain
// since they can't change after being written, it allows simpler management on raptorchain-side

contract DataFeed {
	struct Slot {
		address owner;
		bytes32 variable;	// variable key
		bytes data;
		uint256 timestamp;
		bool written;
	}
	
	struct Variable {
		bytes32[] history;
	}
	
	struct User {
		mapping (bytes32 => Slot) slots;
		mapping (bytes32 => Variable) variables;
	}
	
	mapping (address => User) users;
	
	event SlotWritten(address indexed slotOwner, bytes32 indexed variableKey, bytes32 indexed slotKey, bytes data);
	
	function isWritten(address owner, bytes32 key) public view returns (bool) {
		return users[owner].slots[key].written;
	}
	
	function getSlotData(address owner, bytes32 key) public view returns (bytes memory) {
		return users[owner].slots[key].data;
	}
	
	function getVariableData(address owner, bytes32 key) public view returns (bytes memory) {
		User storage user = users[owner];
		Variable storage _var = user.variables[key];
		if (_var.history.length == 0) {
			return "";
		}
		return user.slots[_var.history[_var.history.length-1]].data;
	}
	
	function write(bytes32 variableKey, bytes memory slotData) public {
		bytes32 slotKey = keccak256(abi.encodePacked(variableKey, blockhash(block.number-1)));
		require(!isWritten(msg.sender, slotKey), "ALREADY_WRITTEN");
		User storage user = users[msg.sender];
		Variable storage _var = user.variables[variableKey];
		_var.history.push(slotKey);
		Slot memory newSlot = Slot({ owner: msg.sender, variable: variableKey, data: slotData, timestamp: block.timestamp , written: true });
		user.slots[slotKey] = newSlot;
		emit SlotWritten(msg.sender, variableKey, slotKey, slotData);
	}
}