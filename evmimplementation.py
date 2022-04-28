from web3.auto import w3
import itertools, rlp


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
        env.stack.append(env.getAccount(env.stack.pop()).balance)
        env.consumeGas(400)
        env.pc += 1
    
    def ORIGIN(self, env):
        env.stack.append(int(env.tx.sender, 16))
        env.consumeGas(2)
        env.pc += 1
    
    def CALLER(self, env):
        env.stack.append(int(env.msgSender, 16))
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
        env.stack.append(len(env.getAccount(env.stack.pop()).code))
        env.consumeGas(700)
        env.pc += 1

    def EXTCODECOPY(self, env):
        addr = env.stack.pop()
        destOffset = env.stack.pop()
        offset = env.stack.pop()
        length = env.stack.pop()
        env.memory.write_bytes(destOffset, length, env.getAccount(addr).code[offset:offset+length])
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
        env.stack.append(int(w3.keccak(env.getAccount(env.stack.pop()).code), 16))
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
        env.stack.append(env.runningAccount.balance)
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
    
    def PUSH1(self, env):
        env.stack.append(env.getPushData(env.pc, 1))
        env.consumeGas(3)
        env.pc += 1
    
    def PUSH2(self, env):
        env.stack.append(env.getPushData(env.pc, 2))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH3(self, env):
        env.stack.append(env.getPushData(env.pc, 3))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH4(self, env):
        env.stack.append(env.getPushData(env.pc, 4))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH5(self, env):
        env.stack.append(env.getPushData(env.pc, 5))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH6(self, env):
        env.stack.append(env.getPushData(env.pc, 6))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH7(self, env):
        env.stack.append(env.getPushData(env.pc, 7))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH8(self, env):
        env.stack.append(env.getPushData(env.pc, 8))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH9(self, env):
        env.stack.append(env.getPushData(env.pc, 9))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH10(self, env):
        env.stack.append(env.getPushData(env.pc, 10))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH11(self, env):
        env.stack.append(env.getPushData(env.pc, 11))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH12(self, env):
        env.stack.append(env.getPushData(env.pc, 12))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH13(self, env):
        env.stack.append(env.getPushData(env.pc, 13))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH14(self, env):
        env.stack.append(env.getPushData(env.pc, 14))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH15(self, env):
        env.stack.append(env.getPushData(env.pc, 15))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH16(self, env):
        env.stack.append(env.getPushData(env.pc, 16))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH17(self, env):
        env.stack.append(env.getPushData(env.pc, 17))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH18(self, env):
        env.stack.append(env.getPushData(env.pc, 18))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH19(self, env):
        env.stack.append(env.getPushData(env.pc, 19))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH20(self, env):
        env.stack.append(env.getPushData(env.pc, 20))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH21(self, env):
        env.stack.append(env.getPushData(env.pc, 21))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH22(self, env):
        env.stack.append(env.getPushData(env.pc, 22))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH23(self, env):
        env.stack.append(env.getPushData(env.pc, 23))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH24(self, env):
        env.stack.append(env.getPushData(env.pc, 24))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH25(self, env):
        env.stack.append(env.getPushData(env.pc, 25))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH26(self, env):
        env.stack.append(env.getPushData(env.pc, 26))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH27(self, env):
        env.stack.append(env.getPushData(env.pc, 27))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH28(self, env):
        env.stack.append(env.getPushData(env.pc, 28))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH29(self, env):
        env.stack.append(env.getPushData(env.pc, 29))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH30(self, env):
        env.stack.append(env.getPushData(env.pc, 30))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH31(self, env):
        env.stack.append(env.getPushData(env.pc, 31))
        env.consumeGas(3)
        env.pc += 1
        
    def PUSH32(self, env):
        env.stack.append(env.getPushData(env.pc, 32))
        env.consumeGas(3)
        env.pc += 1
        
        
        
        
        
    def DUP1(self, env):
        env.stack.append(env.stack[len(env.stack)-1])
        env.consumeGas(3)
        env.pc += 1

    def DUP2(self, env):
        env.stack.append(env.stack[len(env.stack)-2])
        env.consumeGas(3)
        env.pc += 1

    def DUP3(self, env):
        env.stack.append(env.stack[len(env.stack)-3])
        env.consumeGas(3)
        env.pc += 1

    def DUP4(self, env):
        env.stack.append(env.stack[len(env.stack)-4])
        env.consumeGas(3)
        env.pc += 1

    def DUP5(self, env):
        env.stack.append(env.stack[len(env.stack)-5])
        env.consumeGas(3)
        env.pc += 1

    def DUP6(self, env):
        env.stack.append(env.stack[len(env.stack)-6])
        env.consumeGas(3)
        env.pc += 1

    def DUP7(self, env):
        env.stack.append(env.stack[len(env.stack)-7])
        env.consumeGas(3)
        env.pc += 1

    def DUP8(self, env):
        env.stack.append(env.stack[len(env.stack)-8])
        env.consumeGas(3)
        env.pc += 1

    def DUP9(self, env):
        env.stack.append(env.stack[len(env.stack)-9])
        env.consumeGas(3)
        env.pc += 1

    def DUP10(self, env):
        env.stack.append(env.stack[len(env.stack)-10])
        env.consumeGas(3)
        env.pc += 1

    def DUP11(self, env):
        env.stack.append(env.stack[len(env.stack)-11])
        env.consumeGas(3)
        env.pc += 1

    def DUP12(self, env):
        env.stack.append(env.stack[len(env.stack)-12])
        env.consumeGas(3)
        env.pc += 1

    def DUP13(self, env):
        env.stack.append(env.stack[len(env.stack)-13])
        env.consumeGas(3)
        env.pc += 1

    def DUP14(self, env):
        env.stack.append(env.stack[len(env.stack)-14])
        env.consumeGas(3)
        env.pc += 1

    def DUP15(self, env):
        env.stack.append(env.stack[len(env.stack)-15])
        env.consumeGas(3)
        env.pc += 1

    def DUP16(self, env):
        env.stack.append(env.stack[len(env.stack)-16])
        env.consumeGas(3)
        env.pc += 1



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
        env.pc += 1
        
    def LOG1(self, env): # TODO
        offset = env.stack.pop()
        length = env.stack.pop()
        topic0 = env.stack.pop()
        env.pc += 1
        
    def LOG2(self, env): # TODO
        offset = env.stack.pop()
        length = env.stack.pop()
        topic0 = env.stack.pop()
        topic1 = env.stack.pop()
        env.pc += 1

    def LOG3(self, env): # TOOD
        offset = env.stack.pop()
        length = env.stack.pop()
        topic0 = env.stack.pop()
        topic1 = env.stack.pop()
        topic2 = env.stack.pop()
        env.pc += 1
        
    def LOG4(self, env): # TODO
        offset = env.stack.pop()
        length = env.stack.pop()
        topic0 = env.stack.pop()
        topic1 = env.stack.pop()
        topic2 = env.stack.pop()
        topic3 = env.stack.pop()
        env.pc += 1

    def CREATE(self, env):
        if env.isStatic:
            env.revert(b"STATICCALL_DONT_ALLOW_CREATE")
            return
        value = env.stack.pop()
        offset = env.stack.pop()
        length = env.stack.pop()
        _nonce = len(env.runningAccount.sent)
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
        _childEnv = CallEnv(env.getAccount, env.recipient, env.getAccount(addr), addr, env.chain, value, gas, env.tx, bytes(env.memory.data[argsOffset:argsOffset+argsLength]), env.callFallback, env.getAccount(addr).code, env.isStatic, calltype=1)
        result = env.callFallback(_childEnv)
        retValue = result[1]
        env.lastCallReturn = retValue
        env.stack.append(int(result[0]))
        env.memory.write_bytes(retOffset, retLength, retValue)
        env.consumeGas(_childEnv.gasUsed + 5000)
        env.pc += 1

        
        
    def CALLCODE(self, env):
        pass # TODO
        env.pc += 1
        
    def RETURN(self, env):
        print(f"Stack state just before return : {env.stack}")
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
        result = env.callFallback(_subCallEnv)
        retValue = result[1]
        env.lastCallReturn = retValue
        if result[0]:
            env.storage = _subCallEnv.storage.copy()
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
        _nonce = len(env.runningAccount.sent)
        _initBytecode = env.memory.read_bytes(offset, length)
        env.runningAccount.sent.append(hex(_nonce)) # increases contract nonce
        deplAddr = w3.toChecksumAddress(w3.keccak(rlp.encode([0xFF, bytes.fromhex(env.runningAccount.address.replace("0x", "")), int(salt), _initBytecode]))[12:])
        result = env.callFallback(CallEnv(env.getAccount, env.recipient, env.getAccount(deplAddr), deplAddr, env.chain, value, 300000, env.tx, b"", env.callFallback, _initBytecode, False, calltype=3))
        env.stack.append(int(deplAddr, 16))
        env.consumeGas(32000)
    
    def STATICCALL(self, env):
        gas = env.stack.pop()
        addr = env.stack.pop()
        argsOffset = env.stack.pop()
        argsLength = env.stack.pop()
        retOffset = env.stack.pop()
        retLength = env.stack.pop()
        _childEnv = CallEnv(env.getAccount, env.recipient, env.getAccount(addr), addr, env.chain, 0, gas, env.tx, bytes(env.memory.data[argsOffset:argsOffset+argsLength]), env.callFallback, env.getAccount(addr).code, True, calltype=1)
        result = env.callFallback(_childEnv)
        retValue = result[1]
        env.lastCallReturn = retValue
        env.stack.append(int(result[0]))
        env.memory.write_bytes(retOffset, retLength, retValue)
        env.consumeGas(_childEnv.gasUsed + 5000)
        env.pc += 1

    def REVERT(self, env):
        offset = env.stack.pop()
        length = env.stack.pop()
        env.revert(bytes(env.memory.data[offset:offset+length]))
        env.pc += 1

    def SELFDESTRUCT(self, env):
        if env.isStatic():
            env.revert(b"NOT_SUPPORTED_IN_STATICCALL")
            return
        else:
            addr = env.stack.pop()
            env.getAccount(addr).balance += env.getAccount(env.recipient).balance
            env.getAccount(env.recipient).balance = 0
            env.getAccount(env.recipient).bio = ""
            env.getAccount(env.recipient).code = b""
            env.getAccount(env.recipient).storage = {}
            env.halt = True
        env.pc += 1
        


# CALL : CallEnv(self.getAccount, env.recipient, env.getAccount(addr), addr, env.chain, value, gas, env.tx, bytes(env.memory.data[argsOffset:argsOffset+argsLength]), env.callFallback)
class CallEnv(object):
    def __init__(self, accountGetter, caller, runningAccount, recipient, beaconchain, value, gaslimit, tx, data, callfallback, code, static,*, storage=None, calltype=0):
        self.stack = []
        self.getAccount = accountGetter
        self.memory = CallMemory()
        self.msgSender = caller
        self.txorigin = tx.sender
        self.recipient = recipient
        self.chain = beaconchain
        self.runningAccount = runningAccount
        self.calltype=calltype # 0 = in transaction, 1 = child call (staticcall included), 2 = delegate call, 3 = contract creation in subcall
        self.lastCallReturn = b""
        if storage:
            self.storage = storage.copy()
        else:
            self.storage = runningAccount.tempStorage.copy()
        self.value = value
        self.chainid = 69420
        try:
            self.gaslimit = int(gaslimit)
        except:
            self.gaslimit = int(gaslimit, 16)
        self.gasUsed = 21000 if (calltype == 0) else 0
        self.pc = 0
        self.tx = tx
        self.data = data
        self.code = code
        self.halt = False
        self.returnValue = b""
        self.success = True
        self.callFallback = callfallback
        self.isStatic = static
        self.tx.markAccountAffected(caller)
        self.tx.markAccountAffected(recipient)
        self.tx.markAccountAffected(runningAccount.address)
        self.contractDeployment = ((self.tx.contractDeployment) or calltype == 3)
    

    def getBlock(self, height):
        return self.chain.blocks[min(height, len(self.chain.blocks)-1)]
        
    def lastBlock(self):
        return self.chain.blocks[len(self.chain.blocks)-1]

    def blockNumber(self):
        return (len(self.chain.blocks)-1)
    
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
    
    def getPushData(self, pc, length):
        _data = self.code[pc+1:pc+length+1]
        self.pc += length
        return int.from_bytes(_data, "big")
        # return int(_data.hex(), 16)
    
    def swap(self, n):
        head = len(self.stack)-1
        toswap = head-n
        (self.stack[head], self.stack[toswap]) = (self.stack[toswap], self.stack[head])
    
    def returnCall(self, data):
        self.halt = True
        self.returnValue = data
    
    def revert(self, data):
        self.storage = self.runningAccount.tempStorage.copy()
        self.halt = True
        self.success = False
        self.returnValue = data
    
    def getSuccess(self):
        return (self.success and (self.remainingGas() >= 0))
    