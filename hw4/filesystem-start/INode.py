from enum import Enum
from struct import *
import FileSystem

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

    def __init__(self, fs, number=-1):
        self.inode_num = number
        self.block_ptrs = [0] * INode.BlockPtrsPerInode
        self.fs = fs

    ########### Exported functions

    # TODO: Assignment 4
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
        bytes_read = 0
        block_to_read = file_offset // self.fs.block_size   # local to inode
        # print(block_to_read, file_offset)
        if block_to_read == 0:
            offset_in_block = file_offset
        else:
            offset_in_block = file_offset % block_to_read
        read_buffer = bytearray(self.fs.block_size)

        while bytes_read < len(buffer):
            block_addr = self.getDiskAddrOfBlock(self.fs, block_to_read)
            if block_addr == -1:    # no more data to read
                break

            if self.fs.block_map[block_addr] == 1:       # skip if block isn't allocated
                # Get block: check cache first, otherwise read in
                cached_block = self.fs.blockCache.get(block_addr)
                if cached_block != None:
                    read_buffer = cached_block
                else:
                    self.fs.block_device.read_block(block_addr, read_buffer)
                
                # Read to end of block, or read to end of buffer, whichever's shorter
                bytes_to_read = min(self.fs.block_size-offset_in_block, len(buffer)-bytes_read)
                start = bytes_read
                stop = start + bytes_to_read
                read_start = offset_in_block
                read_stop = read_start + bytes_to_read
                # print(start,stop,read_start,read_stop)
                buffer[start:stop] = read_buffer[read_start:read_stop]
                
                bytes_read += bytes_to_read
                # Remaining blocks will be (left-)aligned
                if offset_in_block != 0:
                    offset_in_block = 0

            block_to_read += 1

        return bytes_read


    # TODO: Assignment 4
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
        block_to_write = file_offset // self.fs.block_size
        if block_to_write == 0:
            offset_in_block = file_offset
        else:
            offset_in_block = file_offset % block_to_read
        bytes_written = 0

        while bytes_written < len(buffer):
            block_addr = self.getDiskAddrOfBlock(self.fs, block_to_write, True)

            w_buffer = bytearray(self.fs.block_size)
            bytes_to_write = min(self.fs.block_size-offset_in_block, len(buffer)-bytes_written)
            # If bytes to be written don't fill block, read block to retrieve not-to-be-overwritten bytes
            if bytes_to_write < self.fs.block_size:
                # check cache first, otherwise read in
                cached_block = self.fs.blockCache.get(block_addr)
                if cached_block != None:
                    w_buffer = cached_block
                else:
                    self.fs.block_device.read_block(block_addr, w_buffer)

            # Write block
            start = bytes_written
            stop = start + bytes_to_write
            write_start = offset_in_block
            write_stop = write_start + bytes_to_write
            w_buffer[write_start:write_stop] = buffer[start:stop]
            self.fs.blockCache.put(block_addr, w_buffer)

            if offset_in_block != 0:
                offset_in_block = 0
            bytes_written += bytes_to_write
            block_to_write += 1

        self.length += bytes_written
        return bytes_written

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

    def getDiskAddrOfBlock(self, fs:FileSystem, block_number, alloc_p=False):
        """
        Get the disk address of <block_number> in this INode
            just a wrapper for the _recursive version below
        :param fs:              our FileSystem object (to access blockmap)
        :param block_number:    the block we're looking for
        :param alloc_p:           if it's not there, do we allocate one?
        :return:                -1 on failure, or a > 0 block_number for this INode's block
        """
        if alloc_p:
            self.ensureCapacity(fs, block_number)
            # note: in this case, we ignore the length, but also don't adjust it.
            # we should do that in inode.write
        else:
            if block_number >= FileSystem.ceildiv(self.length, fs.block_size):
                # we're asking for a block past the current file size, in read mode
                return -1

        return self.getDiskAddrOfBlock_recursive(fs, block_number, alloc_p, self.block_ptrs, self.level)

    # TODO: Assignment 3.1
    #     Start by considering just level 0 (the blocks array is an array of block addresses)
    #     Then figure what size is too big for level 0, and how to convert to a level-1 inode,
    #     and how to look up data in a level 1 inode, then use recursion to take care of bigger levels

    def getDiskAddrOfBlock_recursive(self, fs:FileSystem, block_number, alloc_p, blocks, level):
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

        if level == 0:
            assert block_number < len(blocks), \
                "internal error:  level 0 blocks overflow {} >= {}".format(block_number, len(blocks))
            if blocks[block_number] == 0:
                if alloc_p:
                    blocks[block_number] = fs.allocBlock()
                else:
                    print("can't find block {} in {}".format(block_number, blocks))
                    return -1
            return blocks[block_number]

        else:
            block_ptrs_per_block = fs.block_size // 4
            block_pointers_per_index = block_ptrs_per_block ** level
            inner_block_num = block_number // block_pointers_per_index
            inner_offset = block_number % block_pointers_per_index

            inner_blocks = fs.readBlockCache(inner_block_num, blocks)
            return self.getDiskAddrOfBlock_recursive(fs, inner_offset, alloc_p, inner_blocks, level-1)

    def ensureCapacity(self, fs, block_number):
        block_ptrs_per_block = fs.block_size // 4

        while block_number >= len(self.block_ptrs) * (block_ptrs_per_block ** self.level):
            self.increaseLevel(fs)

    #
    # Increases the indirection level of this INode.
    # Preserves the previous INode pointers - just pushes them down a level.
    #
    def increaseLevel(self, fs:FileSystem):
        new_b = fs.allocBlock()
        block_ptrs_per_block = fs.block_size // 4
        # bps is our new, fresh acres of block pointers
        bps = [0] * block_ptrs_per_block
        # copy the inodes block pointers to our new array
        bps[0:len(self.block_ptrs)] = self.block_ptrs
        # zero out our inode's block pointers:
        self.block_ptrs = [0] * len(self.block_ptrs)
        # enter our new array as the 0th element of our inode
        self.block_ptrs[0] = new_b
        # cache it!
        fs.blockCache.put(new_b, bps)
        self.level = self.level + 1

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
        #print("pack: {}".format(self.block_ptrs))
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

        # unpack the block pointers in the INode structure
        off = INodeFormat.size
        self.block_ptrs = [0] * INode.BlockPtrsPerInode

        for i in range(INode.BlockPtrsPerInode):
            (self.block_ptrs[i],) = BlockPointerFormat.unpack_from(buffer, off)
            off += 4

    def unpackBlockPointers(self, buff, block_ptrs_per_block):
        ret = [0] * block_ptrs_per_block
        offset = 0
        for i in range(block_ptrs_per_block):
            (ret[i],) = BlockPointerFormat.unpack_from(buff, offset)
            offset += 4
        return ret

    def packBlockPointers(self, buff, blocks, block_ptrs_per_block):
        offset = 0
        for i in range (block_ptrs_per_block):
            BlockPointerFormat.pack_into(buff, offset, blocks[i])
            offset += 4

    # debugging function: traverse a tree of block pointers to see that gDAOB works
    def printBlocks(self, depth, blocks, fs):
        assert blocks != None
        for i in range(len(blocks)):
            block = blocks[i]
            if block > 0:
                if depth == 0:
                    print(block, end='')
                else:
                    print("  " * (self.level-depth), end='')
                    print(block)
                    inner = fs.readBlockCache(i, blocks, alloc_p = False)
                    self.printBlocks(depth-1, inner, fs)
        print("")

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
        # just checking our block pointers are the expected size:
        assert BlockPointerFormat.size == 4, "Block pointers aren't 32 bits!?"
        return INode._bytes_per_in
