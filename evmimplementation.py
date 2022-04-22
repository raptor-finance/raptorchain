from web3.auto import w3

class EVM(object):
    def __init__(self):
        self.storage = {}
    
    
    class AccountStorage(object):
        def __init__(self):
            self.data = {}
            
        def set(key: int, value: int):
            self.data[int(key)] = int(value)
        
        def get(key: int):
            return int(self.data[int(key)])

    class CallMemory(object):
        def __init__(self):
            self.data = bytearray(b"")
        
        def ceil32(self, number):
            return ((((number-1)//32)+1)*32)
        
        def tobytes32(self, number):
            _bts = bytes.fromhex(number.hex()[2:])
            return (b"\x00"*(32-(len(_bts))) + _bts)
            
        
        def extend(self, start_position: int, size: int) -> None:
            if size == 0:
                return

            new_size = self.ceil32(start_position + size)
            if new_size <= len(self):
                return

            size_to_extend = new_size - len(self)
            try:
                self.data.extend(itertools.repeat(0, size_to_extend))
            except BufferError:
                self.data = self.data + bytearray(size_to_extend)
        
        def write(self, begin, end, value):
            self.data[begin:end] = tobytes32(int(value))
        
        
        def read(self, start_position: int, size: int) -> memoryview:
            return memoryview(self.data)[start_position:start_position + size]

        def read_bytes(self, start_position: int, size: int) -> bytes:
            return bytes(self.data[start_posision:start_posision + size])

        def extend(self, length: int):
            self.data += [0]*length


    class Msg(object):
        def __init__(self, sender, recipient, value):
            self.sender = sender
            self.recipient = recipient
            self.value = 0


    class CallEnv(object):
        def __init__(self, caller, recipient, state, beaconchain, origin, value, gaslimit):
            self.stack = []
            self.memory = CallMemory()
            self.msgSender = caller
            self.txorigin = origin
            self.recipient = recipient
            self.state = state
            self.chain = beaconchain
            self.storage = self.getAccount(recipient).storage.copy()
            self.value = value
            self.chainid = 69420
            self.gaslimit = gaslimit
            self.gasUsed = 0
            self.pc = 0
        
        def getBlock(height):
            return self.chain.blocks[min(height, len(self.chain.blocks)-1)]
            
        def lastBlock():
            return self.chain.blocks[len(self.chain.blocks)-1]

        def blockNumber():
            return (len(self.chain.blocks)-1)

        def getAccount(addr):
            chkaddr = w3.toChecksumAddress(addr)
            return self.state.get(chkaddr, Account(chkaddr, ""))
        
        def consumeGas(gas):
            self.gasUsed += gas
        
        def remainingGas():
            return self.gaslimit - self.gasUsed
        
        def loadStorageKey(key):
            return self.storage.get(key, 0)
        
        def writeStorageKey(key, value):
            self.storage[key] = value
        
        def getPushData(pc, length):
            self.pc += length
            return int(self.getAccount(self.recipient).code[pc:pc+length].hex(), 16)
        
    # class Opcode(object):
        # def __init__(self, logic, gascost):
            # self.logic = logic
            # self.gascost = gascost
        
        # def __call__(stack, env):
            # self.logic(env)

    class Opcodes(object):
        def __init__(self):
            self.opcodes = {}
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
            self.opcodes[0x1b] = self.shr
            self.opcodes[0x1c] = self.shl
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


        def unsigned_to_signed(value: int) -> int:
            return value if value <= (2**255) else value - (2**256)
        
        def add(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            env.stack.append(int(int(a+b)%(2**256)))
            env.pc += 1
            
        
        def sub(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            env.stack.append(int(int(a-b)%(2**256)))
            env.pc += 1
        
        def mul(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            env.stack.append(int(int(a*b)%(2**256)))
            env.pc += 1

        def div(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = 0 if (b==0) else a//b*(-1 if b * b < 0 else 1)
                
            env.stack.append(int(int(result)%(2**256)))
            env.pc += 1
            
        def sdiv(self, env):
            a = self.unsigned_to_signed(env.stack.pop())
            b = self.unsigned_to_signed(env.stack.pop())
            result = 0 if (b==0) else a//b*(-1 if b * b < 0 else 1)
                
            env.stack.append(int(int(result)%(2**256)))
            env.pc += 1

        def mod(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            env.stack.append(int(int(0 if a == 0 else (a%b))%(2**256)))
            env.pc += 1
        
        def smod(self, env):
            a = self.unsigned_to_signed(env.stack.pop())
            b = self.unsigned_to_signed(env.stack.pop())
            result = 0 if mod == 0 else (abs(a) % abs(b) * (-1 if a < 0 else 1)) & (2**256-1)
            env.stack.append(int(int(result)%(2**256)))
            env.pc += 1
            
        def addmod(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            c = env.stack.pop()

            result = 0 if mod == 0 else (a + b) % c

            env.stack.append(int(int(result)%(2**256)))
            env.pc += 1

        def mulmod(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            c = env.stack.pop()

            result = 0 if mod == 0 else (a * b) % c

            env.stack.append(int(int(result)%(2**256)))
            env.pc += 1

        def exp(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = pow(a, b, (2**256))
            env.stack.append(int(int(result)%(2**256)))
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
            env.pc += 1

        def lt(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = int(a<b)
            env.stack.append(int(result))
            env.pc += 1
        
        def gt(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = int(a>b)
            env.stack.append(int(result))
            env.pc += 1

        def slt(self, env):
            a = self.unsigned_to_signed(env.stack.pop())
            b = self.unsigned_to_signed(env.stack.pop())
            result = int(a<b)
            env.stack.append(result)
            env.pc += 1

        def sgt(self, env):
            a = self.unsigned_to_signed(env.stack.pop())
            b = self.unsigned_to_signed(env.stack.pop())
            result = int(a>b)
            env.stack.append(int(result))
            env.pc += 1

        def eq(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = int(a==b)
            env.stack.append(int(result))
            env.pc += 1
        
        def iszero(self, env):
            a = env.stack.pop()
            result = int(a==0)
            env.stack.append(int(result))
            env.pc += 1
        
        def and_op(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = a&b
            env.stack.append(int(result))
            env.pc += 1
        
        def or_op(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = a|b
            env.stack.append(int(result))
            env.pc += 1
        
        def xor(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = a^b
            env.stack.append(int(result))
            env.pc += 1
        
        def not_op(self, env):
            a = env.stack.pop()
            result = (2**256-1)-a
            env.stack.append(int(result))
            env.pc += 1
        
        def byte_op(self, env):
            position = env.stack.pop()
            value = env.stack.pop()
            result = 0 if position >= 32 else (value // pow(256, 31 - position)) % 256
            env.stack.append(int(result))
            env.pc += 1
        
        def shr(self, env):
            shift = env.stack.pop()
            value = env.stack.pop()
            result = (value >> shift)%(2**256)
            env.stack.append(int(result))
            env.pc += 1

        def shl(self, env):
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

            env.memory.extend(start_position, extend)

            sha3_bytes = env.memory.read_bytes(start_position, size)
            # word_count = ceil32(len(sha3_bytes) - 1) // 32
            word_count = (((len(sha3_bytes) - 1)//32) + 1)

            # gas_cost = constants.GAS_SHA3WORD * word_count
            # computation.consume_gas(gas_cost, reason="SHA3: word gas cost")

            result = int(w3.keccak(sha3_bytes).hex())

            env.stack.append(result)
            env.pc += 1

        def ADDRESS(self, env):
            env.stack.append(env.recipient)
            env.pc += 1
        
        def BALANCE(self, env):
            env.stack.append(env.getAccount(env.stack.pop()).balance)
            env.pc += 1
        
        def ORIGIN(self, env):
            env.stack.append(int(env.tx.sender))
            env.pc += 1
        
        def CALLER(self, env):
            env.stack.append(int(env.msgSender))
            env.pc += 1
        
        def CALLVALUE(self, env):
            env.stack.append(int(env.value))
            env.pc += 1
        
        def CALLDATALOAD(self, env):
            i = env.stack.pop()
            env.stack.append(int((env.data[i:i+32]).hex(), 16))
            env.pc += 1
        
        def CALLDATASIZE(self, env):
            env.stack.append(len(env.data))
            env.pc += 1

        def CALLDATACOPY(self, env):
            destOffset = env.stack.pop()
            offset = env.stack.pop()
            length = env.stack.pop()
            
            env.memory.data[destOffset:destOffset+length] = env.data[offset:offset+length]
            env.pc += 1

        def CODESIZE(self, env):
            env.stack.push(len(env.getAccount(env.recipient).code))
            env.pc += 1

        def CODECOPY(self, env):
            destOffset = env.stack.pop()
            offset = env.stack.pop()
            length = env.stack.pop()
            env.memory.data[destOffset:destOffset+length] = env.getAccount(env.recipient).code[offset:offset+length]
            env.pc += 1

        def GASPRICE(self, env):
            env.stack.append(env.tx.gasprice)
            env.pc += 1
        
        def EXTCODESIZE(self, env):
            env.stack.append(len(env.getAccount(env.stack.pop()).code))
            env.pc += 1

        def EXTCODECOPY(self, env):
            addr = env.stack.pop()
            destOffset = env.stack.pop()
            offset = env.stack.pop()
            length = env.stack.pop()
            env.memory.data[destOffset:destOffset+length] = env.getAccount(addr).code[offset:offset+length]
            env.pc += 1
            
        def RETURNDATASIZE(self, env):
            env.stack.append(0) # TODO
            env.pc += 1
            
        def RETURNDATACOPY(self, env):
            env.stack.append(0) # TODO
            env.pc += 1
        
        def EXTCODEHASH(self, env):
            env.stack.append(int(w3.keccak(env.getAccount(env.stack.pop()).code), 16))
            env.pc += 1
        
        def BLOCKHASH(self, env):
            env.stack.append(int(env.getBlock(env.stack.pop()).proof, 16))
            env.pc += 1
        
        def COINBASE(self, env):
            env.stack.append(int(env.lastBlock().miner, 16))
            env.pc += 1
        
        def TIMESTAMP(self, env):
            env.stack.append(int(env.lastBlock().timestamp))
            env.pc += 1
            
        def NUMBER(self, env):
            env.stack.append(int(env.blockNumber()))
            env.pc += 1
            
        def DIFFICULTY(self, env):
            env.stack.append(int(env.lastBlock().difficulty))
            env.pc += 1

        def GASLIMIT(self, env):
            env.stack.append(int(0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff)) # as blocks don't physically contain txns, there isn't real limit
            env.pc += 1
        
        def CHAINID(self, env):
            env.stack.append(int(env.chainid))
            env.pc += 1
        
        def SELFBALANCE(self, env):
            env.stack.append(env.getAccount(env.recipient).balance)
            env.pc += 1
            
        def BASEFEE(self, env):
            env.stack.append(int(0)) # london hardfork not implemented, adding this in case of use
            env.pc += 1
            
        def POP(self, env):
            env.stack.pop()
            env.pc += 1
        
        def MLOAD(self, env):
            offset = env.stack.pop()
            env.stack.push(int(memory.data[offset:offset+32].hex(), 16))
            env.pc += 1
        
        def MSTORE(self, env):
            offset = env.stack.pop()            
            value = env.stack.pop()
            env.memory.write(offset, offset+32, value)
            env.pc += 1
        
        def MSTORE8(self, env):
            offset = env.stack.pop()
            value = env.stack.pop()
            env.memory[offset] = value%0x100
            env.pc += 1
            
        def SLOAD(self, env):
            key = env.stack.pop()
            env.stack.append(env.loadStorageKey(env.stack.pop()))
            env.pc += 1
            
        def SSTORE(self, env):
            key = env.stack.pop()
            value = env.stack.pop()
            env.writeStorageKey(key, value)
            env.pc += 1
        
        def JUMP(self, env):
            env.pc = env.stack.pop()
        
        def JUMPI(self, env):
            dest = env.stack.pop()
            cond = env.stack.pop()
            env.pc = (dest if bool(cond) else (env.pc + 1))
        
        def PC(self, env):
            env.stack.append(env.pc)
            env.pc += 1
        
        def MSIZE(self, env):
            env.stack.append(len(env.memory.data))
            env.pc += 1
        
        def GAS(self, env):
            env.stack.append(env.remainingGas)
            env.pc += 1
        
        def JUMPDEST(self, env):
            env.pc += 1
        
        def PUSH1(self, env):
            env.stack.push(env.getPushData(env.pc, 1))
            env.pc += 1
        
        def PUSH2(self, env):
            env.stack.push(env.getPushData(env.pc, 2))
            env.pc += 1
            
        def PUSH3(self, env):
            env.stack.push(env.getPushData(env.pc, 3))
            env.pc += 1
            
        def PUSH4(self, env):
            env.stack.push(env.getPushData(env.pc, 4))
            env.pc += 1
            
        def PUSH5(self, env):
            env.stack.push(env.getPushData(env.pc, 5))
            env.pc += 1
            
        def PUSH6(self, env):
            env.stack.push(env.getPushData(env.pc, 6))
            env.pc += 1
            
        def PUSH7(self, env):
            env.stack.push(env.getPushData(env.pc, 7))
            env.pc += 1
            
        def PUSH8(self, env):
            env.stack.push(env.getPushData(env.pc, 8))
            env.pc += 1
            
        def PUSH9(self, env):
            env.stack.push(env.getPushData(env.pc, 9))
            env.pc += 1
            
        def PUSH10(self, env):
            env.stack.push(env.getPushData(env.pc, 10))
            env.pc += 1
            
        def PUSH11(self, env):
            env.stack.push(env.getPushData(env.pc, 11))
            env.pc += 1
            
        def PUSH12(self, env):
            env.stack.push(env.getPushData(env.pc, 12))
            env.pc += 1
            
        def PUSH13(self, env):
            env.stack.push(env.getPushData(env.pc, 13))
            env.pc += 1
            
        def PUSH14(self, env):
            env.stack.push(env.getPushData(env.pc, 14))
            env.pc += 1
            
        def PUSH15(self, env):
            env.stack.push(env.getPushData(env.pc, 15))
            env.pc += 1
            
        def PUSH16(self, env):
            env.stack.push(env.getPushData(env.pc, 16))
            env.pc += 1
            
        def PUSH17(self, env):
            env.stack.push(env.getPushData(env.pc, 17))
            env.pc += 1
            
        def PUSH18(self, env):
            env.stack.push(env.getPushData(env.pc, 18))
            env.pc += 1
            
        def PUSH19(self, env):
            env.stack.push(env.getPushData(env.pc, 19))
            env.pc += 1
            
        def PUSH20(self, env):
            env.stack.push(env.getPushData(env.pc, 20))
            env.pc += 1
            
        def PUSH21(self, env):
            env.stack.push(env.getPushData(env.pc, 21))
            env.pc += 1
            
        def PUSH22(self, env):
            env.stack.push(env.getPushData(env.pc, 22))
            env.pc += 1
            
        def PUSH23(self, env):
            env.stack.push(env.getPushData(env.pc, 23))
            env.pc += 1
            
        def PUSH24(self, env):
            env.stack.push(env.getPushData(env.pc, 24))
            env.pc += 1
            
        def PUSH25(self, env):
            env.stack.push(env.getPushData(env.pc, 25))
            env.pc += 1
            
        def PUSH26(self, env):
            env.stack.push(env.getPushData(env.pc, 26))
            env.pc += 1
            
        def PUSH27(self, env):
            env.stack.push(env.getPushData(env.pc, 27))
            env.pc += 1
            
        def PUSH28(self, env):
            env.stack.push(env.getPushData(env.pc, 28))
            env.pc += 1
            
        def PUSH29(self, env):
            env.stack.push(env.getPushData(env.pc, 29))
            env.pc += 1
            
        def PUSH30(self, env):
            env.stack.push(env.getPushData(env.pc, 30))
            env.pc += 1
            
        def PUSH31(self, env):
            env.stack.push(env.getPushData(env.pc, 31))
            env.pc += 1
            
        def PUSH32(self, env):
            env.stack.push(env.getPushData(env.pc, 32))
            env.pc += 1
            
            
            
            
            
        def DUP1(self, env):
            env.stack.push(env.stack[len(env.stack)-1])
            env.pc += 1

        def DUP2(self, env):
            env.stack.push(env.stack[len(env.stack)-2])
            env.pc += 1

        def DUP3(self, env):
            env.stack.push(env.stack[len(env.stack)-3])
            env.pc += 1

        def DUP4(self, env):
            env.stack.push(env.stack[len(env.stack)-4])
            env.pc += 1

        def DUP5(self, env):
            env.stack.push(env.stack[len(env.stack)-5])
            env.pc += 1

        def DUP6(self, env):
            env.stack.push(env.stack[len(env.stack)-6])
            env.pc += 1

        def DUP7(self, env):
            env.stack.push(env.stack[len(env.stack)-7])
            env.pc += 1

        def DUP8(self, env):
            env.stack.push(env.stack[len(env.stack)-8])
            env.pc += 1

        def DUP9(self, env):
            env.stack.push(env.stack[len(env.stack)-9])
            env.pc += 1

        def DUP10(self, env):
            env.stack.push(env.stack[len(env.stack)-10])
            env.pc += 1

        def DUP11(self, env):
            env.stack.push(env.stack[len(env.stack)-11])
            env.pc += 1

        def DUP12(self, env):
            env.stack.push(env.stack[len(env.stack)-12])
            env.pc += 1

        def DUP13(self, env):
            env.stack.push(env.stack[len(env.stack)-13])
            env.pc += 1

        def DUP14(self, env):
            env.stack.push(env.stack[len(env.stack)-14])
            env.pc += 1

        def DUP15(self, env):
            env.stack.push(env.stack[len(env.stack)-15])
            env.pc += 1

        def DUP16(self, env):
            env.stack.push(env.stack[len(env.stack)-16])
            env.pc += 1







            
    class Call(object):
        def __init__(self, storage):
            self.env = CallEnv(storage)

        def execOpcode(self, opcode, env):
            opcode(env)
            
        def call()