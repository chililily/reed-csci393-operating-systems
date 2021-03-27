from enum import Enum
from struct import *
from math import ceil,log

INodeFormat = Struct("<HIIHBBII")
BlockPointerFormat = Struct("<I")
INODE_MAGIC = 0xD0D0F00D


class INodeType(Enum):
    FREE = 0
    FILE = 1
    DIRECTORY = 2
    SYMLINK = 3


class INode():
    BlockPtrsPerInode = 26
    inode_num = 0
    cdate = 0
    mdate = 0
    flags = INodeType.FREE
    perms = 0
    level = 0
    length = 0  # content length in bytes, forgot this in As 2. Struct includes it
    magic_number = 0
    block_ptrs = None
    _bytes_per_in = -1  # cached value

    def __init__(self, number=-1):
        self.inode_num = number
        self.block_ptrs = [0] * INode.BlockPtrsPerInode

    ########### Exported functions

    # TODO: Assignment 3.2
    #    Tricky bits: both the file_offset and the buffer_len might not
    #    (probably won't be) block aligned.
    #    Read the blocks that are covered by this request, then copy the bytes
    #    from those blocks into buffer. Write tests to catch the various cases!
    #    If the user reads from a block that is in the file, but doesn't have
    #    a block allocated to it, just copy 0-bytes to the buffer for that block

    def read(self, file_offset: int, buffer):
        """
        Read from this INode into buffer

        :param file_offset: the offset into the file we want to read from
        :param buffer:      read up to len(buffer) bytes into this buffer
        :return:            number of bytes successfully read
        """
        pass

    # TODO: Assignment 3.2
    #     Similarly tricky as read, except when you look up blocks, pass the
    #     alloc = True flag to getDiskAddrOfBlock, so that the block does get
    #     allocated.
    def write(self, file_offset: int, buffer):
        """
        Write buffer to INode @ file_offset

        :param file_offset:  offset we want to write to
        :param buffer:       write these bytes to the file
        :return:             number of bytes written
        """
        pass

    # isFile and isDirectory help clients of the API not need to know about
    # our enum type.

    def isFile(self):
        return self.flags == INodeType.FILE

    def isDirectory(self):
        return self.flags == INodeType.DIRECTORY

    # returns a character with the textual representation of its type
    def charRep(self):
        chars = "_fds"
        return chars[self.flags.value]

    def truncate(self, len):
        # TODO: mark any allocated blocks in the truncated range
        #       as free if we shorten the inode
        self.length = len

    ########### Internal functions

    def getDiskAddrOfBlock(self, fs, block_number, alloc_p=False):
        """
        Get the disk address of <block_number> in this INode
            just a wrapper for the _recursive version below
        :param fs:              our FileSystem object (to access blockmap)
        :param block_number:    the block we're looking for
        :param alloc_p:           if it's not there, do we allocate one?
        :return:                -1 on failure, or a > 0 block_number for this INode's block
        """
        return self.getDiskAddrOfBlock_recursive(fs, block_number, alloc_p, self.block_ptrs, self.level)

    # TODO: Assignment 3.1
    #     Start by considering just level 0 (the blocks array is an array of block addresses)
    #     Then figure what size is too big for level 0, and how to convert to a level-1 inode,
    #     and how to look up data in a level 1 inode, then use recursion to take care of bigger levels

    def getDiskAddrOfBlock_recursive(self, fs, block_number, alloc_p, blocks, level):
        """
        Helper function for getDiskAddrOfBlock, which takes level and blocks, which makes recursion feasible
        In a lot of ways, this is the real business of an INode.
        Note, if the INode grows, we may have to increase the level.

        :param fs:           our filesystem (to allow us to alloc blocks)
        :param block_number: the block we seek
        :param alloc_p:      whether we should allocate if the sought block is missing
        :param blocks:       the block array at this level
        :param level:        the distance from the leaves of the block pointer tree
        :return:             -1 if alloc is false and block is missing, otherwise the disk block address
                                corresponding to this INode's data @ block_number
        """
        ptrsPerBlock = fs.block_size // 4

        if blocks == None:
            if alloc_p:
                blocks = [0]*self.BlockPtrsPerInode
            else:
                return -1

        # At start of recursion, compare target block number against inode's current maximum capacity
        if level == self.level:
            if alloc_p:
                self.ensureCapacity(block_number, fs.block_size,level)
                bumps = self.level - level
                if bumps > 0:
                    # Bump current block pointer array down by however many levels were added by ensureCapacity
                    for i in range(bumps):
                        old_blockPtrs = [0]*ptrsPerBlock
                        if self.block_ptrs != None:
                            old_blockPtrs[:self.BlockPtrsPerInode] = self.block_ptrs
                        new_blockPtrs = [0]*self.BlockPtrsPerInode
                        block_loc = fs.allocBlock()
                        assert block_loc != -1
                        new_blockPtrs[0] = block_loc
                        self.block_ptrs = new_blockPtrs
                        fs.block_ptrs_cache[block_loc] = old_blockPtrs
                    return self.getDiskAddrOfBlock_recursive(fs, block_number, alloc_p, self.block_ptrs, self.level)
            else:
                capacity = self.BlockPtrsPerInode*(ptrsPerBlock**level)
                if block_number > capacity:
                    return -1

        # Base case
        if level == 0:
            if alloc_p and blocks[block_number] == 0:
                block_loc = fs.allocBlock()
                assert block_loc != -1
                blocks = blocks
                blocks[block_number] = block_loc
                fs.block_ptrs_cache[block_loc] = blocks
            return blocks[block_number]

        # Figure out which block-pointer subtree to walk
        width_subtree = ptrsPerBlock**level              # max amt of leaves
        which_subtree = block_number // width_subtree    # which elt in blocks
        block_to_read = blocks[which_subtree]

        # Missing block (pointer)
        if block_to_read == 0:
            if alloc_p:
                # Add new array (level) of block pointers at root of designated subtree
                block_loc = fs.allocBlock()
                assert block_loc != -1
                blocks[which_subtree] = block_loc
                next_blocks = [0]*ptrsPerBlock
            else:
                return -1
        # Not missing, so fetch next level (down) of block pointers
        else:
            next_blocks = fs.block_ptrs_cache[block_to_read]
            if next_blocks == None:
                buff = bytearray(bytes(fs.block_size))
                fs.block_device.read_block(block_to_read, buff)
                fmt = "<"+str(ptrsPerBlock)+"I"
                next_blocks = list(unpack(fmt, buff))

        local_block_number = block_number - which_subtree*width_subtree
        return self.getDiskAddrOfBlock_recursive(fs, local_block_number, alloc_p, next_blocks, level-1)
                
    # Checks if iNode's level can accommodate < num_blocks > and increases it if necessary
    def ensureCapacity(self,num_blocks,block_size,level):
        ptrsPerBlock = block_size // 4
        capacity = self.BlockPtrsPerInode*(ptrsPerBlock**level)
        if capacity < num_blocks:
            self.level = ceil(log(num_blocks / self.BlockPtrsPerInode, ptrsPerBlock))

    #
    # The pack/unpack functions take care of getting an INode into and out of a bytearray.
    #
    def packIntoBuffer(self, buffer, offset):
        """
        Pack this inode into buffer @offset
        :param buffer: the buffer to pack into
        :param offset: where to pack my bits
        :return: void
        """
        INodeFormat.pack_into(buffer, offset, self.inode_num, self.cdate, self.mdate,
                              self.perms, self.level, self.flags.value, self.length, INODE_MAGIC)
        off = offset + INodeFormat.size
        for i in range(INode.BlockPtrsPerInode):
            BlockPointerFormat.pack_into(buffer, off, self.block_ptrs[i])
            off += BlockPointerFormat.size

    def unpackFromBuffer(self, buffer):
        """
        Reconstitute my instance variables from a buffer
        :param buffer: the buffer holding my bits
        :return: void
        """
        (self.inode_num, self.cdate, self.mdate, self.perms, self.level, flagVal, self.length, self.magic_number) \
            = INodeFormat.unpack_from(buffer)
        self.flags = INodeType(flagVal)
        assert self.magic_number == INODE_MAGIC, "Bad magic in INode.unpackFromBuffer"

    @staticmethod
    def bytesPerINode():
        # we save this value in the class for reuse...
        if INode._bytes_per_in > 0:
            return INode._bytes_per_in
        # but the first time this method is called, we calculate it:
        unrounded_bpi = INodeFormat.size + 4 * INode.BlockPtrsPerInode
        # the block pointer array's alignment might induce some padding
        # granularity is the size of a block pointer - lets figure out if it adds space
        granularity = BlockPointerFormat.size
        round_error = unrounded_bpi % granularity
        if round_error != 0:
            unrounded_bpi += granularity - round_error
        # unrounded_bpi is now a misnomer - it's rounded up to the nearest multiple of granularity,
        # so save it in our class variable, and return it:
        INode._bytes_per_in = unrounded_bpi
        return INode._bytes_per_in
        