from enum import Enum
from struct import pack,unpack,calcsize
from math import ceil
from numpy import packbits,unpackbits,uint8
from BlockDevice import *

MAGIC = 0x30541541
IMAGIC = 0x3665
BYTES_PER_INODE = calcsize("2B3H30I")

class MasterBlock(Enum):
    MAGIC = 0
    BLOCK_SIZE = 1
    BLOCK_COUNT = 2
    INODE_COUNT = 3
    BLOCKMAP_LOC = 4
    INODEMAP_LOC = 5
    ROOT_LOC = 6
    FLAGS = 7

class iFlags(Enum):
    STATUS = 0
    FILE = 1
    DIR = 2
    SYMLINK = 3

class iNodeData(Enum):
    # lowercase for easier matching against iNode attributes
    flags = 0
    level = 1
    num = 2
    perms = 3
    imagic = 4
    cdate = 5
    mdate = 6
    block_ptrs = 7


class FileSystem:
    @staticmethod
    def createFileSystem(filename,block_count,block_size=default_blocksize):
        assert block_size >= BYTES_PER_INODE, "block size is too small"
        
        fs = FileSystem()
        fs.bd = BlockDevice(filename,block_count,block_size,True)
        fs.filename = fs.bd.filename

        # Initialize master block.
        # Since inodemap doesn't have a fixed size,
        # root is placed into the last block so that they grow
        # towards each other
        inode_count = 1
        blockmap_loc = 1
        blockmap_size = ceil(block_count / (8*block_size))
        inodemap_loc = blockmap_size+1
        root_loc = block_count - 1
        flags = 1       # uhh...idk what other flags to include

        fs.mblock = (MAGIC, block_size, block_count, inode_count, blockmap_loc, inodemap_loc, root_loc, flags)
        mbBytes = bytearray(pack("IHIHIIIB", *fs.mblock))
        fs.bd.write_block(0, mbBytes, True)

        # Initialize blockmap
        fs.bmap = BlockMap(block_count)

        # Initialize inodemap
        fs.imap = iNodeMap()

        # Initialize root (inode)
        root_flags = [1,0,1,0]
        num = 0
        block_ptrs = [0]*28
        block_ptrs[0] = root_loc
        root = iNode(root_flags,0,num,0,IMAGIC,0,0,block_ptrs)
        fs.imap.add_inode(root)
        fs.bmap.array[-1] = True

        # Mark allocated blocks in blockmap
        inodemap_size = ceil(len(fs.imap.array)*BYTES_PER_INODE / block_size)
        for i in range(inodemap_size + inodemap_loc):
            fs.bmap.array[i] = True

        # Write out to file 
        fs.bmap.writeOut(fs.bd,block_size,inodemap_loc)
        fs.imap.writeOut(fs.bd,block_size,inodemap_loc)

        fs.bd.close()
        return fs

    @staticmethod
    def mount(filename):
        status = 1
        fs = FileSystem()
        fs.bd = BlockDevice(filename)
        block_size = fs.bd.blocksize
        buff = bytearray(bytes(block_size))
        read_from = 0       # block number

        # Read master block
        fs.bd.read_block(read_from,buff)
        bytes_to_read = calcsize("IHIHIIIB")
        fs.mblock = list(unpack("IHIHIIIB", buff[:bytes_to_read]))
        if fs.mblock[MasterBlock.FLAGS.value] == 0:
            status == 0
        fs.mblock[MasterBlock.FLAGS.value] = 0
        read_from += 1

        # Read blockmap
        inodemap_loc = fs.mblock[MasterBlock.INODEMAP_LOC.value]
        block_count = fs.mblock[MasterBlock.BLOCK_COUNT.value]
        fs.bmap = BlockMap()
        while read_from < inodemap_loc:
            fs.bd.read_block(read_from,buff)
            fs.bmap.array.extend(unpackbits(buff)[:block_count])
            read_from += 1

        # Read inodemap
        fs.imap = iNodeMap()
        inodes_per_block = block_size // BYTES_PER_INODE
        while read_from < len(fs.bmap.array):
            if fs.bmap.array[read_from]:
                fs.bd.read_block(read_from,buff)
                
                # Interpret inode-size portions of read-in block
                for j in range(inodes_per_block):
                    start = j*BYTES_PER_INODE
                    end = start + BYTES_PER_INODE
                    inode_data = unpack("2B3H30I", buff[start:end])
                    node = iNode.createiNode(list(inode_data))
                    if node != None:
                        fs.imap.add_inode(node)

                read_from += 1
            else:
                break

        return (fs,status)

    def unmount(self):
        # Write out blockmap
        block_size = self.mblock[MasterBlock.BLOCK_SIZE.value]
        inodemap_loc = self.mblock[MasterBlock.INODEMAP_LOC.value]
        self.bmap.writeOut(self.bd,block_size,inodemap_loc)

        # Write out inodemap
        self.imap.writeOut(self.bd,block_size,inodemap_loc)

        # Write out master block
        self.mblock[MasterBlock.FLAGS.value] = 1
        buff = bytearray(pack("IHIHIIIB", *self.mblock))
        self.bd.write_block(0,buff,True)

        self.bd.close()
        self.bd = None


class BlockMap:
    def __init__(self,block_count=0):
        self.array = [False] * block_count

    # Returns a binary representation of the blockmap with 64 blocks per line and a separator every 8 blocks
    def rep(self):
        a = self.array
        s = ""

        num_rows = ceil(len(a) / 64)
        last = False
        for i in range(num_rows):
            idx = 64 * i
            if i == num_rows - 1:
                last = True
                length = len(a) % 64
            else:
                length = 64
            for j in range(length):
                if j != 0 and j%8 == 0:
                    s += '|'
                if a[idx+j]:
                    s += '1'
                else:
                    s += '0'
            if not last:
                s += "\n"

        return s

    # Allocate a block and print its number
    def alloc_block(self):
        try:
            i = self.array.index(False)
            self.array[i] = True
            return i
        except ValueError:
            return -1

    # Mark block <n> as free
    def free_block(self,n):
        if n < 3:
            return 0
        else:
            self.array[n] = False
            return 1

    # Returns a bytearray representation of the blockmap (for writing)
    def toBytes(self):
        buff = packbits(self.array)
        return bytearray(buff)

    # Writes blockmap out using a given BlockDevice
    def writeOut(self,bd,block_size,inodemap_loc):
        buff = self.toBytes()
        
        for i in range(1,inodemap_loc):
            start = (i-1)*block_size
            end = start + block_size
            if end > len(buff):
                end == len(buff)
            bd.write_block(i,buff[start:end],True)


class iNode:
    def __init__(self,flags,level,num,perms,imagic,cdate,mdate,block_ptrs):
        # Ordered based on size...because otherwise the bytearray for packing/unpacking needs size >128 bytes
        self.flags = flags
        self.level = level
        self.num = num
        self.perms = perms
        self.imagic = imagic
        self.cdate = cdate
        self.mdate = mdate
        self.block_ptrs = block_ptrs

    # Make integer list of inode contents
    def flatten(self):
        attrs = vars(self)
        data = []
        for name, member in iNodeData.__members__.items():
            if name == "flags":
                data.append(packbits(self.flags)[0])
            elif name == "block_ptrs":
                data.extend(self.block_ptrs)
            else:
                data.append(attrs[name])

        assert len(data) == 35, "toBytes: mismatch in number of items"
        return data

    # Creates an iNode object (if appropriate) from read-in data (unpacked bytearray as list)
    @staticmethod
    def createiNode(data):
        assert len(data) == 35, "createiNode: mismatch in number of items"

        # Modify data contents to match format in iNode class
        flat_flags = data[iNodeData.flags.value]
        flags = list(unpackbits(uint8(flat_flags)))
        # Check if valid (initialized) inode
        if data[iNodeData.num.value] == 0 and flags[iFlags.STATUS.value] == 0:
            return None
        data[iNodeData.flags.value] = flags
        block_ptrs = data[iNodeData.block_ptrs.value:]
        data = data[:iNodeData.block_ptrs.value]
        data.append(block_ptrs)

        node = iNode(*data)
        return node



class iNodeMap:
    def __init__(self):
        self.array = []
        self.size = 0       # number of initialized inodes

    # Return summary of inodes
    def rep(self):
        s = ""
        j = 0
        for i in range(len(self.array)):
            # Formatting (mimics blockmap)
            if j != 0:
                if j % 64 == 0:
                    s += "\n"
                elif j % 8 == 0:
                    s += "|"

            node = self.array[i]
            if node == None:
                pass
            else:
                flags = node.flags
                if flags[iFlags.STATUS.value]:
                    if flags[iFlags.FILE.value]:
                        s += 'f'
                    elif flags[iFlags.DIR.value]:
                        s += 'd'
                    elif flags[iFlags.SYMLINK.value]:
                        s += 's'
                    else:
                        # allocated but no file type; shouldn't happen but accounted for just in case
                        s += '1'
                else:
                    s += '0'

        return s

    # Allocate a free inode, mark it with <kind>, and return its number
    def alloc_inode(self,kind):
        if kind == 'f':
            flags = [1,1,0,0]
        elif kind == 'd':
            flags = [1,0,1,0]
        elif kind == 's':
            flags = [1,0,0,1]
        else:
            return -1

        if self.size != len(self.array):
            for j in range(len(self.array)):
                if self.array[j] == None:
                    i = j
                    break
                else:
                    status = self.array[j].flags[iFlags.STATUS.value]
                    if not status:
                        i = j
                        break
        else:
            i = len(self.array)
            self.array.append(None)

        block_ptrs = [0]*28
        node = iNode(flags,0,i,0,IMAGIC,0,0,block_ptrs)
        self.array[i] = node
        self.size += 1
        return(i)

    # Mark inode <n> as free.
    def free_inode(self,n):
        if n > 0 and n < len(self.array):
            inode = self.array[n]
            if inode != None:
                inode.flags[iFlags.STATUS.value] = 0


    # Adds an inode to the inodemap and updates its size
    def add_inode(self,inode):
        if inode == None:
            return

        # Check if need to expand array
        if inode.num == 0 or inode.num >= len(self.array):
            m = inode.num - len(self.array)
            self.array.extend([None]*(m+1))

        self.array[inode.num] = inode
        self.size += 1

    # Pack inodemap into bytearray (in preparation for writing to file)
    def toBytes(self):
        buff = bytearray(bytes(BYTES_PER_INODE*self.size))
        i = 0
        for node in self.array:
            if i == self.size:
                break
            if node == None:
                pass
            else:
                inode_data = node.flatten()
                start = i*BYTES_PER_INODE
                end = start+BYTES_PER_INODE
                buff[start:end] = pack("2B3H30I", *inode_data)
                i += 1
        return buff

    # Write inodemap out to file
    def writeOut(self,bd,block_size,inodemap_loc):
        buff = self.toBytes()
        
        last = False
        inodes_per_block = block_size // BYTES_PER_INODE
        for i in range(self.size):
            if last:
                break
            start = i*block_size
            end = start + block_size
            if end > len(buff):
                end == len(buff)
                last = True
            bd.write_block(inodemap_loc+i,buff[start:end],last)


def test_create_mount_fs():
    bc = 127
    bs = 256
    fs = FileSystem.createFileSystem("testfs",bc,bs)
    mfs,status = FileSystem.mount(fs.filename)
    assert status == 1

    # test master block read
    mfs_bc = mfs.mblock[MasterBlock.BLOCK_COUNT.value]
    mfs_bs = mfs.mblock[MasterBlock.BLOCK_SIZE.value]
    assert mfs_bc == bc, "mismatched block count"
    print(mfs_bs)
    assert mfs_bs == bs, "mismatched block size"

    # test blockmap read
    print("created file system blockmap:")
    print(fs.bmap.rep())
    print("mounted file system blockmap:")
    print(mfs.bmap.rep())
    assert fs.bmap.rep() == mfs.bmap.rep(), "mismatched blockmap"

    # test inodemap read
    print("created file system inodemap:")
    print(fs.imap.rep())
    print("mounted file system inodemap:")
    print(mfs.imap.rep())
    assert fs.imap.rep() == mfs.imap.rep(), "mismatched inodemap"
    mfs.unmount()

def test_fs():
    bc = 127
    bs = 256
    filename = FileSystem.createFileSystem("testfs",bc,bs).filename
    fs,status = FileSystem.mount(filename)
    assert status == 1
    init_bmap = fs.bmap.rep()
    init_imap = fs.imap.rep()

    print("initial blockmap & inodemap")
    print(init_bmap)
    print(init_imap)

    i = fs.imap.alloc_inode('f')
    b = fs.bmap.alloc_block()
    print("maps after allocation")
    print(fs.imap.rep())
    print(fs.bmap.rep())
    assert i != -1, "alloc_inode failed"
    assert b != -1, "alloc_block failed"

    fs.imap.free_inode(i)
    fs.bmap.free_block(b)
    print("maps after freeing just allocated nodes")
    print(fs.imap.rep())
    print(fs.bmap.rep())
    assert init_bmap == fs.bmap.rep(), "blockmap mismatch"
    assert init_imap+"0" == fs.imap.rep(), "inodemap mismatch"

    fs.unmount()