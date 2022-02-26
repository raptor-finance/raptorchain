pragma solidity ^0.7.0;
pragma abicoder v2;

interface ERC20Interface {
    function totalSupply() external view returns (uint);
    function balanceOf(address tokenOwner) external view returns (uint balance);
    function allowance(address tokenOwner, address spender) external view returns (uint remaining);
    function transfer(address to, uint tokens) external returns (bool success);
    function approve(address spender, uint tokens) external returns (bool success);
    function transferFrom(address from, address to, uint tokens) external returns (bool success);
}

interface BridgeFallbackInterface {
	function bridgeFallBack(bytes32 _hash, bytes memory _data) external;
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

library Math {
	function sum(uint256[] memory numbers) internal pure returns (uint256 _sum) {
		uint256 i = 0;
		while (i < numbers.length) {
			_sum += numbers[i];
			i += 1;
		}
	}
	
	function min(uint256[] memory numbers) internal pure returns (uint256 _min) {
		uint256 i = 0;
		_min = numbers[0];
		while (i < numbers.length) {
			if (_min > numbers[i]) {
				_min = numbers[i];
			}
			i += 1;
		}
	}
	
	function max(uint256[] memory numbers) internal pure returns (uint256 _max) {
		uint256 i = 0;
		_max = numbers[0];
		while (i < numbers.length) {
			if (_max < numbers[i]) {
				_max = numbers[i];
			}
			i += 1;
		}
	}
}

contract CustodyManager {
	using SafeMath for uint256;
	struct Deposit {
		uint256 amount; // deposit value
		address depositor; // address that deposits tokens
		uint256 nonce;
		address token; // or address 0 if you deposit BNB
		bytes32 hash; // keccak256(abi.encodePacked(amount, depositor, token, blockhash(), nonce))
	}
	
	struct Withdrawal {
		uint256 amount; // withdrawal value
		address withdrawer; // address that tokens
		uint256 nonce;
		address token; // withdrawn token
		bytes32 hash;
		bool claimed;
	}
	
	
	address masterContract;
	Deposit[] public __deposits;
	mapping (bytes32 => Deposit) public _deposits;
	
	Withdrawal[] public __withdrawals;
	mapping (bytes32 => Withdrawal) public _withdrawals;
	
	
	uint256 public transferNonce = 0;
	uint256 public totalDeposited;
	StakeManager public stakingManager;
	
	constructor(StakeManager _stakingManager) {
		masterContract = msg.sender;
		stakingManager = _stakingManager;
	}
	
	event Deposited(address indexed depositor, address indexed token, uint256 amount, uint256 nonce, bytes32 hash);
	
	function deposits(uint256 _index) public view returns (Deposit memory) {
		return __deposits[_index];
	}
	
	function deposits(bytes32 _hash) public view returns (Deposit memory) {
		return _deposits[_hash];
	}

	function withdrawals(uint256 _index) public view returns (Withdrawal memory) {
		return __withdrawals[_index];
	}
	
	function withdrawals(bytes32 _hash) public view returns (Withdrawal memory) {
		return _withdrawals[_hash];
	}


	
	function deposit(address token, uint256 amount) public {
		ERC20Interface _token = ERC20Interface(token);
		uint256 balanceBefore = _token.balanceOf(address(this));
		_token.transferFrom(msg.sender, address(this), amount);
		uint256 received = _token.balanceOf(address(this)).sub(balanceBefore);
		bytes32 _hash_ = keccak256(abi.encodePacked(received,msg.sender, blockhash(block.number-1), transferNonce));
		Deposit memory _newDeposit = Deposit({amount: received, depositor: msg.sender, nonce: transferNonce, token: token, hash: _hash_});
		__deposits.push(_newDeposit);
		_deposits[_hash_] = _newDeposit;
		emit Deposited(msg.sender, token, received, transferNonce, _hash_);
		transferNonce += 1;
	}
	
	function requestWithdrawal(address token, address withdrawer, uint256 amount, uint256 nonce, bytes32 l2Hash) private {
		// bytes32 _hash = keccak256(abi.encodePacked(amount, withdrawer, token, nonce));
		// require(l2Hash == _hash, "HASH_UNMATCHED");
		require(stakingManager.confirmationsMatched(l2Hash), "CONFIRMATIONS_UNMATCHED");
		require(!_withdrawals[l2Hash].claimed, "ALREADY_CLAIMED");
		Withdrawal memory _newWithdrawal = Withdrawal({amount: amount, withdrawer: withdrawer, nonce: nonce, token: token, hash: l2Hash, claimed: true});
		_withdrawals[l2Hash] = _newWithdrawal;
		__withdrawals.push(_newWithdrawal);
	}
	
	function bridgeFallBack(bytes memory _data) public {
		require(msg.sender == address(stakingManager), "Only PoS bridge can use this :/");
		bytes32 _hash = keccak256(_data);
		(address token, address withdrawer, uint256 amount, uint256 nonce) = abi.decode(_data, (address, address, uint256, uint256));
		requestWithdrawal(token, withdrawer, amount, nonce, _hash);
	}
	
	function depositsLength() public view returns (uint256) {
		return __deposits.length;
	}
}

contract BeaconChainHandler {
	struct Beacon {
		address miner;
		uint256 nonce;
		bytes[] messages;
		uint256 difficulty;
		bytes32 miningTarget;
		uint256 timestamp;
		bytes32 parent;
		bytes32 proof;
		uint256 height;
		bytes32 son;
	}
	
	StakeManager public stakingContract;
	Beacon[] public beacons;
	uint256 blockTime = 600;
	
	modifier onlyStakingContract {
		require(msg.sender == address(stakingContract));
		_;
	}
	
	function _chainId() internal pure returns (uint256) {
		uint256 id;
		assembly {
			id := chainid()
		}
		return id;
	}
	
	constructor(Beacon memory _genesisBeacon, StakeManager _stakingContract) {
		stakingContract = _stakingContract;
		beacons.push(_genesisBeacon);
		beacons[0].height = 0;
	}
	
	function beaconHash(Beacon memory _beacon) public pure returns (bytes32 beaconRoot) {
		bytes32 messagesRoot = keccak256(abi.encodePacked(_beacon.messages));
		bytes32 bRoot = keccak256(abi.encodePacked(_beacon.parent, _beacon.timestamp,  messagesRoot, _beacon.miner));
		beaconRoot = keccak256(abi.encodePacked(bRoot, _beacon.nonce));
	}
	
	function isBeaconValid(Beacon memory _beacon) public pure returns (bool valid, string memory reason) {
		bytes32 _hash = beaconHash(_beacon);
		if (_hash != _beacon.hash) {
			return (false, "UNMATCHED_HASH");
		}
		bytes32 lastBlockHash = beacons[beacons.length-1].hash;
		if (lastBlockHash != _beacon.parent) {
			return (false, "UNMATCHED_PARENT");
		}
		if (_beacon.height != blocks.length) {
			return (false, "UNMATCHED_HEIGHT");
		}
		if ((_beacon.timestamp > block.timestamp) || (_beacon.timestamp < (beacons[beacons.length-1] + blockTime))) {
			return (false, "UNMATCHED_TIMESTAMP");
		}
		return (true, "VALID_BEACON")
	}
	
	function pushBeacon(Beacon memory _beacon) public onlyStakingContract {
		beacons.push(_beacon);
		uint256 n = 0;
		uint256 chainID;
		address recipient;
		bytes memory data;
		beacons[beacons.length-1].son = _beacon.hash;
		
		while (n < _beacon.messages.length) {
			(recipient, chainID, data) = abi.decode(_beacon.messages[n]);
			if (chainID == _chainId) {
				BridgeFallbackInterface(recipient).bridgeFallBack(data);
			}
			n += 1;
		}
	}
}

contract StakeManager {
	using SafeMath for uint256;
	ERC20Interface public stakingToken;
	BeaconChainHandler public beaconChain;
	
	address masterContract;
	uint256 totalStaked;
	uint256 MNCollateral;
	
	struct Staker {
		uint256 staked;
		uint256 signed;
		mapping (bytes32 => uint256) voted;
		uint256 unlockDate;
		bytes32[] votedList;
	}
	// mapping (address => Staker) stakers;
	
	struct MasterNode {
		address owner;
		address operator;
		uint256 collateral;
		uint256 rewards;
		bytes32[] signedBlocks;
		mapping(bytes32 => uint256) voted;
		bool operating;
	}
	mapping (address => MasterNode) public masternodes;
	
	struct PendingBlock {
		BeaconChainHandler.Beacon beacon;
		uint256 confirmations;
		bool finalized;
		bytes32 hash;
	}
	PendingBlock currentPendingBlock;
	
	constructor(address _stakingToken) {
		stakingToken = ERC20Interface(_stakingToken);
		masterContract = msg.sender;
	}
	
	function setBeaconHandler(BeaconChainHandler _handler) {
		require(beaconChain == address(0), "BEACONHANDLER_ALREADY_SET");
		beaconChain = _handler;
	}
	
	
	
	function _submitL2Block(BeaconChainHandler.Beacon _beacon) internal {
		l2Blocks[_beacon.hash] = PendingBlock({beacon: _beacon, confirmations: 0, hash: _beacon.hash, finalized: false});
	}
	
	
	function _confirmL2Block(bytes32 _hash) internal {
		require(!(masternodes[msg.sender].voted[_hash]),"ALREADY_VOTED");
		l2Blocks[_hash].confirmations = l2Blocks[_hash].confirmations.add(1);
		if (confirmationsMatched(_hash)) {
			l2Blocks[_hash].finalized = true;
		}
	}
	
	function sendL2Block(BeaconChainHandler.Beacon _block) public {
		require(masternodes[msg.sender].operating, "INVALID_MASTERNODE");
		(bool _valid, string memory _reason) = beaconChain.isBeaconValid(currentPendingBlock.beacon);
		require(_valid, _reason);
		
		
		if (l2Blocks[_hash].hash != _hash) {
			_submitL2Block(_beacon);
		}
		_confirmL2Hash(_hash);
		if (l2Hashes[_hash].finalized) {
			beaconChain.pushBeacon(_block);
		}
	}
	
	function confirmationsMatched(bytes32 _hash) public view returns (bool) {
		return (l2Hashes[_hash].confirmations > (totalStaked/2));
	}
	
	function createMN(address nodeOperator) public {
		require(masternodes[nodeOperator].owner == address(0), "NODE_ALDREADY_EXISTS");
		stakingToken.transferFrom(msg.sender, address(this), MNCollateral);
		masternodes[nodeOperator] = MasterNode({owner: msg.sender, operator: nodeOperator, collateral: MNCollateral, rewards: 0, signedBlocks: (new bytes32[]), voted: mapping (bytes32 => bool),operating: true});
		totalStaked += 1;
	}
	
	function disableMN(address nodeOperator) public {
		MasterNode storage MN = masternodes[nodeOperator];
		require(MN.owner == msg.sender, "UNMATCHED_MN_OWNER");
		require(MN.operating, "NODE_ALREADY_STOPPED");
		claimMNRewards(nodeOperator);
		masternodes[nodeOperator].operating = false;
		require(stakingToken.transfer(msg.sender, MNCollateral));
		totalStaked -= 1;
	}
	
	function enableMN(address nodeOperator) public {
		MasterNode storage MN = masternodes[nodeOperator];
		require(MN.owner == msg.sender, "UNMATCHED_MN_OWNER");
		require(!MN.operating, "NODE_ALREADY_RUNNING");
		require(stakingToken.transferFrom(msg.sender, address(this), MNCollateral));
		masternodes[nodeOperator].operating = true;
		totalStaked += 1;
	}
	
	function destroyMN(address nodeOperator) public {
		MasterNode storage MN = masternodes[nodeOperator];
		require(MN.owner == msg.sender, "UNMATCHED_MN_OWNER");
		if (MN.operating) {
			disableMN(nodeOperator);
		}
		MN = MasterNode();
	}
	
	function claimMNRewards(address nodeOperator) public {
		MasterNode storage MN = masternodes[nodeOperator];
		require(MN.owner == msg.sender, "UNMATCHED_MN_OWNER");
		uint256 _rewards = MN.rewards;
		MN.rewards = 0;
		stakingToken.transfer(msg.sender, _rewards);
	}
}

contract MasterContract {
	StakeManager public staking;
	CustodyManager public custody;
	
	constructor(address stakingToken) {
		staking = new StakeManager(stakingToken);
		custody = new CustodyManager(staking);
	}
	
}