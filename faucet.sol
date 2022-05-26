pragma solidity ^0.7.0;

contract RaptorTestnetFaucet {
	mapping (address => uint256) public lastClaim;
	uint256 public claimTime = 86400; // 24 hours
	uint256 public faucetPrize = 1000000000000000000000; // 1000 tRPTR
	
	modifier claimDelay {
		require((block.timestamp - lastClaim[msg.sender]) >= claimTime, "Can only claim once in 24hrs");
		lastClaim[msg.sender] = block.timestamp;
		_;
	}
	
	function claim() public claimDelay {
		payable(msg.sender).transfer(faucetPrize);
	}
	
	
	
	fallback() external {
	}
	
	receive() external payable {
	}
}