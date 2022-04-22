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
            self.data = bytearray()
        
        def ceil32(self, number):
            return ((((number-1)//32)+1)*32)
        
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
        
        def write(self, key: int, value: int):
            self.data[int(key)] = int(value)
        
        
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
        def __init__(self, storage, caller, recipient, state, origin, value):
            self.stack = []
            self.memory = CallMemory()
            self.storage = storage
            self.msgSender = caller
            self.txorigin = origin
            self.recipient = recipient
            self.state = state
            self.value = value
            
        def getAccount(acct):
            return self.state[w3.toChecksum]

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
        
        def sub(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            env.stack.append(int(int(a-b)%(2**256)))
        
        def mul(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            env.stack.append(int(int(a*b)%(2**256)))

        def div(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = 0 if (b==0) else a//b*(-1 if b * b < 0 else 1)
                
            env.stack.append(int(int(result)%(2**256)))
            
        def sdiv(self, env):
            a = self.unsigned_to_signed(env.stack.pop())
            b = self.unsigned_to_signed(env.stack.pop())
            result = 0 if (b==0) else a//b*(-1 if b * b < 0 else 1)
                
            env.stack.append(int(int(result)%(2**256)))

        def mod(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            env.stack.append(int(int(0 if a == 0 else (a%b))%(2**256)))
        
        def smod(self, env):
            a = self.unsigned_to_signed(env.stack.pop())
            b = self.unsigned_to_signed(env.stack.pop())
            result = 0 if mod == 0 else (abs(a) % abs(b) * (-1 if a < 0 else 1)) & (2**256-1)
            env.stack.append(int(int(result)%(2**256)))
            
        def addmod(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            c = env.stack.pop()

            result = 0 if mod == 0 else (a + b) % c

            env.stack.append(int(int(result)%(2**256)))

        def mulmod(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            c = env.stack.pop()

            result = 0 if mod == 0 else (a * b) % c

            env.stack.append(int(int(result)%(2**256)))

        def exp(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = pow(a, b, (2**256))
            env.stack.append(int(int(result)%(2**256)))

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

        def lt(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = int(a<b)
            env.stack.append(int(result))
        
        def gt(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = int(a>b)
            env.stack.append(int(result))

        def slt(self, env):
            a = self.unsigned_to_signed(env.stack.pop())
            b = self.unsigned_to_signed(env.stack.pop())
            result = int(a<b)
            env.stack.append(result)

        def sgt(self, env):
            a = self.unsigned_to_signed(env.stack.pop())
            b = self.unsigned_to_signed(env.stack.pop())
            result = int(a>b)
            env.stack.append(int(result))

        def eq(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = int(a==b)
            env.stack.append(int(result))
        
        def iszero(self, env):
            a = env.stack.pop()
            result = int(a==0)
            env.stack.append(int(result))
        
        def and_op(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = a&b
            env.stack.append(int(result))
        
        def or_op(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = a|b
            env.stack.append(int(result))
        
        def xor(self, env):
            a = env.stack.pop()
            b = env.stack.pop()
            result = a^b
            env.stack.append(int(result))
        
        def not_op(self, env):
            a = env.stack.pop()
            result = (2**256-1)-a
            env.stack.append(int(result))
        
        def byte_op(self, env):
            position = env.stack.pop()
            value = env.stack.pop()
            result = 0 if position >= 32 else (value // pow(256, 31 - position)) % 256
            env.stack.append(int(result))
        
        def shr(self, env):
            shift = env.stack.pop()
            value = env.stack.pop()
            result = (value >> shift)%(2**256)
            env.stack.append(int(result))

        def shl(self, env):
            shift = env.stack.pop()
            value = self.unsigned_to_signed(env.stack.pop())
            result = (value << shift)%(2**256)
            env.stack.append(int(result))
            if shift >= 256:
                result = 0 if value >= 0 else (2**256-1)
            else:
                result = (value >> shift) & (2**256-1)
                

        def sha3(self, env):
            start_position = env.stack.pop()
            size = env.stack.pop()

            env.memory.extend(start_position, extend)

            sha3_bytes = env.memory.read_bytes(start_position, size)
            # word_count = ceil32(len(sha3_bytes) - 1) // 32
            word_count = (((len(sha3_bytes) - 1)//32) + 1)

            # gas_cost = constants.GAS_SHA3WORD * word_count
            # computation.consume_gas(gas_cost, reason="SHA3: word gas cost")

            result = int(keccak(sha3_bytes).hex())

            env.stack.append(result)

        def ADDRESS(self, env):
            env.stack.append(env.recipient)
        
        def BALANCE(self, env):
            env.stack.append(env.getAccount(env.stack.pop()).balance)
        
        def ORIGIN(self, env):
            env.stack.append(int(env.tx.sender))
        
        def CALLER(self, env):
            env.stack.append(int(env.msgSender))
        
        def CALLVALUE(self, env):
            env.stack.append(int(env.value))
        
        def CALLDATALOAD(self, env):
            i = env.stack.pop()
            env.stack.append(int((env.data[i:i+32]).hex(), 16))
        
        def CALLDATASIZE(self, env):
            env.stack.append(len(env.data))

        def CALLDATACOPY(self, env):
            destOffset = env.stack.pop()
            offset = env.stack.pop()
            length = env.stack.pop()
            
            env.memory.data[destOffset:destOffset+length] = env.data[offset:offset+length]

        def CODESIZE(self, env):
            env.stack.push(len(env.getAccount(env.recipient).code))

        def CODECOPY(self, env):
            destOffset = env.stack.pop()
            offset = env.stack.pop()
            length = env.stack.pop()
            env.memory.data[destOffset:destOffset+length] = env.getAccount(env.recipient).code[offset:offset+length]

        def GASPRICE(self, env):
            env.stack.append(env.tx.gasprice)
        
        def EXTCODESIZE(self, env):
            env.stack.push(len(env.getAccount(env.stack.pop()).code))

        def EXTCODECOPY(self, env):
            addr = env.stack.pop()
            destOffset = env.stack.pop()
            offset = env.stack.pop()
            length = env.stack.pop()
            env.memory.data[destOffset:destOffset+length] = env.getAccount(addr).code[offset:offset+length]
            
        def RETURNDATASIZE(self, env):
            env.stack.push(0) # TODO
            
        def RETURNDATACOPY(self, env):
            env.stack.push(0) # TODO


    class Call(object):
        def __init__(self, storage):
            self.env = CallEnv(storage)

        def execOpcode(self, opcode, env):
            opcode(env)
            
        def call()