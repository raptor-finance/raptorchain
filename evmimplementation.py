from web3.auto import w3
import itertools, rlp, hashlib, eth_abi
from Crypto.Hash import RIPEMD160

class CallMemory(object):
    def __init__(self):
        self.data = bytearray(b"")
    
    def ceil32(self, number):
        return ((((number-1)//32)+1)*32)
    
    def tobytes32(self, number):
        # _hex_ = hex(number)[2:]
        # _bts = bytes.fromhex(_hex_+("0"*(64-len(_hex_))))
        # return _bts
        return int(number).to_bytes(32, "big")
        # return (b"\x00"*(32-(len(_bts))) + _bts)
        
    
    def extend(self, start_position: int, size: int) -> None:
        if size == 0:
            return

        new_size = self.ceil32(start_position + size)
        if new_size <= len(self.data):
            return

        size_to_extend = new_size - len(self.data)
        try:
            self.data.extend(itertools.repeat(0, size_to_extend))
        except BufferError:
            self.data = self.data + bytearray(size_to_extend)
    
    def write(self, begin, end, value):
        _data = self.tobytes32(int(value))
        _len_ = len(self.data)
        self.extend(begin, end-begin)
        self.data[begin:end] = _data
    
    def write_bytes(self, offset, length, value):
        self.extend(offset, length)
        self.data[offset:offset+length] = value
    
    def read(self, offset, size) -> int:
        _data = bytes(self.data[offset:offset+size])
        if len(_data) == 0:
            return 0
        return int.from_bytes(_data, byteorder="big")

    def read_bytes(self, start_position: int, size: int) -> bytes:
        return bytes(self.data[start_position:start_position + size])

    # def extend(self, length: int):
        # self.data += [0]*length


class Msg(object):
    def __init__(self, sender, recipient, value):
        self.sender = sender
        self.recipient = recipient
        self.value = 0


# CallEnv(tx.sender, self.accounts.get(),)

   
# class Opcode(object):
    # def __init__(self, logic, gascost):
        # self.logic = logic
        # self.gascost = gascost
    
    # def __call__(stack, env):
        # self.logic(env)

class Opcodes(object):
    def __init__(self):
        self.opcodes = {}
        self.opcodes[0x00] = self.STOP
        self.opcodes[0x01] = self.add
        self.opcodes[0x02] = self.mul
        self.opcodes[0x03] = self.sub
        self.opcodes[0x04] = self.div
        self.opcodes[0x05] = self.sdiv
        self.opcodes[0x06] = self.mod
        self.opcodes[0x07] = self.smod
        self.opcodes[0x08] = self.addmod
        self.opcodes[0x09] = self.mulmod
        self.opcodes[0x0a] = self.exp
        self.opcodes[0x0b] = self.signextend
        self.opcodes[0x0c] = None
        self.opcodes[0x0d] = None
        self.opcodes[0x0e] = None
        self.opcodes[0x0f] = None
        self.opcodes[0x10] = self.lt
        self.opcodes[0x11] = self.gt
        self.opcodes[0x12] = self.slt
        self.opcodes[0x13] = self.sgt
        self.opcodes[0x14] = self.eq
        self.opcodes[0x15] = self.iszero
        self.opcodes[0x16] = self.and_op
        self.opcodes[0x17] = self.or_op
        self.opcodes[0x18] = self.xor
        self.opcodes[0x19] = self.not_op
        self.opcodes[0x1a] = self.byte_op
        self.opcodes[0x1b] = self.shl
        self.opcodes[0x1c] = self.shr
        self.opcodes[0x1d] = self.sar
        self.opcodes[0x1e] = None
        self.opcodes[0x1f] = None
        self.opcodes[0x20] = self.sha3
        self.opcodes[0x21] = None
        self.opcodes[0x22] = None
        self.opcodes[0x23] = None
        self.opcodes[0x23] = None
        self.opcodes[0x24] = None
        self.opcodes[0x25] = None
        self.opcodes[0x26] = None
        self.opcodes[0x27] = None
        self.opcodes[0x28] = None
        self.opcodes[0x29] = None
        self.opcodes[0x2a] = None
        self.opcodes[0x2b] = None
        self.opcodes[0x2c] = None
        self.opcodes[0x2d] = None
        self.opcodes[0x2e] = None
        self.opcodes[0x2f] = None
        self.opcodes[0x30] = self.ADDRESS
        self.opcodes[0x31] = self.BALANCE
        self.opcodes[0x32] = self.ORIGIN
        self.opcodes[0x33] = self.CALLER
        self.opcodes[0x34] = self.CALLVALUE
        self.opcodes[0x35] = self.CALLDATALOAD
        self.opcodes[0x36] = self.CALLDATASIZE
        self.opcodes[0x37] = self.CALLDATACOPY
        self.opcodes[0x38] = self.CODESIZE
        self.opcodes[0x39] = self.CODECOPY
        self.opcodes[0x3A] = self.GASPRICE
        self.opcodes[0x3B] = self.EXTCODESIZE
        self.opcodes[0x3C] = self.EXTCODECOPY
        self.opcodes[0x3D] = self.RETURNDATASIZE
        self.opcodes[0x3E] = self.RETURNDATACOPY
        self.opcodes[0x3F] = self.EXTCODEHASH
        self.opcodes[0x40] = self.BLOCKHASH
        self.opcodes[0x41] = self.COINBASE
        self.opcodes[0x42] = self.TIMESTAMP
        self.opcodes[0x43] = self.NUMBER
        self.opcodes[0x44] = self.DIFFICULTY
        self.opcodes[0x45] = self.GASLIMIT
        self.opcodes[0x46] = self.CHAINID
        self.opcodes[0x47] = self.SELFBALANCE
        self.opcodes[0x48] = self.BASEFEE
        self.opcodes[0x49] = None
        self.opcodes[0x4A] = None
        self.opcodes[0x4B] = None
        self.opcodes[0x4C] = None
        self.opcodes[0x4D] = None
        self.opcodes[0x4E] = None
        self.opcodes[0x4F] = None
        self.opcodes[0x50] = self.POP
        self.opcodes[0x51] = self.MLOAD
        self.opcodes[0x52] = self.MSTORE
        self.opcodes[0x53] = self.MSTORE8
        self.opcodes[0x54] = self.SLOAD
        self.opcodes[0x55] = self.SSTORE
        self.opcodes[0x56] = self.JUMP
        self.opcodes[0x57] = self.JUMPI
        self.opcodes[0x58] = self.PC
        self.opcodes[0x59] = self.MSIZE
        self.opcodes[0x5A] = self.GAS
        self.opcodes[0x5B] = self.JUMPDEST
        self.opcodes[0x5C] = None
        self.opcodes[0x5D] = None
        self.opcodes[0x5E] = None
        self.opcodes[0x5F] = None
        self.opcodes[0x60] = self.PUSH1
        self.opcodes[0x61] = self.PUSH2
        self.opcodes[0x62] = self.PUSH3
        self.opcodes[0x63] = self.PUSH4
        self.opcodes[0x64] = self.PUSH5
        self.opcodes[0x65] = self.PUSH6
        self.opcodes[0x66] = self.PUSH7
        self.opcodes[0x67] = self.PUSH8
        self.opcodes[0x68] = self.PUSH9
        self.opcodes[0x69] = self.PUSH10
        self.opcodes[0x6A] = self.PUSH11
        self.opcodes[0x6B] = self.PUSH12
        self.opcodes[0x6C] = self.PUSH13
        self.opcodes[0x6D] = self.PUSH14
        self.opcodes[0x6E] = self.PUSH15
        self.opcodes[0x6F] = self.PUSH16
        self.opcodes[0x70] = self.PUSH17
        self.opcodes[0x71] = self.PUSH18
        self.opcodes[0x72] = self.PUSH19
        self.opcodes[0x73] = self.PUSH20
        self.opcodes[0x74] = self.PUSH21
        self.opcodes[0x75] = self.PUSH22
        self.opcodes[0x76] = self.PUSH23
        self.opcodes[0x77] = self.PUSH24
        self.opcodes[0x78] = self.PUSH25
        self.opcodes[0x79] = self.PUSH26
        self.opcodes[0x7A] = self.PUSH27
        self.opcodes[0x7B] = self.PUSH28
        self.opcodes[0x7C] = self.PUSH29
        self.opcodes[0x7D] = self.PUSH30
        self.opcodes[0x7E] = self.PUSH31
        self.opcodes[0x7F] = self.PUSH32
        self.opcodes[0x80] = self.DUP1
        self.opcodes[0x81] = self.DUP2
        self.opcodes[0x82] = self.DUP3
        self.opcodes[0x83] = self.DUP4
        self.opcodes[0x84] = self.DUP5
        self.opcodes[0x85] = self.DUP6
        self.opcodes[0x86] = self.DUP7
        self.opcodes[0x87] = self.DUP8
        self.opcodes[0x88] = self.DUP9
        self.opcodes[0x89] = self.DUP10
        self.opcodes[0x8A] = self.DUP11
        self.opcodes[0x8B] = self.DUP12
        self.opcodes[0x8C] = self.DUP13
        self.opcodes[0x8D] = self.DUP14
        self.opcodes[0x8E] = self.DUP15
        self.opcodes[0x8F] = self.DUP16
        self.opcodes[0x90] = self.SWAP1
        self.opcodes[0x91] = self.SWAP2
        self.opcodes[0x92] = self.SWAP3
        self.opcodes[0x93] = self.SWAP4
        self.opcodes[0x94] = self.SWAP5
        self.opcodes[0x95] = self.SWAP6
        self.opcodes[0x96] = self.SWAP7
        self.opcodes[0x97] = self.SWAP8
        self.opcodes[0x98] = self.SWAP9
        self.opcodes[0x99] = self.SWAP10
        self.opcodes[0x9A] = self.SWAP11
        self.opcodes[0x9B] = self.SWAP12
        self.opcodes[0x9C] = self.SWAP13
        self.opcodes[0x9D] = self.SWAP14
        self.opcodes[0x9E] = self.SWAP15
        self.opcodes[0x9F] = self.SWAP16
        self.opcodes[0xA0] = self.LOG0
        self.opcodes[0xA1] = self.LOG1
        self.opcodes[0xA2] = self.LOG2
        self.opcodes[0xA3] = self.LOG3
        self.opcodes[0xA4] = self.LOG4
        self.opcodes[0xA5] = None
        self.opcodes[0xA6] = None
        self.opcodes[0xA7] = None
        self.opcodes[0xA8] = None
        self.opcodes[0xA9] = None
        self.opcodes[0xAA] = None
        self.opcodes[0xAB] = None
        self.opcodes[0xAC] = None
        self.opcodes[0xAD] = None
        self.opcodes[0xAE] = None
        self.opcodes[0xAF] = None
        # Skipping rest of NONE stuff, it isn't useful
        self.opcodes[0xF0] = self.CREATE
        self.opcodes[0xF1] = self.CALL
        self.opcodes[0xF2] = self.CALLCODE
        self.opcodes[0xF3] = self.RETURN
        self.opcodes[0xF4] = self.DELEGATECALL
        self.opcodes[0xF5] = self.CREATE2
        self.opcodes[0xFA] = self.STATICCALL
        self.opcodes[0xFD] = self.REVERT

    def padded(self, data, size):
        return (b"\x00"*(size-(len(_bts))) + _bts)[0:size]

    def unsigned_to_signed(self, value):
        return value if value <= (2**255) else value - (2**256)
    
    def STOP(self, env):
        env.halt = True
    
    def add(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        env.stack.append(int(int(a+b)%(2**256)))
        env.consumeGas(3)
        env.pc += 1
    
    def sub(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        env.stack.append(int(int(a-b)%(2**256)))
        env.consumeGas(3)
        env.pc += 1
    
    def mul(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        env.stack.append(int(int(a*b)%(2**256)))
        env.consumeGas(5)
        env.pc += 1

    def div(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        result = 0 if (b==0) else a//b*(-1 if b * b < 0 else 1)
            
        env.stack.append(int(int(result)%(2**256)))
        env.consumeGas(5)
        env.pc += 1
        
    def sdiv(self, env):
        a = self.unsigned_to_signed(env.stack.pop())
        b = self.unsigned_to_signed(env.stack.pop())
        result = 0 if (b==0) else a//b*(-1 if b * b < 0 else 1)
            
        env.stack.append(int(int(result)%(2**256)))
        env.consumeGas(5)
        env.pc += 1

    def mod(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        env.stack.append(int(int(0 if a == 0 else (a%b))%(2**256)))
        env.consumeGas(5)
        env.pc += 1
    
    def smod(self, env):
        a = self.unsigned_to_signed(env.stack.pop())
        b = self.unsigned_to_signed(env.stack.pop())
        result = 0 if mod == 0 else (abs(a) % abs(b) * (-1 if a < 0 else 1)) & (2**256-1)
        env.stack.append(int(int(result)%(2**256)))
        env.consumeGas(5)
        env.pc += 1
        
    def addmod(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        c = env.stack.pop()

        result = 0 if mod == 0 else (a + b) % c

        env.stack.append(int(int(result)%(2**256)))
        env.consumeGas(8)
        env.pc += 1

    def mulmod(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        c = env.stack.pop()

        result = 0 if mod == 0 else (a * b) % c

        env.stack.append(int(int(result)%(2**256)))
        env.consumeGas(8)
        env.pc += 1

    def exp(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        result = pow(a, b, (2**256))
        env.stack.append(int(int(result)%(2**256)))
        env.consumeGas(10*(b+1))
        env.pc += 1

    def signextend(self, env):
        bits = env.stack.pop()
        value = env.stack.pop()
        
        if bits <= 31:
            testbit = bits * 8 + 7
            sign_bit = (1 << testbit)
            if value & sign_bit:
                result = value | ((2**256) - sign_bit)
            else:
                result = value & (sign_bit - 1)
        else:
            result = value
        env.stack.append(int(int(result)%(2**256)))
        env.consumeGas(5)
        env.pc += 1

    def lt(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        result = int(a<b)
        env.stack.append(int(result))
        env.consumeGas(3)
        env.pc += 1
    
    def gt(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        result = int(a>b)
        env.stack.append(int(result))
        env.consumeGas(3)
        env.pc += 1

    def slt(self, env):
        a = self.unsigned_to_signed(env.stack.pop())
        b = self.unsigned_to_signed(env.stack.pop())
        result = int(a<b)
        env.stack.append(result)
        env.consumeGas(3)
        env.pc += 1

    def sgt(self, env):
        a = self.unsigned_to_signed(env.stack.pop())
        b = self.unsigned_to_signed(env.stack.pop())
        result = int(a>b)
        env.stack.append(int(result))
        env.consumeGas(3)
        env.pc += 1

    def eq(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        result = int(a==b)
        env.stack.append(int(result))
        env.consumeGas(3)
        env.pc += 1
    
    def iszero(self, env):
        a = env.stack.pop()
        result = int(a==0)
        env.stack.append(int(result))
        env.consumeGas(3)
        env.pc += 1
    
    def and_op(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        result = a&b
        env.stack.append(int(result))
        env.consumeGas(3)
        env.pc += 1
    
    def or_op(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        result = a|b
        env.stack.append(int(result))
        env.consumeGas(3)
        env.pc += 1
    
    def xor(self, env):
        a = env.stack.pop()
        b = env.stack.pop()
        result = a^b
        env.stack.append(int(result))
        env.consumeGas(3)
        env.pc += 1
    
    def not_op(self, env):
        a = env.stack.pop()
        result = (2**256-1)-a
        env.stack.append(int(result))
        env.consumeGas(3)
        env.pc += 1
    
    def byte_op(self, env):
        position = env.stack.pop()
        value = env.stack.pop()
        result = 0 if position >= 32 else (value // pow(256, 31 - position)) % 256
        env.stack.append(int(result))
        env.consumeGas(3)
        env.pc += 1
    
    def shl(self, env):
        shift = env.stack.pop()
        value = env.stack.pop()
        result = (value << shift)%(2**256)
        env.stack.append(int(result))
        env.pc += 1
    
    def shr(self, env):
        shift = env.stack.pop()
        value = env.stack.pop()
        result = (value >> shift)%(2**256)
        env.stack.append(int(result))
        env.pc += 1


    def sar(self, env):
        shift = env.stack.pop()
        value = self.unsigned_to_signed(env.stack.pop())
        result = (value << shift)%(2**256)
        env.stack.append(int(result))
        if shift >= 256:
            result = 0 if value >= 0 else (2**256-1)
        else:
            result = (value >> shift) & (2**256-1)
        env.pc += 1

    

    def sha3(self, env):
        start_position = env.stack.pop()
        size = env.stack.pop()

        sha3_bytes = env.memory.read_bytes(start_position, size)
        # word_count = ceil32(len(sha3_bytes) - 1) // 32
        word_count = (((len(sha3_bytes) - 1)//32) + 1)

        # gas_cost = constants.GAS_SHA3WORD * word_count
        # computation.consume_gas(gas_cost, reason="SHA3: word gas cost")
        env.consumeGas(30+(6*word_count))
        result = int(w3.keccak(sha3_bytes).hex(), 16)

        env.stack.append(result)
        env.pc += 1

    def ADDRESS(self, env):
        env.stack.append(int(env.runningAccount.address, 16))
        env.consumeGas(2)
        env.pc += 1
    
    def BALANCE(self, env):
        env.stack.append(env.getAccount(env.stack.pop()).tempBalance)
        env.consumeGas(400)
        env.pc += 1
    
    def ORIGIN(self, env):
        env.stack.append(int(env.tx.sender, 16))
        env.consumeGas(2)
        env.pc += 1
    
    def CALLER(self, env):
        env.stack.append(env.msgSender if (type(env.msgSender) == int) else int(env.msgSender, 16))
        env.consumeGas(2)
        env.pc += 1
    
    def CALLVALUE(self, env):
        try:
            _value = int(env.value)
        except:
            _value = int(env.value, 16)
        env.stack.append(_value)
        env.consumeGas(2)
        env.pc += 1
    
    def CALLDATALOAD(self, env):
        i = env.stack.pop()
        _data = env.data[i:i+32]
        if (len(_data) > 0):
            _data = (_data + (b"\x00"*(32-len(_data))))
            env.stack.append(int.from_bytes(_data, byteorder="big"))
        else:
            env.stack.append(0)
        env.consumeGas(3)
        env.pc += 1
    
    def CALLDATASIZE(self, env):
        env.stack.append(len(env.data))
        env.consumeGas(2)
        env.pc += 1

    def CALLDATACOPY(self, env):
        destOffset = env.stack.pop()
        offset = env.stack.pop()
        length = env.stack.pop()
        env.memory.write_bytes(destOffset, length, env.data[offset:offset+length])
        env.consumeGas(((((length - 1)//32) + 1) * 3) + 2)
        env.pc += 1

    def CODESIZE(self, env):
        env.stack.append(len(env.code))
        env.consumeGas(2)
        env.pc += 1

    def CODECOPY(self, env):
        destOffset = env.stack.pop()
        offset = env.stack.pop()
        length = env.stack.pop()
        env.memory.write_bytes(destOffset, length, env.code[offset:offset+length])
        env.consumeGas(((((int(length) - 1)//32) + 1) * 3) + 2)
        env.pc += 1

    def GASPRICE(self, env):
        env.stack.append(env.tx.gasprice)
        env.stack.consumeGas(2)
        env.pc += 1
    
    def EXTCODESIZE(self, env):
        _addr = env.stack.pop()
        env.stack.append(len(env.getCode(_addr)))
        env.consumeGas(700)
        env.pc += 1

    def EXTCODECOPY(self, env):
        addr = env.stack.pop()
        destOffset = env.stack.pop()
        offset = env.stack.pop()
        length = env.stack.pop()
        # env.memory.write_bytes(destOffset, length, env.getAccount(addr).code[offset:offset+length])
        env.memory.write_bytes(destOffset, length, env.getCode(addr)[offset:offset+length])
        env.consumeGas(700+(3*(length//32)))
        env.pc += 1
        
    def RETURNDATASIZE(self, env):
        env.stack.append(len(env.lastCallReturn))
        env.pc += 1
        
    def RETURNDATACOPY(self, env):
        destOffset = env.stack.pop()
        offset = env.stack.pop()
        length = env.stack.pop()
        env.memory.write_bytes(destOffset, length, env.lastCallReturn[offset:offset+length])
        env.consumeGas(((length//32) * 3) + 2)
        env.pc += 1
    
    def EXTCODEHASH(self, env):
        env.stack.append(int(w3.keccak(env.getCode(env.stack.pop())), 16))
        env.consumeGas(700)
        env.pc += 1
    
    def BLOCKHASH(self, env):
        env.stack.append(int(env.getBlock(env.stack.pop()).proof, 16))
        env.consumeGas(200)
        env.pc += 1
    
    def COINBASE(self, env):
        env.stack.append(int(env.lastBlock().miner, 16))
        env.consumeGas(200)
        env.pc += 1
    
    def TIMESTAMP(self, env):
        env.stack.append(int(env.lastBlock().timestamp))
        env.consumeGas(200)
        env.pc += 1
        
    def NUMBER(self, env):
        env.stack.append(int(env.blockNumber()))
        env.consumeGas(20)
        env.pc += 1
        
    def DIFFICULTY(self, env):
        env.stack.append(int(env.lastBlock().difficulty))
        env.consumeGas(200)
        env.pc += 1

    def GASLIMIT(self, env):
        env.stack.append(int(0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff)) # as blocks don't physically contain txns, there isn't real limit
        env.consumeGas(2)
        env.pc += 1
    
    def CHAINID(self, env):
        env.stack.append(int(env.chainid))
        env.consumeGas(2)
        env.pc += 1
    
    def SELFBALANCE(self, env):
        env.stack.append(env.runningAccount.tempBalance)
        env.consumeGas(5)
        env.pc += 1
        
    def BASEFEE(self, env):
        env.stack.append(int(0)) # london hardfork not implemented, adding this in case of use
        env.pc += 1
        
    def POP(self, env):
        try:
            env.stack.pop()
        except:
            pass
        env.consumeGas(2)
        env.pc += 1
    
    def MLOAD(self, env):
        offset = env.stack.pop()
        env.stack.append(int(env.memory.read(offset, 32)))
        env.consumeGas(3)
        env.pc += 1
    
    def MSTORE(self, env):
        offset = env.stack.pop()
        value = env.stack.pop()
        env.memory.write(offset, offset+32, value)
        env.consumeGas(3)
        env.pc += 1
    
    def MSTORE8(self, env):
        offset = env.stack.pop()
        value = env.stack.pop()
        env.memory.extend(offset, 1)
        env.memory.data[offset] = value%0x100
        env.consumeGas(3)
        env.pc += 1
        
    def SLOAD(self, env):
        key = env.stack.pop()
        env.stack.append(env.loadStorageKey(key))
        env.consumeGas(200)
        env.pc += 1
        
    def SSTORE(self, env):
        key = env.stack.pop()
        value = env.stack.pop()
        env.writeStorageKey(key, value)
        env.consumeGas(5000 if (value == 0) else 20000)
        env.pc += 1
    
    def JUMP(self, env):
        env.pc = env.stack.pop()
        env.consumeGas(8)
    
    def JUMPI(self, env):
        dest = env.stack.pop()
        cond = env.stack.pop()
        env.pc = (dest if bool(cond) else (env.pc + 1))
        env.consumeGas(10)
    
    def PC(self, env):
        env.stack.append(env.pc)
        env.consumeGas(2)
        env.pc += 1
    
    def MSIZE(self, env):
        env.stack.append(len(env.memory.data))
        env.consumeGas(2)
        env.pc += 1
    
    def GAS(self, env):
        env.consumeGas(2)
        env.stack.append(env.remainingGas())
        env.pc += 1
    
    def JUMPDEST(self, env):
        env.pc += 1
    
    def PUSH(self, env, nBytes): # single method for all PUSH<n> opcodes (cleaner !)
        env.stack.append(env.getPushData(env.pc, nBytes))
        env.consumeGas(3)
        env.pc += 1
    
    def PUSH1(self, env):
        self.PUSH(env, 1)
    
    def PUSH2(self, env):
        self.PUSH(env, 2)
        
    def PUSH3(self, env):
        self.PUSH(env, 3)
        
    def PUSH4(self, env):
        self.PUSH(env, 4)
        
    def PUSH5(self, env):
        self.PUSH(env, 5)
        
    def PUSH6(self, env):
        self.PUSH(env, 6)
        
    def PUSH7(self, env):
        self.PUSH(env, 7)
        
    def PUSH8(self, env):
        self.PUSH(env, 8)
        
    def PUSH9(self, env):
        self.PUSH(env, 9)
        
    def PUSH10(self, env):
        self.PUSH(env, 10)
        
    def PUSH11(self, env):
        self.PUSH(env, 11)
        
    def PUSH12(self, env):
        self.PUSH(env, 12)
        
    def PUSH13(self, env):
        self.PUSH(env, 13)
        
    def PUSH14(self, env):
        self.PUSH(env, 14)
        
    def PUSH15(self, env):
        self.PUSH(env, 15)
        
    def PUSH16(self, env):
        self.PUSH(env, 16)
        
    def PUSH17(self, env):
        self.PUSH(env, 17)
        
    def PUSH18(self, env):
        self.PUSH(env, 18)
        
    def PUSH19(self, env):
        self.PUSH(env, 19)
        
    def PUSH20(self, env):
        self.PUSH(env, 20)
        
    def PUSH21(self, env):
        self.PUSH(env, 21)
        
    def PUSH22(self, env):
        self.PUSH(env, 22)
        
    def PUSH23(self, env):
        self.PUSH(env, 23)
        
    def PUSH24(self, env):
        self.PUSH(env, 24)
        
    def PUSH25(self, env):
        self.PUSH(env, 25)
        
    def PUSH26(self, env):
        self.PUSH(env, 26)
        
    def PUSH27(self, env):
        self.PUSH(env, 27)
        
    def PUSH28(self, env):
        self.PUSH(env, 28)
        
    def PUSH29(self, env):
        self.PUSH(env, 29)
        
    def PUSH30(self, env):
        self.PUSH(env, 30)
        
    def PUSH31(self, env):
        self.PUSH(env, 31)
        
    def PUSH32(self, env):
        self.PUSH(env, 32)
        
        
        
    def DUP(self, env, nItem): # function to manage them all !
        env.stack.append(env.stack[len(env.stack)-nItem])
        env.consumeGas(3)
        env.pc += 1
        
    def DUP1(self, env):
        self.DUP(env, 1)
        # env.stack.append(env.stack[len(env.stack)-1])
        # env.consumeGas(3)
        # env.pc += 1

    def DUP2(self, env):
        self.DUP(env, 2)

    def DUP3(self, env):
        self.DUP(env, 3)

    def DUP4(self, env):
        self.DUP(env, 4)

    def DUP5(self, env):
        self.DUP(env, 5)

    def DUP6(self, env):
        self.DUP(env, 6)

    def DUP7(self, env):
        self.DUP(env, 7)

    def DUP8(self, env):
        self.DUP(env, 8)

    def DUP9(self, env):
        self.DUP(env, 9)

    def DUP10(self, env):
        self.DUP(env, 10)

    def DUP11(self, env):
        self.DUP(env, 11)

    def DUP12(self, env):
        self.DUP(env, 12)

    def DUP13(self, env):
        self.DUP(env, 13)

    def DUP14(self, env):
        self.DUP(env, 14)

    def DUP15(self, env):
        self.DUP(env, 15)

    def DUP16(self, env):
        self.DUP(env, 16)



    def SWAP1(self, env):
        env.swap(1)
        env.consumeGas(3)
        env.pc += 1

    def SWAP2(self, env):
        env.swap(2)
        env.consumeGas(3)
        env.pc += 1

    def SWAP3(self, env):
        env.swap(3)
        env.consumeGas(3)
        env.pc += 1

    def SWAP4(self, env):
        env.swap(4)
        env.consumeGas(3)
        env.pc += 1

    def SWAP5(self, env):
        env.swap(5)
        env.consumeGas(3)
        env.pc += 1

    def SWAP6(self, env):
        env.swap(6)
        env.consumeGas(3)
        env.pc += 1

    def SWAP7(self, env):
        env.swap(7)
        env.consumeGas(3)
        env.pc += 1

    def SWAP8(self, env):
        env.swap(8)
        env.consumeGas(3)
        env.pc += 1
        
    def SWAP9(self, env):
        env.swap(9)
        env.consumeGas(3)
        env.pc += 1
        
    def SWAP10(self, env):
        env.swap(10)
        env.consumeGas(3)
        env.pc += 1

    def SWAP11(self, env):
        env.swap(11)
        env.consumeGas(3)
        env.pc += 1

    def SWAP12(self, env):
        env.swap(12)
        env.consumeGas(3)
        env.pc += 1

    def SWAP13(self, env):
        env.swap(13)
        env.consumeGas(3)
        env.pc += 1

    def SWAP14(self, env):
        env.swap(14)
        env.consumeGas(3)
        env.pc += 1

    def SWAP15(self, env):
        env.swap(15)
        env.consumeGas(3)
        env.pc += 1

    def SWAP16(self, env):
        env.swap(16)
        env.consumeGas(3)
        env.pc += 1

    def LOG0(self, env): # TODO
        offset = env.stack.pop()
        length = env.stack.pop()
        _data = env.memory.read_bytes(offset, length)
        env.postEvent([], _data)
        env.pc += 1
        
    def LOG1(self, env): # TODO
        offset = env.stack.pop()
        length = env.stack.pop()
        topic0 = env.stack.pop()
        _data = env.memory.read_bytes(offset, length)
        env.postEvent([topic0], _data)
        env.pc += 1
        
    def LOG2(self, env): # TODO
        offset = env.stack.pop()
        length = env.stack.pop()
        topic0 = env.stack.pop()
        topic1 = env.stack.pop()

        _data = env.memory.read_bytes(offset, length)
        env.postEvent([topic0, topic1], _data)
        
        env.pc += 1

    def LOG3(self, env): # TODO
        offset = env.stack.pop()
        length = env.stack.pop()
        topic0 = env.stack.pop()
        topic1 = env.stack.pop()
        topic2 = env.stack.pop()
        
        _data = env.memory.read_bytes(offset, length)
        env.postEvent([topic0, topic1, topic2], _data)
        
        env.pc += 1
        
    def LOG4(self, env): # TODO
        offset = env.stack.pop()
        length = env.stack.pop()
        topic0 = env.stack.pop()
        topic1 = env.stack.pop()
        topic2 = env.stack.pop()
        topic3 = env.stack.pop()
        
        _data = env.memory.read_bytes(offset, length)
        env.postEvent([topic0, topic1, topic3], _data)
        
        env.pc += 1

    def CREATE(self, env):
        if env.isStatic:
            env.revert(b"STATICCALL_DONT_ALLOW_CREATE")
            return
        value = env.stack.pop()
        offset = env.stack.pop()
        length = env.stack.pop()
        _nonce = len(env.runningAccount.sent)
        if env.tx.persist:
            env.runningAccount.sent.append(hex(_nonce)) # increases contract nonce
        deplAddr = w3.toChecksumAddress(w3.keccak(rlp.encode([bytes.fromhex(env.runningAccount.address.replace("0x", "")), int(_nonce)]))[12:])
        _childEnv = CallEnv(env.getAccount, env.recipient, env.getAccount(deplAddr), deplAddr, env.chain, value, 300000, env.tx, b"", env.callFallback, env.memory.read_bytes(offset, length), False, calltype=3)
        result = env.callFallback(_childEnv)
        env.lastCallReturn = _childEnv.returnValue
        env.stack.append(int(deplAddr, 16))
        env.consumeGas(32000)
        env.pc += 1
        
    def CALL(self, env):
        gas = env.stack.pop()
        addr = env.stack.pop()
        value = env.stack.pop()
        argsOffset = env.stack.pop()
        argsLength = env.stack.pop()
        retOffset = env.stack.pop()
        retLength = env.stack.pop()
        
        # child env execution
        _calldata = bytes(env.memory.data[argsOffset:argsOffset+argsLength])
        (success, retValue) = env.performExternalCall(addr, value, gas, _calldata)
        
        # push result to parent env
        env.lastCallReturn = retValue
        env.stack.append(int(success))
        env.memory.write_bytes(retOffset, retLength, retValue)
        
        # recover potential messages IF childEnv succeeded
        # if success:
            # env.messages = env.messages + _childEnv.messages
            # env.systemMessages = env.systemMessages + _childEnv.systemMessages
        
        env.pc += 1

        
        
    def CALLCODE(self, env):
        pass # TODO
        env.pc += 1
        
    def RETURN(self, env):
        # print(f"Stack state just before return : {env.stack}")
        offset = env.stack.pop()
        length = env.stack.pop()
        env.returnCall(bytes(env.memory.data[offset:offset+length]))
        env.pc += 1
        
    def DELEGATECALL(self, env):
        gas = env.stack.pop()
        addr = env.stack.pop()
        argsOffset = env.stack.pop()
        argsLength = env.stack.pop()
        retOffset = env.stack.pop()
        retLength = env.stack.pop()
        _subCallEnv = CallEnv(env.getAccount, env.msgSender, env.getAccount(env.recipient), env.recipient, env.chain, 0, gas, env.tx, bytes(env.memory.data[argsOffset:argsOffset+argsLength]), env.callFallback, env.isStatic, calltype=2)
        env.childEnvs.append(_subCallEnv)
        result = env.callFallback(_subCallEnv)
        retValue = _subCallEnv.returnValue
        env.lastCallReturn = retValue
        if result[0]:
            env.storage = _subCallEnv.storage
            env.messages = env.messages + _childEnv.messages
            env.systemMessages = env.systemMessages + _childEnv.systemMessages
        env.stack.append(int(result[0]))
        env.memory.write_bytes(retOffset, retLength, retValue)
        env.consumeGas(_childEnv.gasUsed + 5000)
        env.pc += 1
        
    def CREATE2(self, env):
        if env.isStatic:
            env.revert(b"STATICCALL_DONT_ALLOW_CREATE")
            return
        value = env.stack.pop()
        offset = env.stack.pop()
        length = env.stack.pop()
        salt = env.stack.pop()
        
        _initBytecode = env.memory.read_bytes(offset, length)
        
        _nonce = len(env.runningAccount.sent)
        if env.tx.persist:
            env.runningAccount.sent.append(hex(_nonce)) # increases contract nonce (TODO : update that shit)
            
        # calculate deployment address
        deplAddr = w3.toChecksumAddress(w3.keccak(((b'\xff' + bytes.fromhex(env.runningAccount.address.replace("0x", "")) + int(salt).to_bytes(32, "big") + w3.keccak(_initBytecode))))[12:])
        print(f"CREATE2 called to deploy address {deplAddr}")
        
        # exec creation
        env.createBackend(deplAddr, value, _initBytecode)

        # push deplAddr
        env.stack.append(int(deplAddr, 16))
        env.consumeGas(32000)
        env.pc += 1
    
    def STATICCALL(self, env):
        gas = env.stack.pop()
        addr = env.stack.pop()
        argsOffset = env.stack.pop()
        argsLength = env.stack.pop()
        retOffset = env.stack.pop()
        retLength = env.stack.pop()
        
        # fetch calldata from memory
        _calldata = bytes(env.memory.data[argsOffset:argsOffset+argsLength])
        
        # perform external call
        (success, retValue) = env.performStaticCall(addr, gas, _calldata)
        
        env.lastCallReturn = retValue
        env.stack.append(int(success))
        env.memory.write_bytes(retOffset, retLength, retValue)
        
        env.pc += 1

    def REVERT(self, env):
        offset = env.stack.pop()
        length = env.stack.pop()
        _errorMsg = bytes(env.memory.data[offset:offset+length])
        env.revert(_errorMsg)
        print(f"REVERTED in tx {env.tx.txid} for reason {_errorMsg}")
        env.pc += 1

    def SELFDESTRUCT(self, env):
        if env.isStatic():
            env.revert(b"NOT_SUPPORTED_IN_STATICCALL")
            return
        else:
            addr = env.stack.pop()
            env.tx.accountsToDestroy.append([env.recipient, addr])
            env.halt = True
        env.pc += 1
        
class PrecompiledContracts(object):
    class Precompile(object):
        methods = {}    # moves declaration to inherited class
        # no init because it forces child classes to call it (additional burden)
    
        def returnSingleType(self, env, _type, _arg):
            env.returnCall(eth_abi.encode_abi([_type], [_arg]))
        
        def returnMultipleTypes(self, env, types, args):
            env.returnCall(eth_abi.encode_abi(types, args))

        def calcFunctionSelector(self, functionName):
            return bytes(w3.keccak(str(functionName).encode()))[0:4]
        
        def printCalledFunction(self, functionName, args):
            print(f"{functionName}({', '.join(str(i) for i in args)})")
            
        def addMethod(self, _name, _implementation):
            self.methods[self.calcFunctionSelector(_name)] = _implementation    # calculates selector and binds implementation

        def decodeParams(self, env, _types):
            return eth_abi.decode_abi(_types, env.data[4:]) # wrapper around decode_abi, improves readability

        def formatAddress(self, _addr):
            if (type(_addr) == int):
                return w3.toChecksumAddress(_addr.to_bytes(20, "big"))
            return w3.toChecksumAddress(_addr)

        def fallback(self, env):
            env.revert(b"") # default fallback, can be overriden in child class
            
        def call(self, env):
            try:
                self.methods.get(env.data[:4], self.fallback)(env)
            except Exception as e:
                print(f"Exception {e.__repr__()} caught calling CrossChainDataFeed with calldata {env.data.hex()}")
                env.revert(b"")

    class SimplePrecompile(Precompile):
        # this allows using python's standard return format, with encoding set within the call handler
    
        def call(self, env):
            try:
                retData = self.methods.get(env.data[:4], self.fallback)(env)
                if retData:
                    (retTypes, retValues) = retData
                    self.returnMultipleTypes(env, retTypes, retValues)
            except Exception as e:
                print(f"Exception {e.__repr__()} caught calling CrossChainDataFeed with calldata {env.data.hex()}")
                env.revert(b"")

    class ecRecover(object):
        def call(self, env):
            sig = env.data[63:] # as v is one-byte, 32:63 is empty (only zeroes) due to EVM's 32-bytes word size
            try:
                recovered = w3.eth.account.recoverHash(env.data[0:32], vrs=(sig[0], sig[1:33], sig[33:65]))
            except:
                recovered = "0x0000000000000000000000000000000000000000"
            env.returnCall(int(recovered, 16).to_bytes(32, "big"))
    
    class crossChainBridge(object):
        def __init__(self, bridgeFallBack, addr, bsc):
            self.address = addr
            self.fallback = bridgeFallBack
            self.bsc = bsc
        
        def call(self, env):
            # if env.calltype: # shouldn't be in child call
                # env.revert(b"DONT_WORK_IN_CHILD_CALL")
                # return
            env.messages.append(self.fallback(self.bsc.custodyContract.address, self.bsc.token, env.msgSender, env.value, len(env.runningAccount.transactions)))
    
    class accountBioManager(Precompile):
        def __init__(self):
            # note to myself : use normal declaration next time
            self.methods[b'y\xe6"\x86'] = self.setAccountBio
            self.methods[b'^;\x04!'] = self.getAccountBio
            
        def fallback(self, env):
            env.revert(b"")
    
        def setAccountBio(self, env):
            env.consumeGas(2300)
            try:
                params = eth_abi.decode_abi(["string"], env.data[4:])
                _bio = params[0]
                env.getAccount(env.msgSender).bio = _bio
            except:
                env.revert(b"ERROR_PARSING_PARAMS")
            else:
                env.returnCall(b"")
        
        def getAccountBio(self, env):
            env.consumeGas(2300)
            try:
                params = eth_abi.decode_abi(["address"], env.data[4:])
                addr = params[0]
                bio = env.getAccount(addr).bio
                env.returnCall(eth_abi.encode_abi(["string"], [bio]))
            except:
                env.revert(b"ERROR_PARSING_PARAMS")
                
            
        def call(self, env):
            env.consumeGas(2300)
            self.methods.get(env.data[:4], self.fallback)(env)
            
    class CrossChainToken(Precompile):
        def __init__(self, bsc, token, _bridge):
            self.bsc = bsc
            self.BEP20Instance = bsc.getBEP20At(w3.toChecksumAddress(token))
            self.bridge = _bridge
            self._name = self.BEP20Instance.name
            self._symbol = self.BEP20Instance.symbol
            self._decimals = self.BEP20Instance.decimals
            # avoids possible address collisions (bridging a remote token to an existing local address)
            self.address = w3.toChecksumAddress((int(self.BEP20Instance.address, 16) +  int(self.bsc.chainID)).to_bytes(20, "big"))

            self.supply = 0
            
            self.supplySlot = 0
            self.balancesSlot = 1
            self.allowancesSlot = 2
            
            self.addMethod("totalSupply()", self.totalSupply)
            self.addMethod("decimals()", self.decimals)
            self.addMethod("name()", self.name)
            self.addMethod("symbol()", self.symbol)
            self.addMethod("balanceOf(address)", self.balanceOf)
            self.addMethod("transfer(address,uint256)", self.transfer)
            self.addMethod("approve(address,uint256)", self.approve)
            self.addMethod("transferFrom(address,address,uint256)", self.transferFrom)
            print(f"Token name : {self._name}\nToken Symbol : {self._symbol}\nToken decimals : {self._decimals}")
        
        
        def safeIncrease(self, env, slot, value, errorMessage=b"INTEGER_OVERFLOW_DETECTED"):
            _prevValue = int(env.loadStorageKey(slot))
            _prevValue += value
            if (_prevValue >= 2**256):
                env.revert(errorMessage)
                return False
            env.writeStorageKey(slot, _prevValue)
            return True
        
        def safeDecrease(self, env, slot, value, errorMessage=b"INTEGER_UNDERFLOW_DETECTED"):
            _prevValue = env.loadStorageKey(slot)
            if _prevValue < value:
                env.revert(errorMessage)
                return False
            env.writeStorageKey(slot, _prevValue - value)
            return True
            
        
        def calcBalanceAddress(self, tokenOwner):
            return int.from_bytes(w3.solidityKeccak(["uint256", "address"], [int(self.balancesSlot), w3.toChecksumAddress(tokenOwner)]), "big")
            
        def calcAllowanceAddress(self, tokenOwner, spender):
            return int.from_bytes(w3.solidityKeccak(["uint256", "address", "address"], [int(self.allowancesSlot), w3.toChecksumAddress(tokenOwner), w3.toChecksumAddress(spender)]), "big")
        
        def totalSupply(self, env):
            env.consumeGas(2300)
            self.returnSingleType(env, "uint256", env.loadStorageKey(self.supplySlot))
        
        
        def decimals(self, env):
            env.consumeGas(2300)
            self.returnSingleType(env, "uint8", self._decimals)
        
        def name(self, env):
            env.consumeGas(2300)
            self.returnSingleType(env, "string", self._name)
    
        def symbol(self, env):
            env.consumeGas(2300)
            self.returnSingleType(env, "string", self._symbol)
        
        
        def _crossChain(self, env, tokens):
            _decrSuccess = env.safeDecrease(self.supplySlot, tokens)
            if not _decrSuccess:
                return False
            env.messages.append(self.bridge.fallback(self.bsc.custodyContract.address, self.BEP20Instance.address, env.msgSender, tokens, len(env.runningAccount.transactions)))
            return True
        
        def _transfer(self, env, sender, recipient, tokens):
            _from = self.calcBalanceAddress(sender)
            _to = self.calcBalanceAddress(recipient)
            _decrSuccess = env.safeDecrease(_from, int(tokens), b"INSUFFICIENT_BALANCE")
            if not _decrSuccess:
                return False
            return (self._crossChain(env, tokens) if (recipient == self.bridge.address) else env.safeIncrease(_to, int(tokens)))
                
        def approve(self, env):
            params = self.decodeParams(env, ["address", "uint256"])
            self.printCalledFunction("approve", params)
            allowanceAddress = self.calcAllowanceAddress(env.msgSender, params[0])
            env.consumeGas(16900)
            self.returnSingleType(env, "bool", True)
        
        def transfer(self, env):
            params = self.decodeParams(env, ["address", "uint256"])
            self.printCalledFunction("transfer", params)
            _success = self._transfer(env, env.msgSender, params[0], params[1])
            env.consumeGas(69000)
            if not _success:
                return
            self.returnSingleType(env, "bool", True)

        def transferFrom(self, env):
            params = self.decodeParams(env, ["address", "address", "uint256"])
            env.consumeGas(69000)
            self.printCalledFunction("transferFrom", params)
            allowanceAddress = self.calcAllowanceAddress(params[0], env.msgSender)
            apprSuccess = env.safeDecrease(allowanceAddress, params[2], b"INSUFFICIENT_ALLOWANCE")
            if not apprSuccess:
                return
            transfSuccess = self._transfer(env, params[0], params[1], params[2])
            if not transfSuccess:
                return
            self.returnSingleType(env, "bool", True)
            
        def balanceOf(self, env):
            params = self.decodeParams(env, ["address"])
            # self.printCalledFunction("balanceOf", params)
            env.consumeGas(6900)
            self.returnSingleType(env, "uint256", env.loadStorageKey(self.calcBalanceAddress(params[0])))
       
       
        def mint(self, env, to, tokens):
            print(f"Cross-chain depositing {tokens} to {to}")
            depositorAddr = self.calcBalanceAddress(w3.toChecksumAddress(to))
            env.safeIncrease(depositorAddr, tokens)
            env.safeIncrease(self.supplySlot, tokens)
            # env.writeStorageKey(depositorAddr, (env.loadStorageKey(depositorAddr) + tokens))
            # env.writeStorageKey(env.supplySlot, (env.loadStorageKey(self.supplySlot) + tokens))
            # print(f"Minted {tokens/(10**(self._decimals))} {self._symbol} to {w3.toChecksumAddress(to)}")
        
        def burn(self, env, user, tokens):
            depositorAddr = self.calcBalanceAddress(w3.toChecksumAddress(user))
            env.writeStorageKey(depositorAddr, (env.loadStorageKey(depositorAddr) - tokens))
            env.writeStorageKey(env.supplySlot, (env.loadStorageKey(self.supplySlot) - tokens))
            print(f"Burned {tokens/(10**(self._decimals))} {self._symbol} to {w3.toChecksumAddress(to)}")
        
        def fallback(self, env):
            env.revert(b"")
        
        def call(self, env):
            try:
                self.methods.get(env.data[:4], self.fallback)(env)
            except Exception as e:
                print(f"Exception {e.__repr__()} caught calling {self.address} with calldata {env.data}")
    
    class Printer(object):
        def call(self, env):
            env.consumeGas(69)
            print(f"Hi {env.msgSender}")
    
    class Sha256(object):
        def call(self, env):
            env.returnCall(hashlib.sha256(env.data).digest())
    
    class Ripemd160(object):
        def call(self, env):
            hasher = RIPEMD160.new()
            hasher.update(env.data) # TODO : make sure data comes raw
            env.returnCall(hasher.digest())
    
    class RelayerSigsHandler(Precompile):
        def __init__(self):
            self.addMethod("addSig(bytes32,bytes)", self.addSig)
        
        def addSig(self, env):
            params = self.decodeParams(env, ["bytes32", "bytes"])
#            env.pushSystemMessage(env.SystemMessage(env.msgSender, env.recipient, 0, params))
        
        def fallback(self, env):
            pass
            
        def call(self, env):
            try:
                self.methods.get(env.data[:4], self.fallback)(env)
            except Exception as e:
                print(f"Exception {e.__repr__()} caught calling {self.address} with calldata {env.data}")
                env.revert(b"")
    
    class CrossChainDataFeed(Precompile):
        def __init__(self):
            self.methods = {}
            self.addMethod("getSlotData(uint256,address,bytes32)", self.getSlotData)
            self.addMethod("crossChainCall(uint256,address,uint256,bytes)", self.crossChainCall)
            self.addMethod("isChainSupported(uint256)", self.isChainSupported)
            self.addMethod("isMN(address)", self.isMN)
            self.addMethod("mnOwner(address)", self.mnOwner)
            self.nullAddress = "0x0000000000000000000000000000000000000000"
            
        def _isChainSupported(self, env, chainid):
            cnt = env.chain.datafeed.contracts.get(chainid)
            return bool(cnt) # True if chain is supported, False otherwise
            
        def encodePayload(self, _from, _to, gasLimit, callData):
            return eth_abi.encode_abi(["address", "address", "uint256", "bytes"], [_from, _to, gasLimit, callData]) # decoder on solidity side : (address from, address to, uint256 gasLimit, bytes memory data) = abi.decode(_data, (address, address, uint256, bytes));
            
        def packPayload(self, env, payload, chainid):
            handlerContract = env.chain.datafeed.contracts.get(chainid)
            if (handlerContract == None):
                return False
            return [handlerContract.address, payload, chainid] # will be ABI-encoded on postMessage
            
        def fallback(self, env):
            env.revert(b"")
            
        def isChainSupported(self, env):
            params = self.decodeParams(env, ["uint256"]) # uint256 chainid
            _chainid = params[0]
            supported = self._isChainSupported(env, _chainid)
            self.returnSingleType(env, "bool", supported)
            env.consumeGas(3400)
            
        def getSlotData(self, env):
            params = self.decodeParams(env, ["uint256", "address", "bytes32"]) # uint256 chainid, address dataOwner, bytes32 slotKey
            d = env.chain.datafeed.getSlotData(params[0], params[1], params[2])
            self.returnSingleType(env, "bytes", d)
            env.consumeGas(6900)
        
        def crossChainCall(self, env):
            params = self.decodeParams(env, ["uint256", "address", "uint256", "bytes"]) # uint256 chainid, address to, uint256 gasLimit, uint256 data
            _chainid = params[0]
            _to = params[1]
            _gas = params[2]
            _data = params[3]
            
            _pricePerGas = env.chain.datafeed.gasPricings.get(_chainid, 3)  # loads proper gas pricing
            env.consumeGas(100)
            if (not self._isChainSupported(env, _chainid)):
                env.revert(b"") # reverts if unsupported chain
                return # halts execution
            
            payload = self.encodePayload(env.msgSender, _to, _gas, _data)
            packedPL = self.packPayload(env, payload, _chainid)
#            print(packedPL)
            env.messages.append(packedPL)
            env.consumeGas(6900 + (_gas * _pricePerGas))
        
        def isMN(self, env):
            params = self.decodeParams(env, ["address"])
            _addr = self.formatAddress(params[0])           # formats operator address
            _val = env.chain.validators.get(_addr, False)   # attempts to load validator at address
            _exists = bool(_val)                            # true if object exists, false if it don't
            self.returnSingleType(env, "bool", _exists)     # ABI encoding and returning
            
        def mnOwner(self, env):
            params = self.decodeParams(env, ["address"])
            _addr = self.formatAddress(params[0])   # formats operator address
            _val = env.chain.validators.get(_addr)  # attempts to get validator address
            # returns owner if validator exists, otherwise return address 0
            print(f"Validator existence check : {bool(_val)}")
            self.returnSingleType(env, "address", _val.owner if bool(_val) else self.nullAddress)
        
        def call(self, env):
            try:
                self.methods.get(env.data[:4], self.fallback)(env)
            except Exception as e:
                print(f"Exception {e.__repr__()} caught calling CrossChainDataFeed with calldata {env.data.hex()}")
                env.revert(b"")
    
    def __init__(self, bridgeFallBack, bsc, getAccount):
        self.contracts = {}
        self.bsc = bsc
        self.getAccount = getAccount
        self.crossChainAddress = "0x0000000000000000000000000000000000000097"
        self.setContract("0x0000000000000000000000000000000000000001", self.ecRecover(), True)
        self.setContract("0x0000000000000000000000000000000000000002", self.Sha256(), False)
        self.setContract("0x0000000000000000000000000000000000000003", self.Ripemd160(), False)
        self.setContract("0x0000000000000000000000000000000000000069", self.accountBioManager(), False)
        self.setContract("0x000000000000000000000000000000000000FEeD", self.CrossChainDataFeed(), False)
        self.setContract(self.crossChainAddress, self.crossChainBridge(bridgeFallBack, self.crossChainAddress, bsc), False)
        # self.setContract("0x0000000000000000000000000000000d0ed622a3", self.Printer())
    
    def setContract(self, address, contract, initialize=False):
        self.contracts[address] = contract
        _acct = self.getAccount(address)
        _acct.setPrecompiledContract(contract, initialize)
        
    def calcBridgedAddress(self, addr):
        return w3.toChecksumAddress((int(addr, 16) +  int(self.bsc.chainID)).to_bytes(20, "big"))

    def mintCrossChainToken(self, env, tokenAddress, to, tokens):
        if not self.contracts.get(tokenAddress):
            _token = self.CrossChainToken(self.bsc, tokenAddress, self.contracts.get(self.crossChainAddress))
            self.setContract(_token.address, _token)
            print(f"Deployed cross-chain token {tokenAddress} to address {_token.address}")
        self.contracts[self.calcBridgedAddress(tokenAddress)].mint(env, to, tokens)



class Msg(object):
    def __init__(self, sender, recipient, value, gas, tx, data=b"", calltype=0, shallSaveData=False):
        self.sender = sender
        self.recipient = recipient
        self.value = int(value)
        self.gas = int(gas)
        self.tx = tx
        self.data = data
        self.calltype = calltype
        self.persistStorage = shallSaveData
        
# CALL : CallEnv(self.getAccount, env.recipient, env.getAccount(addr), addr, env.chain, value, gas, env.tx, bytes(env.memory.data[argsOffset:argsOffset+argsLength]), env.callFallback)
class CallEnv(object):
    class SystemMessage(object):
        def __init__(self, sender, contract, instruction, data):
            self.sender = sender
            self.contract = contract
            self.instruction = instruction
            self.data = data

    class Event(object):
        # TODO : move this function to a common class
        def formatAddress(self, _addr):
            if (type(_addr) == int):
                return w3.toChecksumAddress(_addr.to_bytes(20, "big"))
            return w3.toChecksumAddress(_addr)
    
        def __init__(self, env, topics, _data):
            self.address = env.recipient
            
            self.topics = topics
            self.data = _data
            self.index = 0
            
            self.txid = env.tx.txid
            self.bkhash = env.lastBlock().proof
            self.bknbr = env.blockNumber()
            
        def setIndex(self, _index):
            self.index = _index
            
        def JSONEncodable(self):
            _topics = [("0x" + t.to_bytes(32, "big").hex()) for t in self.topics]
            _data = "0x" + self.data.hex()
            return {"address": self.formatAddress(self.address), "topics": _topics, "data": _data, "blockNumber": self.bknbr, "transactionIndex": "0x1", "blockHash": self.bkhash, "transactionHash": self.txid, "logIndex": self.index, "removed": False}
            

    def __init__(self, accountGetter, caller, runningAccount, recipient, beaconchain, value, gaslimit, tx, data, callfallback, code, static,*, storage=None, calltype=0, calledFromAcctClass=False):
        self.stack = []
        self.getAccount = accountGetter
        self.memory = CallMemory()
        self.msgSender = caller
        self.debugfile = None # set by other parts of code, better to have one here
        self.txorigin = tx.sender
        self.recipient = recipient
        self.chain = beaconchain
        self.runningAccount = runningAccount
        self.calltype=calltype # 0 = in transaction, 1 = child call (staticcall included), 2 = delegate call, 3 = contract creation in subcall
        self.lastCallReturn = b""
        self.systemMessages = []
        if storage:
            self.storage = storage
            self.storageBefore = self.storage.copy()
        else:
            self.storage = runningAccount.tempStorage
            self.storageBefore = runningAccount.tempStorage.copy()
        self.value = value
        self.testnet = False
        self.chainid = 499597202514 if self.testnet else 1380996178
        try:
            self.gaslimit = int(gaslimit)
        except:
            self.gaslimit = int(gaslimit, 16)
        self.gasUsed = 21000 if (calltype == 0) else 0
        self.gaslimit = (self.gaslimit + 2300) if (calltype == 1) else self.gaslimit
        self.pc = 0
        self.tx = tx
        self.events = []
        self.data = data
        self.code = (b"" if calledFromAcctClass else code)
        self.halt = False
        self.returnValue = b""
        self.success = True
        self.callFallback = callfallback
        self.isStatic = static
        self.tx.markAccountAffected(caller)
        self.tx.markAccountAffected(recipient)
        self.tx.markAccountAffected(runningAccount.address)
        self.contractDeployment = ((self.tx.contractDeployment) or calltype == 3)
        self.messages = []
        self.childEnvs = []
        
        self.balanceFromBefore = self.getAccount(self.msgSender).tempBalance
        self.balanceToBefore = self.runningAccount.tempBalance

    def getBlock(self, height):
        return self.chain.blocks[min(height, len(self.chain.blocks)-1)]
        
    def lastBlock(self):
        return self.chain.blocks[len(self.chain.blocks)-1]

    def blockNumber(self):
        return (len(self.chain.blocks)-1)
    
    def refreshDebugFile(self):
        if self.debugfile:
            self.debugfile.close()
        self.debugfile = open(f"raptorevmdebug-{self.tx.txid}.log", "a")
    
    def consumeGas(self, units):
        self.gasUsed += units
        if (self.gasUsed > self.gaslimit):
            self.halt = True
            self.success = False
    
    def remainingGas(self):
        return self.gaslimit - self.gasUsed
    
    def loadStorageKey(self, key):
        return self.storage.get(key, 0)
    
    def writeStorageKey(self, key, value):
        if self.isStatic:
            self.success = False
            self.halt = True
            self.returnValue = b"STATICCALL_DONT_ALLOW_SSTORE"
        else:
            self.storage[key] = value
            if value == 0:
                del self.storage[key]
    
    def safeIncrease(self, slot, value, errorMessage=b"INTEGER_OVERFLOW_DETECTED"):
        _prevValue = self.loadStorageKey(slot)
        _prevValue += value
        if (_prevValue >= 2**256):
            self.revert(errorMessage)
            return False
        self.writeStorageKey(slot, _prevValue)
        return True
    
    def safeDecrease(self, slot, value, errorMessage=b"INTEGER_UNDERFLOW_DETECTED"):
        _prevValue = self.loadStorageKey(slot)
        if _prevValue < value:
            self.revert(errorMessage)
            return False
        self.writeStorageKey(slot, _prevValue - value)
        return True
            
    
    def getPushData(self, pc, length):
        _data = self.code[pc+1:pc+length+1]
        self.pc += length
        return int.from_bytes(_data, "big")
        # return int(_data.hex(), 16)
    
    def getCode(self, addr):
        _acct = self.getAccount(addr)
        return _acct.tempcode
    
    def swap(self, n):
        head = len(self.stack)-1
        toswap = head-n
        (self.stack[head], self.stack[toswap]) = (self.stack[toswap], self.stack[head])
    
    def returnCall(self, data):
        self.halt = True
        self.returnValue = data
        self.runningAccount.tempStorage = self.storage
        if self.debugfile:
            self.debugfile.write(f"Call ended, returnValue: {data.hex()}\n\n\n")
    
    def revert(self, data):
        self.storage = self.storageBefore.copy()
        self.runningAccount.tempStorage = self.storage
        
        self.getAccount(self.msgSender).tempBalance = self.balanceFromBefore
        self.runningAccount.tempBalance = self.balanceToBefore
        
        self.halt = True
        self.success = False
        self.returnValue = data
        for _e in reversed(self.childEnvs):
            _e.revert(b"")
        # self.returnValue = eth_abi.encode_abi(["bytes"], [data]) if type(data) == bytes else eth_abi.encode_abi(["string"], [data])
    
    def pushSystemMessage(self, sysmsg):
        self.systemMessages.append(sysmsg)
    
    
    def createBackend(self, deplAddr, value, _initBytecode):
        _childEnv = CallEnv(self.getAccount, self.recipient, self.getAccount(deplAddr), deplAddr, self.chain, value, 300000, self.tx, b"", self.callFallback, _initBytecode, False, calltype=3)
        self.childEnvs.append(_childEnv)
        return self.callFallback(_childEnv)
    
    
    # external calls
    def performExternalCall(self, addr, value, gas, _calldata):
        _acct = self.getAccount(addr)
        _childEnv = CallEnv(self.getAccount, self.recipient, _acct, addr, self.chain, value, gas, self.tx, _calldata, self.callFallback, self.getCode(addr), self.isStatic, calltype=1)
        self.childEnvs.append(_childEnv)
        result = self.callFallback(_childEnv)
        if result[0]:   # success bool
            self.messages = self.messages + _childEnv.messages
            self.events = self.events + _childEnv.events
            self.systemMessages = self.systemMessages + _childEnv.systemMessages
        self.consumeGas(_childEnv.gasUsed + 5000) # forward gas costs
        return result # success and returnValue
    
    def performStaticCall(self, addr, gas, _calldata):
        _acct = self.getAccount(addr)
        _childEnv = CallEnv(self.getAccount, self.recipient, _acct, addr, self.chain, 0, gas, self.tx, _calldata, self.callFallback, self.getCode(addr), True, calltype=1)
        self.childEnvs.append(_childEnv)
        result = self.callFallback(_childEnv)
        self.consumeGas(_childEnv.gasUsed + 5000) # forward gas costs
        # STATICCALL don't allow cross-chain messages, nothing to push
        return result # success and returnValue


    def postEvent(self, topics, _data):
        self.events.append(self.Event(self, topics, _data))

    def getSuccess(self):
        return (self.success and (self.remainingGas() >= 0))