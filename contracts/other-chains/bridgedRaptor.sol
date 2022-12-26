pragma solidity ^0.7.0;

interface ERC20Interface {
    function totalSupply() external view returns (uint);
    function balanceOf(address tokenOwner) external view returns (uint balance);
    function allowance(address tokenOwner, address spender) external view returns (uint remaining);
    function transfer(address to, uint tokens) external returns (bool success);
    function approve(address spender, uint tokens) external returns (bool success);
    function transferFrom(address from, address to, uint tokens) external returns (bool success);
}

interface CrossChainFallback {
	function crossChainCall(address from, bytes memory data) external;
}

interface DataFeedInterface {
	function write(bytes32 variableKey, bytes memory slotData) external returns (bytes32);
}

contract Owned {
    address public owner;
    address public newOwner;
	
	mapping (address => uint256) public balanceOf;
	mapping (address => mapping (address => uint256)) allowances;

    event OwnershipTransferred(address indexed _from, address indexed _to);
	event OwnershipRenounced();

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner {
        require(msg.sender == owner);
        _;
    }

    function transferOwnership(address _newOwner) public onlyOwner {
        newOwner = _newOwner;
    }
	
	function _chainId() internal pure returns (uint256) {
		uint256 id;
		assembly {
			id := chainid()
		}
		return id;
	}
	
    function acceptOwnership() public {
        require(msg.sender == newOwner);
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
        newOwner = address(0);
    }
	
	function renounceOwnership() public onlyOwner {
		owner = address(0);
		newOwner = address(0);
		emit OwnershipRenounced();
	}
}

contract BridgedRaptor is Owned {
	address public operator;	// operator on other side of the bridge
	address public bridge;		// bridge
	
	uint256 systemNonce;


	event UnWrap(address indexed from, address indexed to, bytes32 indexed slotKey, uint256 tokens);

	modifier onlyOperator(address from) {
		require((msg.sender == bridge) && (from == operator), "ONLY_OPERATOR_CAN_DO_THAT");
		_;
	}
	
	// system internal functions
	function _recordUnwrap(address from, address to, uint256 tokens) private {
		DataFeedInterface _bridge = DataFeedInterface(bridge);
		bytes32 key = keccak256(abi.encodePacked(to, systemNonce));
		bytes memory data = abi.encode(to, tokens);
		bytes32 slotKey = _bridge.write(key, data);
		systemNonce += 1;
	}
	
	function crossChainCall(address from, bytes memory data) public onlyOperator(from) {
		
	}
}