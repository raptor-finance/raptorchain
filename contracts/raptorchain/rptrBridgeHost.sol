pragma solidity ^0.7.0;
// SPDX-License-Identifier: MIT

// this is RaptorChain side of token bridge
// holds RPTR while it's wrapped to polygon
// processes both wrap and unwrap

// WRAP
// - RaptorChain-side custody contract (holds RPTR) calls RaptorChain-side datafeed (address(0xfeed))
// - RaptorChain-side datafeed throws a cross-chain message
// - a RaptorChain masternode includes it into a beacon block
// - beacon block gets forwarded to Polygon-side handler
// - handler unpacks call and calls token contract
// - token contract mints token

// UNWRAP
// - user calls `unwrap` method
// - contract burns polygon-side token
// - contract writes data to a slot on polygon-side datafeed (slots can be accessed by raptorchain-side contracts)
// - raptorchain-side custody contract calls raptorchain-side datafeed, which returns slot data
// - raptorchain-side custody contract marks slot as processed (to avoid getting it processed twice)
// - raptorchain-side custody sends RPTR to recipient

interface CrossChainDataFeed {
	function getSlotData(uint256 chainid, address slotOwner, bytes32 slotKey) external view returns (bytes memory slotData);
	function crossChainCall(uint256 chainid, address to, uint256 gasLimit, bytes memory data) external;
}

library SafeMath {
    /**
     * @dev Returns the addition of two unsigned integers, reverting on
     * overflow.
     *
     * Counterpart to Solidity's `+` operator.
     *
     * Requirements:
     *
     * - Addition cannot overflow.
     */
    function add(uint256 a, uint256 b) internal pure returns (uint256) {
        uint256 c = a + b;
        require(c >= a, "SafeMath: addition overflow");

        return c;
    }

    /**
     * @dev Returns the subtraction of two unsigned integers, reverting on
     * overflow (when the result is negative).
     *
     * Counterpart to Solidity's `-` operator.
     *
     * Requirements:
     *
     * - Subtraction cannot overflow.
     */
    function sub(uint256 a, uint256 b) internal pure returns (uint256) {
        return sub(a, b, "SafeMath: subtraction overflow");
    }

    /**
     * @dev Returns the subtraction of two unsigned integers, reverting with custom message on
     * overflow (when the result is negative).
     *
     * Counterpart to Solidity's `-` operator.
     *
     * Requirements:
     *
     * - Subtraction cannot overflow.
     */
    function sub(uint256 a, uint256 b, string memory errorMessage) internal pure returns (uint256) {
        require(b <= a, errorMessage);
        uint256 c = a - b;

        return c;
    }

    /**
     * @dev Returns the multiplication of two unsigned integers, reverting on
     * overflow.
     *
     * Counterpart to Solidity's `*` operator.
     *
     * Requirements:
     *
     * - Multiplication cannot overflow.
     */
    function mul(uint256 a, uint256 b) internal pure returns (uint256) {
        // Gas optimization: this is cheaper than requiring 'a' not being zero, but the
        // benefit is lost if 'b' is also tested.
        // See: https://github.com/OpenZeppelin/openzeppelin-contracts/pull/522
        if (a == 0) {
            return 0;
        }

        uint256 c = a * b;
        require(c / a == b, "SafeMath: multiplication overflow");

        return c;
    }

    /**
     * @dev Returns the integer division of two unsigned integers. Reverts on
     * division by zero. The result is rounded towards zero.
     *
     * Counterpart to Solidity's `/` operator. Note: this function uses a
     * `revert` opcode (which leaves remaining gas untouched) while Solidity
     * uses an invalid opcode to revert (consuming all remaining gas).
     *
     * Requirements:
     *
     * - The divisor cannot be zero.
     */
    function div(uint256 a, uint256 b) internal pure returns (uint256) {
        return div(a, b, "SafeMath: division by zero");
    }

    /**
     * @dev Returns the integer division of two unsigned integers. Reverts with custom message on
     * division by zero. The result is rounded towards zero.
     *
     * Counterpart to Solidity's `/` operator. Note: this function uses a
     * `revert` opcode (which leaves remaining gas untouched) while Solidity
     * uses an invalid opcode to revert (consuming all remaining gas).
     *
     * Requirements:
     *
     * - The divisor cannot be zero.
     */
    function div(uint256 a, uint256 b, string memory errorMessage) internal pure returns (uint256) {
        require(b > 0, errorMessage);
        uint256 c = a / b;
        // assert(a == b * c + a % b); // There is no case in which this doesn't hold

        return c;
    }

    /**
     * @dev Returns the remainder of dividing two unsigned integers. (unsigned integer modulo),
     * Reverts when dividing by zero.
     *
     * Counterpart to Solidity's `%` operator. This function uses a `revert`
     * opcode (which leaves remaining gas untouched) while Solidity uses an
     * invalid opcode to revert (consuming all remaining gas).
     *
     * Requirements:
     *
     * - The divisor cannot be zero.
     */
    function mod(uint256 a, uint256 b) internal pure returns (uint256) {
        return mod(a, b, "SafeMath: modulo by zero");
    }

    /**
     * @dev Returns the remainder of dividing two unsigned integers. (unsigned integer modulo),
     * Reverts with custom message when dividing by zero.
     *
     * Counterpart to Solidity's `%` operator. This function uses a `revert`
     * opcode (which leaves remaining gas untouched) while Solidity uses an
     * invalid opcode to revert (consuming all remaining gas).
     *
     * Requirements:
     *
     * - The divisor cannot be zero.
     */
    function mod(uint256 a, uint256 b, string memory errorMessage) internal pure returns (uint256) {
        require(b != 0, errorMessage);
        return a % b;
    }
}

contract Owned {
    address public owner;
    address public newOwner;

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

contract RPTRBridgeHost is Owned {
	using SafeMath for uint256;
	
	CrossChainDataFeed public datafeed; // data feed for call processing
	address public bridgedToken;	// bridged instance on destination chain
	uint256 public bridgedChainId;
	uint256 public wrapGasLimit;
	
	mapping(bytes32 => bool) public processed;
	
	event BridgedTokenChanged(address indexed newToken);
	
	constructor(uint256 _chainid, address _bridgedtoken, uint256 _wrapGas) {
		bridgedChainId = _chainid;
		bridgedToken = _bridgedtoken;
		wrapGasLimit = _wrapGas;
        datafeed = CrossChainDataFeed(address(0xfeed));
	}
	
	function setBridgedToken(address _token) public onlyOwner {
		 bridgedToken = _token;
		 emit BridgedTokenChanged(_token);
	}
	
	function setWrapGas(uint256 _gas) public onlyOwner {
		wrapGasLimit = _gas;
	}
	
	function getUnwrapData(bytes32 slotKey) public view returns (address to, uint256 coins) {
		bytes memory data = datafeed.getSlotData(bridgedChainId, bridgedToken, slotKey);
		(to, coins) = abi.decode(data, (address, uint256));
	}
	
	
	// wrapping backend
    function encodeWrapMessage(address to, uint256 coins) public pure returns (bytes memory data) {
        return abi.encode(to, coins);
    }

	function _postWrapMessage(address to, uint256 coins) private {
		bytes memory data = encodeWrapMessage(to, coins);
		datafeed.crossChainCall(bridgedChainId, bridgedToken, wrapGasLimit, data);
	}
	
	// wraps msg.value to "to"
	function wrap() public payable {
		_postWrapMessage(msg.sender, msg.value);
	}
	
	function wrap(address to) public payable {
		_postWrapMessage(to, msg.value);
	}
	
	// unwrap backend
	function _unwrap(bytes32 slotKey) private {
		require(!processed[slotKey]);
		processed[slotKey] = true;
		(address to, uint256 coins) = getUnwrapData(slotKey);
		payable(to).transfer(coins);
	}
	
	function unwrap(bytes32 slotKey) public {
		_unwrap(slotKey);
	}
	
	function unwrapmultiple(bytes32[] memory slots) public {
		for (uint256 i = 0; i < slots.length; i++) {
			bytes32 _slot = slots[i];
			if (!processed[_slot]) {
				_unwrap(_slot);
			}
		}
	}

	receive() external payable {
		_postWrapMessage(msg.sender, msg.value);
	}
}