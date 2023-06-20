pragma solidity ^0.7.0;

interface ConsensusInfoInterface {
	// following method allows to know whether an address is a masternode or not
	function isMN(address addr) external view returns (bool);
	// following method returns masternode owner - address 0 if MN don't exist
	function mnOwner(address operator) external view returns (address);
}