from BlockDevice import *
import numpy as np
from INode import INodeType, INode, BlockPointerFormat
from struct import Struct
import File


MAGIC_NUMBER = 0xF00DCAFE   # change me, but make it
INODE_COUNT = 1024

class BlockCache():
    def __init__(self, size):
        self.cache = [None]*size
        self.dirty = [False]*size

    def put(self, num_block, data):
        self.cache[num_block] = data
        self.dirty[num_block] = True

    def get(self, num_block):
        return self.cache[num_block]

    def isDirty(self, num_block):
        return self.dirty[num_block]

class FileSystem():
    """ A File System lives on a block device. The root block, at a
        fixed location, pulls together the block map, the inode map, and
        the root directory.

        The in-memory FileSystem object also points to the various
        caches: the block map, the inode map, the directory cache,
        which are just Python arrays (the block map and inode map - assignment 2)
        and structures (the directory cache - assignment 3)
    """

    def __init__(self, bd:BlockDevice):
        self.block_device = bd
        self.block_size = bd.block_size
        self.block_count = bd.num_blocks
        self.block_map_loc = 1   # we know this, so set it
        self.inode_map_loc = -1  # we learn this in createFS or mount
        self.root_dir_inode = 0    # not used until assignment 3
        self.inode_count = INODE_COUNT
        self.inode_map = None
        self.block_map = None
        self.dirty = 0
        self.blockCache = None
        self.dirCache = None

    # TODO: part of Assignment 4:
    def open(self, path, mode):
        """
        Return a File object corresponding to "path", opened for either
        reading, writing, creating or appending.
        Model your semantics of these flags on the Python documentation here:
        https://docs.python.org/3/library/functions.html#open
        :param path:   path to the file we want to open
        :param mode:   "r", "w", or "a"
        :return:       File object, or None if there is no such file (or it's a directory)
        """
        path_contents = path.split("/")
        if path[0] == "/":
            path_contents = path_contents[1:]
        if path[-1] == "/":
            path_contents = path_contents[:-1]

        cwd = File.inode_to_object(self, self.inode_map[self.root_dir_inode], None, "w")
        for i in range(len(path_contents)):
            fname = path_contents[i]
            try:
                cwd.ensure_cached()
                # for name in cwd.children:
                #     print(name, cwd.children[name].mode)
                cwd = cwd.get_children()[fname]
            except KeyError:
                return None
        
        if cwd.inode.isDirectory():
            return None
        return cwd

    # TODO: part of Assignment 4:
    def namei(self, path):
        """
        Return the INode structure corresponding to path
        :param path: path of a file or directory
        :return: INode structure
        """
        ret = None
        # start cwd <- root_dir,
        # iterate through elements of path,
        # finding a child of the current directory whose name matches, updating cwd as you go
        path_contents = path.split("/")
        if path[0] == "/":
            path_contents = path_contents[1:]
        if path[-1] == "/":
            path_contents = path_contents[:-1]
        
        cwd = File.inode_to_object(self, self.inode_map[self.root_dir_inode], None, "r")
        cwd.ensure_cached()
        for i in range(len(path_contents)):
            fname = path_contents[i]
            try:
                cwd = cwd.get_children()[fname]
            except KeyError:
                return None
        
        if cwd != None:
            ret = cwd.inode
        return ret

    @staticmethod
    def createFileSystem(filename, block_count, block_size = default_blocksize):
        """
        createFileSystem - creates a newly initialized file system (doesn't mount it)
        :param filename:        block device name
        :param block_count:     block device size
        :param block_size:      block size
        :return:                0 upon success
        """

        # create a FileSystem object, including block map, inode map, so that we can
        # call the same write functions as unmount to initialize it on disk.
        bd = BlockDevice(filename, blockCount=block_count, blockSize=block_size, create=True)
        fs = FileSystem(bd)

        fs.block_map = [False] * block_count # will fix this later in this function

        fs.inode_map = []
        for i in range(INODE_COUNT):
            fs.inode_map.append(INode(fs, number=i))

        bytes_in_block_map = ceildiv(block_count, 8)
        blocks_in_block_map = ceildiv(bytes_in_block_map, block_size)
        blocks_in_inode_map = ceildiv(INode.bytesPerINode() * INODE_COUNT, block_size)

        fs.inode_map_loc = fs.block_map_loc + blocks_in_block_map
        preallocated_blocks = fs.inode_map_loc + blocks_in_inode_map

        # now we know how many blocks need to be preallocated
        assert preallocated_blocks < block_count,\
            "ERROR: createFileSystem with too few blocks - need at least {}".format(preallocated_blocks)

        for i in range(preallocated_blocks):
            fs.block_map[i] = True

        # create our root directory
        fs.root_dir_inode = fs.allocINode(INodeType.DIRECTORY)

        fs.writeBlockMap()
        fs.writeINodeMap()
        fs.writeMasterBlock()

        return 0

    # Master Block contents in order:
    #   magic number - 32 bits,
    #   number of blocks in the file system - 32 bits
    #   block size, in bytes (e.g., 512, 1024, 2048, ...) - 16 bits
    #   number of inodes in the file system - 16 bits
    #   block # of the block map - 32 bits
    #   block # of the inode map - 32 bits
    #   block number of the root directory - 32 bits
    #   dirty - 8 bits
    #
    MasterBlockFormat = Struct("<IIHHIIIB")

    @staticmethod
    def mount(name):
        """
        Factory method - mounts device file, reads master block, returns FileSystem object
        :param name: name of device
        :return: FileSystem object or None if invalid file system
        """
        bd = BlockDevice(name)
        ret = FileSystem(bd)
        ret.readMasterBlock()

        if ret.magic_number != MAGIC_NUMBER:
            print("Bad magic! {} != {}".format(ret.magic_number, MAGIC_NUMBER))
            return None

        # process the dirty bit:
        #  First, want to check that the file system we're mounting was clean. If not, print warning
        #  Second, want to set the dirty bit on disk, which is only cleared at the end of unmount
        if ret.dirty != 0:
            print("Warning: mounting a file system that was not cleanly unmounted")

        ret.readBlockMap()
        ret.readINodeMap()

        ret.dirty = 1
        ret.writeMasterBlock() # set the dirty bit on disk
        ret.blockCache = BlockCache(bd.num_blocks)
        ret.dirCache = []
        return ret

    # writeMasterBlock / readMasterBlock use the struct package to get the FileSystem object's
    # critical statistics written to the master block of it's device.
    def writeMasterBlock(self):
        buf = FileSystem.MasterBlockFormat.pack(MAGIC_NUMBER, self.block_count, self.block_size,
                                                self.inode_count, self.block_map_loc,
                                                self.inode_map_loc, self.root_dir_inode, self.dirty)
        ba = bytearray(buf)
        self.block_device.write_block(0, ba, pad = True)

    def readMasterBlock(self):
        bd = self.block_device
        master_block_bytes = bytearray(bd.block_size)
        bd.read_block(0, master_block_bytes)
        (self.magic_number, self.block_count, self.block_size, self.inode_count,
         self.block_map_loc, self.inode_map_loc, self.root_dir_inode, self.dirty) = \
            FileSystem.MasterBlockFormat.unpack(master_block_bytes[0:FileSystem.MasterBlockFormat.size])

    def unmount(self):
        """
        Unmount - write block map, inode map, caches, then master block indicating a clean unmount
        :return: True on success
        """
        self.flushDirCache()
        self.writeBlockMap()
        self.writeINodeMap()
        self.flushBlockCache()
        # When we have a directory cache and a file cache, flush them here:
        # TODO: flush file and directory caches
        # clear dirty bit, then write clean master block to disk:
        self.dirty = 0
        self.writeMasterBlock()
        self.block_device.close()
        return True

    def flushDirCache(self):
        for d in self.dirCache:
            d.sync()

    """
    Block Cache functions:
    flushBlockCache - writes the block cache to disk
    readBlockCache - reads a block of block pointers
    """
    def flushBlockCache(self):
        buf = bytearray(self.block_device.block_size)
        # todo: check whether the buffer is a bytearray or an array of ints
        for i in range(self.block_device.num_blocks):
            if self.blockCache.isDirty(i):
                offset = 0
                cached_block = self.blockCache.get(i)
                if isinstance(cached_block, bytearray):
                    self.block_device.write_block(i, cached_block)
                else:
                    for bptr in cached_block:
                        BlockPointerFormat.pack_into(buf, offset, bptr)
                        offset += BlockPointerFormat.size
                    self.block_device.write_block(i, buf)

    # Assignment 4: important note:
    # This is the cache-helper for INode.getDiskAddressOfBlock
    # If you're using this starting point, part of your assignment
    # is to understand what this method does. (really!) You'll want a sibling method
    # to this one for handling the bytearray contents of INodes as a helper for
    # Inode.read and write

    def readBlockCache(self, index, blocks, alloc_p = True):
        block_ptrs_per_block = self.block_device.block_size // 4
        if blocks[index] == 0:
            if alloc_p:
                block_num = self.allocBlock()
                blocks[index] = block_num
                self.blockCache.put([0] * block_ptrs_per_block, block_num)
                return self.blockCache.get(block_num)
            else:
                # if it's not
                return None
        block_num = blocks[index]
        if self.blockCache.get(block_num) == None:
            buf = bytearray(self.block_device.block_size)
            self.block_device.read_block(block_num, buf)
            ptrs = [0] * block_ptrs_per_block
            for i in range(block_ptrs_per_block):
                (ptrs[i],) = BlockPointerFormat.unpack_from(buf, i * 4)
            self.blockCache.put(block_num, ptrs)
        return self.blockCache.get(block_num)

    """
    BlockMap functions:
    The BlockMap is how we keep track of allocated and free blocks.
    On-disk, it's a contiguous set of blocks storing the sequence of bits
    0 -> free, 1 -> allocated.
    In memory it's a Python array of booleans, False -> free, True -> allocated
    """
    #
    # allocBlock and freeBlock allocate and free block if the file system has
    # been mounted.
    #
    def allocBlock(self):
        for i in range(len(self.block_map)):
            if self.block_map[i] == False:
                self.block_map[i] = True
                return i
        print("There are no free blocks available for allocation")
        return -1

    def freeBlock(self, n:int):
        if self.block_map[n] == False:
            print("Warning: attempt to free an already unallocated block {}".format(n))
        self.block_map[n] = False

    # Internal read/write functions for mount/unmount
    def writeBlockMap(self):
        """
        flush the current block map to disk
        :return: the number of blocks written
        """
        blockmap_buffer = bytearray(self.block_size)

        # Split block map into block-sized chunks
        blockmapchunks = split_array(self.block_map, self.block_size * 8)

        # iterate through each chunk, turning it into a bytearray, and writing it
        for i in range(len(blockmapchunks)):
            buffer = bytearray(self.block_size)
            bitsAsBytes = bytearray(np.packbits(blockmapchunks[i]))
            buffer[0:len(bitsAsBytes)] = bitsAsBytes
            self.block_device.write_block(self.block_map_loc + i, buffer)
        return len(blockmapchunks)

    def readBlockMap(self):
        """
        read the block map from disk.
        Assumes that self contains the metadata from the master block
        :return: side-effect that self has a populated block map
        """
        blockmap_buffer = bytearray(self.block_size)
        self.block_map = [False] * self.block_count

        bitOffset = 0
        bitsPerBlock = self.block_size * 8

        for diskBlock in range(self.block_map_loc, self.inode_map_loc):
            self.block_device.read_block(diskBlock, blockmap_buffer)
            blockmap_bits = np.unpackbits(blockmap_buffer)
            self.block_map[bitOffset:bitOffset+bitsPerBlock] = blockmap_bits
            bitOffset += bitsPerBlock

    def blockMapAsString(self):
        resultstring = ""
        for i in range(len(self.block_map)):
            if i % 8 == 0 and i != 0:
                resultstring += "|"
            if i % 64 == 0 and i != 0:
                resultstring += "\n"
            if self.block_map[i]:
                resultstring += "1"
            else:
                resultstring += "0"
        return resultstring

    """
    INodeMap functions:
    The INodeMap is an array of all of the inodes in this file system. It's also how
    we keep track of which ones are free. The status byte is one of the INodeType enum
    values: FREE, FILE, DIRECTORY, SYMLINK
    """

    #
    # allocINode and freeINode both work like alloc and free block
    #

    def allocINode(self, inode_type:INodeType):
        for i in range(len(self.inode_map)):
            if self.inode_map[i].flags == INodeType.FREE:
                self.inode_map[i].flags = inode_type
                return i
        # if we made it this far, all of the inodes are allocated
        print("ERROR: there are no inodes available for allocation")
        return -1

    def freeINode(self, n:int):
        # todo: throw an error if the user tries to free a reserved block
        self.inode_map[n].flags = INodeType.FREE

    # Internal read/write functions for mount/unmount
    def writeINodeMap(self):
        inode_buffer = bytearray(self.block_size)
        blocks_in_inode_map = ceildiv(INode.bytesPerINode() * INODE_COUNT, self.block_size)
        inodes_per_block = self.block_size // INode.bytesPerINode()
        inode_index = 0
        for i in range(blocks_in_inode_map):
            for j in range (inodes_per_block):
                self.inode_map[inode_index].packIntoBuffer(inode_buffer, j * INode.bytesPerINode())
                inode_index = inode_index + 1
            self.block_device.write_block(self.inode_map_loc + i, inode_buffer)

    def readINodeMap(self):
        blocks_in_inode_map = ceildiv(INode.bytesPerINode() * INODE_COUNT, self.block_size)
        inode_buffer = bytearray(self.block_size)
        inodes_per_block = self.block_size // INode.bytesPerINode()

        inode_index = 0
        self.inode_map = [None] * INODE_COUNT
        for i in range(blocks_in_inode_map):
            self.block_device.read_block(self.inode_map_loc + i, inode_buffer)
            for j in range(inodes_per_block):
                t = INode(self)
                start = j * INode.bytesPerINode()
                end = start + INode.bytesPerINode()
                t.unpackFromBuffer(inode_buffer[start:end])
                self.inode_map[inode_index] = t
                inode_index = inode_index + 1

    def inodeMapAsString(self):
        resultstring = ""
        for i in range(len(self.inode_map)):
            if i % 8 == 0 and i != 0:
                resultstring += "|"
            if i % 64 == 0 and i != 0:
                resultstring += "\n"
            resultstring += self.inode_map[i].charRep()
        return resultstring

########## end of FileSystem definition

# utility functions - inspired by Alyssa's submission:

def ceildiv(x, y): # Like x // y, but rounds towards (+/-) infinity rather than 0
    return -(-x // y)

def split_array(array, n):
    """
    Splits an array of arbitrary length into many arrays of length n and returns the list of those arrays;
    the final array in the list is non-padded, so e.g. splitting an array of length 37 into chunks of length 8
    will return four arrays of length 8 and one of length 5
    """
    num_splits = ceildiv(len(array), n)
    splits = [[]] * num_splits
    for i in range(num_splits): #Populates the output list
        if i == num_splits - 1:
            splits[i] = array[(i * n):]
        else:
            splits[i] = array[(i * n):((i * n) + n)]
    return splits

##### nose tests

# def test_newfs():
#     FileSystem.createFileSystem("nose_fs", block_count=200, block_size=1024)
#     fs = FileSystem.mount("nose_fs")
#     aFileIndex = -1
#     aDirIndex = -1
#     for i in range(10):
#         fs.allocBlock()
#     for i in range(10):
#         aDirIndex = fs.allocINode(INodeType.DIRECTORY)
#         aFileIndex = fs.allocINode(INodeType.FILE)
#     fs.unmount()
#     fs2 = FileSystem.mount("nose_fs")
#     for b in range(10):
#         assert fs2.block_map[b], "huh, block {} wasn't allocated".format(b)
#     assert fs2.inode_map[aFileIndex].isFile()
#     assert fs2.inode_map[aDirIndex].isDirectory()
#     fs2.unmount()

# def test_inode_lookup():
#     fs = FileSystem.mount("nose_fs")
#     inode_indices = [None] * 10
#     inodes = [None] * 10
#     block_addrs = [None] * 10
#     i = 0

#     for i in range(5):
#         inode_indices[i] = fs.allocINode(INodeType.FILE)
#         inodes[i] = fs.inode_map[i]
#         block_addrs[i] = inodes[i].getDiskAddrOfBlock(fs, 10 ** i, True)
#     fs.unmount()
#     fs = None

#     fs2 = FileSystem.mount("nose_fs")
#     for i in range(5):
#         block_addr = inodes[i].getDiskAddrOfBlock(fs2, 10 ** i, True)
#         assert block_addr == block_addrs[i], "get disk address of block lookup failed: {} != {}".format(block_addr, block_addrs[i])
#         missing_block = inodes[i].getDiskAddrOfBlock(fs2, (10 ** i) - 1, False)
#         assert missing_block == -1, "get disk addr of missing block failed: {} != -1".format(missing_block)
#     fs2.unmount()

