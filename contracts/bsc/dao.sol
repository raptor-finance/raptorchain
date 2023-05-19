// SPDX-License-Identifier: UNLICENSED

pragma solidity 0.7.6;
pragma abicoder v2;

interface ERC20Interface {
    function totalSupply() external view returns (uint);
    function balanceOf(address tokenOwner) external view returns (uint balance);
    function allowance(address tokenOwner, address spender) external view returns (uint remaining);
    function transfer(address to, uint tokens) external returns (bool success);
    function approve(address spender, uint tokens) external returns (bool success);
    function transferFrom(address from, address to, uint tokens) external returns (bool success);
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

contract RaptorDAO {
	using SafeMath for uint256;

	struct Relayer {
		address owner;
		address operator;
		bool active;
		
		uint256 totalShares;	// to handle slashings/rewards/whatever
		uint256 tokens;
		
		mapping(address=>uint256) shares;				// shares per delegator
		mapping (address => bool) everbeendelegated;	// for share value processing
		
		bool exists;
	}
	
	struct Delegator {
		uint256 undelegated;	// user undelegated tokens
		uint256 depositBlock;	// delay before delegating
		address[] delegated;
	}
	
	address public owner;
	address public controlSigner; // veto right, no right to force push data
	
	bool public controlSignerReleased = false;
	ERC20Interface public stakingToken;
	
	mapping(address => Relayer) public relayerInfo;
	mapping(address => Delegator) public delegators;
	address[] public relayersList;
	
	uint256 public activeRelayers;
	mapping (uint256 => mapping (bytes32 => mapping (address => bool))) signerCounted;
	uint256 public systemNonce;
	
	uint256 public totalBondedTokens;
	
	event ControlSignerReleased();
	
	
	modifier onlyRelayerOwner(address operator) {
		require(relayerInfo[operator].owner == msg.sender, "Only relayer owner can do that");
		_;
	}
	
	modifier onlyOwner() {
		require(msg.sender == owner);
		_;
	}
	
	function _chainId() public pure returns (uint256) {
		uint256 id;
		assembly {
			id := chainid()
		}
		return id;
	}
	
	function splitSignature(bytes memory sig) public pure returns (bytes32 r, bytes32 s, uint8 v) {
		require(sig.length == 65, "invalid signature length");

		assembly {
			// first 32 bytes, after the length prefix
			r := mload(add(sig, 32))
			// second 32 bytes
			s := mload(add(sig, 64))
			// final byte (first byte of the next 32 bytes)
			v := byte(0, mload(add(sig, 96)))
		}

		// implicitly return (r, s, v)
	}

	function _addRelayer(address _owner, address operator, bool active) private {
		require(!relayerInfo[operator].exists, "RELAYER_ALREADY_EXISTS");
		Relayer storage rel = relayerInfo[operator];
		rel.exists = true;
		rel.owner = _owner;
		rel.operator = operator;
		rel.active = active;
		
		
		relayersList.push(operator);
		activeRelayers += 1;
	}
	
	constructor(address _stakingToken, address bootstrapRelayer) {
		owner = msg.sender;
		stakingToken = ERC20Interface(_stakingToken);
		_addRelayer(address(0), bootstrapRelayer, true);
		controlSigner = bootstrapRelayer;
	}
	
	
	// share-related functions
	function sharesToTokens(uint256 shares, uint256 totalTokens, uint256 totalShares) public pure returns (uint256) {
		if (totalShares == 0) {
			return shares;	// take rate of 1 if relayer is empty
		}
		return shares.mul(totalTokens).div(totalShares);
	}
	
	function tokensToShares(uint256 tokens, uint256 totalTokens, uint256 totalShares) public pure returns (uint256) {
		if (totalTokens == 0) {
			return tokens;	// use rate of 1 if empty
		}
		return tokens.mul(totalShares).div(totalTokens);
	}
	
	// delegator-related functions
	function sharesValue(address _delegator, address _relayer) public view returns (uint256) {
		Relayer storage rel = relayerInfo[_relayer];
		return sharesToTokens(rel.shares[_delegator], rel.tokens, rel.totalShares);
	}
	
	function sharesTotalValue(address _delegator) public view returns (uint256 value) {
		Delegator storage delg = delegators[_delegator];
		for (uint256 n = 0; n<delg.delegated.length; n++) {
			value = value.add(sharesValue(_delegator, delg.delegated[n]));
		}
	}
	
	function deposit(uint256 tokens) public {
		Delegator storage delg = delegators[msg.sender];
		stakingToken.transferFrom(msg.sender, address(this), tokens);
		delg.undelegated = delg.undelegated.add(tokens);
		delg.depositBlock = block.number;
	}
	
	function withdraw(uint256 tokens) public {
		Delegator storage delg = delegators[msg.sender];
		require(block.number > delg.depositBlock, "UNMATCHED_COOLDOWN");
		delg.undelegated = delg.undelegated.sub(tokens, "INSUFFICIENT_UNDELEGATED");
		stakingToken.transfer(msg.sender, tokens);
	}
	
	function delegate(address relayer, uint256 tokens) public {
		Delegator storage delg = delegators[msg.sender];
		Relayer storage rel = relayerInfo[relayer];
		require(block.number > delg.depositBlock, "UNMATCHED_COOLDOWN");
		require(rel.exists, "UNEXISTENT_RELAYER");
		delg.undelegated = delg.undelegated.sub(tokens, "INSUFFICIENT_UNDELEGATED");
		
		uint256 shares = tokensToShares(tokens, rel.tokens, rel.totalShares);
		rel.tokens = rel.tokens.add(tokens);
		rel.totalShares = rel.totalShares.add(shares);
		rel.shares[msg.sender] = rel.shares[msg.sender].add(shares);
		
		if (!rel.everbeendelegated[msg.sender]) {
			rel.everbeendelegated[msg.sender] = true;
			delg.delegated.push(relayer);
		}
		
		if (rel.active) {
			totalBondedTokens = totalBondedTokens.add(tokens);
		}
	}
	
	function undelegate(address relayer, uint256 tokens) public {
		Delegator storage delg = delegators[msg.sender];
		Relayer storage rel = relayerInfo[relayer];
		require(block.number > delg.depositBlock, "UNMATCHED_COOLDOWN");
		require(rel.exists, "UNEXISTENT_RELAYER");
		
		uint256 shares = tokensToShares(tokens, rel.tokens, rel.totalShares);
		rel.shares[msg.sender] = rel.shares[msg.sender].sub(shares, "INSUFFICIENT_SHARES");
		rel.totalShares = rel.totalShares.sub(shares);
		rel.tokens = rel.tokens.sub(tokens);
		
		delg.undelegated = delg.undelegated.add(tokens);
		
		if (rel.active) {
			totalBondedTokens = totalBondedTokens.sub(tokens);
		}
	}
	
	
	
	
	function balanceOf(address delegator) public view returns (uint256) {
		uint256 undelegated = delegators[delegator].undelegated;
		uint256 delegated = sharesTotalValue(delegator);
		return delegated.add(undelegated);
	}
	
	// relayer-related functions
	function nakamotoCoefficient() public view returns (uint256) {
		return (totalBondedTokens/2)+1;	// division can't overflow. as it returns a number below 2**255, addition can't overflow either
	}
	
	function registerRelayer(address relayer) public {
		_addRelayer(msg.sender, relayer, false);
	}

	function enableRelayer(address relayer) public onlyRelayerOwner(relayer) {
		Relayer storage rel = relayerInfo[relayer];
		require(!rel.active, "ALREADY_ACTIVE");	// no need to check existence since unexistent relayers are owned by address 0
		rel.active = true;
		totalBondedTokens = totalBondedTokens.add(rel.tokens);
	}
	
	function disableRelayer(address relayer) public onlyRelayerOwner(relayer) {
		Relayer storage rel = relayerInfo[relayer];
		require(rel.active, "ALREADY_INACTIVE");
		rel.active = false;
		totalBondedTokens = totalBondedTokens.sub(rel.tokens);
	}
	
	
	
	function bondedTokens(address addr) public view returns (uint256) {
		if (!relayerInfo[addr].active) {
			return 0;
		}
		return relayerInfo[addr].tokens;
	}
	
	// sig related stuff
	
	function recoverSig(bytes32 hash, bytes memory _sig) public pure returns (address signer) {
		(bytes32 r, bytes32 s, uint8 v) = splitSignature(_sig);
		return ecrecover(hash, v, r, s);
	}
	
	function recoverRelayerSigs(bytes32 hash, bytes[] memory _sigs) public view returns (uint256 signedTokens, bool coeffmatched) {
		bool controlSigMatch;
		bool _controlReleased = controlSignerReleased;
		address _controlSigner = controlSigner;
		
		uint256 naka = nakamotoCoefficient();
		
		address prevAddress = address(0);
		
		
		for (uint256 n = 0; n<_sigs.length; n++) {
			address addr = recoverSig(hash, _sigs[n]);
			if (addr > prevAddress) {
				controlSigMatch = (controlSigMatch || _controlReleased || (_controlSigner == addr));
				signedTokens += bondedTokens(addr);
				prevAddress = addr;
				coeffmatched = ((signedTokens >= naka) && controlSigMatch);
			}
			if (coeffmatched) { break; } // we don't need to keep checking once we're sure it works
		}
	}
	
	function recoverDelegatorSigs(bytes32 hash, uint256 threshold, bytes[] memory _sigs) public view returns (uint256 signedTokens, bool thresholdMatched) {
		address prevAddress = address(0);
		address addr;

		for (uint256 n = 0; n<_sigs.length; n++) {
            addr = recoverSig(hash, _sigs[n]);
			if (addr > prevAddress) {
				signedTokens += sharesTotalValue(addr);	// counts share value
				thresholdMatched = (threshold == 0) ? false : (signedTokens > threshold);	// don't break if there's no threshold
				if (thresholdMatched) { break; }		// gas
			}
		}
	}
	
	function renounceControlSigner() public {
		require(msg.sender == controlSigner, "UNMATCHED_CONTROL_SIGNER");
		require(!controlSignerReleased, "ALREADY_RELEASED");
		controlSignerReleased = true;
		emit ControlSignerReleased();
	}
	
	// slashing
	function _slash(address _relayer, uint256 tokens) private {
		Relayer storage rel = relayerInfo[_relayer];
		// disable relayer if it was enabled
		if (rel.active) {
			rel.active = false;
			totalBondedTokens = totalBondedTokens.sub(rel.tokens);
		}
		// take relayer tokens (reflects in share value)
		rel.tokens = rel.tokens.sub(tokens);
		// burn tokens
		stakingToken.transfer(tokens, address(0xdead));
	}
	
	// DAO functions
	function totalDeposited() public view returns (uint256) {
		return stakingToken.balanceOf(address(this));
	}
	
	function daoThreshold() public view returns (uint256) {
		return totalDeposited().div(2).add(1);	// make sure to be OVER threshold, division rounds down
	}
}

contract DAOAccount {
	// This account allows executing DAO calls in a reduced permission setup
	// Thus, it can't expose staked assets

	RaptorDAO public dao;
	
	event DAOCallExecuted(address indexed to, bool indexed success, bytes data, bytes returnData);
	
	struct DAOCall {
		address to;
		bytes data;
	}

	constructor(address _dao) {
		dao = RaptorDAO(_dao);
	}
	
	function execCall(DAOCall memory _call, bytes[] memory _sigs) public {
		bytes32 hash = keccak256(abi.encodePacked("execCall", _chainId(), abi.encode(_call)));
		(, bool matched) = dao.recoverDelegatorSigs(hash, dao.daoThreshold(), _sigs);
        require(matched, "UNMATCHED_DAO_SIGS");
        address to = _call.to;
        bytes memory data = _call.data;
        (bool success, bytes memory retData) = to.call(data);
        emit DAOCallExecuted(to, success, data, retData);
	}
}