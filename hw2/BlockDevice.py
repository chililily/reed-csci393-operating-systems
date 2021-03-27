import os

default_blocksize = 1024
class BlockDevice:
    """ The BlockDevice is the API that a file system is built on.
        Any block device supports block-level reads and writes.
        In this system, we simulate a block device using an OS file.
        In theory (an exercise for the motivated?) we could use almost
        this exact code to access an actual raw device (e.g.,
        /dev/rdiskx), but then the program would need to run as
        super-user, and if the wrong device were specified, you could
        overwrite your OS or user data. Beware.
    """

    """ 
        Device files have a name, and end in .dev
        I wanted to bake in to the device filename a notion of the 
        blocksize, because it matters. So, there's a default blocksize
        (1024 bytes). If a device filename has no number in the name,
        that's the assumed block size. If it does have a number in the name,
        that number specifies the block size.
    """

    """ Attributes:
        self.num_blocks
        self.blocksize
        self.filename
        self.handle --- opened file
    """
    @staticmethod
    def normalize_filename(filename, blocksize=default_blocksize):
        """
        Create a well-structured device filename
        :param filename: either a full filename (mydev.1024.dev) or just
                the descriptive part (mydev)
        :param blocksize: default 1024, or your own blocksize
        :return: a string with the full devicefile name (e.g., mydev.1024.dev)
        """
        filename_parts = filename.split(".")
        if len(filename_parts) == 1:
            filename_parts.append("dev")
        if not blocksize == default_blocksize:
            if not filename_parts[1].isdecimal() or (not
                    int(filename_parts[1]) == blocksize):
                filename_parts.insert(1,str(blocksize))
        return str(".".join(filename_parts))

    @staticmethod
    def filename_to_blocksize(filename):
        """
        Extract the block size from a device filename
        :param   filename: the device file's filename
        :return: the blocksize, extracted from the filename, or default
        """
        f_parts=filename.split(".")
        if len(f_parts) == 1 or not f_parts[1].isdecimal():
            return default_blocksize
        return int(f_parts[1])

    def __init__(self, filename="blocks.1024.dev", blockCount=-1,
            blocksize=default_blocksize, create=False):
        """
            Create a new BlockDevice from a given filename. Used for
            creating a new one as well as opening an existing one.
        :param filename:   the device filename
        :param blockCount: how big the device should be, in blocks
        :param blocksize:  how big each block should be
        :param create:     whether to create the file or just open it
        """

        self.filename = filename
        if create:
            if blockCount <= 0:
                print("invalid device size: {}".format(blockCount))
                return
            self.num_blocks = blockCount
            self.blocksize = blocksize
            self.filename = BlockDevice.normalize_filename(filename, blocksize)
            print('creating {} with {} blocks'.format(self.filename,
                blockCount))
            self.handle = open(self.filename, 'wb+', buffering=0)
            self.handle.seek((blocksize * blockCount) - 1)
            outb = bytearray(b'0')
            num_written = self.handle.write(outb)
        else:
            self.filename = BlockDevice.normalize_filename(filename, blocksize)
            self.blocksize = BlockDevice.filename_to_blocksize(self.filename)
            info = os.stat(self.filename)
            self.num_blocks = int(info.st_size / self.blocksize)
            self.handle = open(self.filename, 'rb+', buffering=0)

    def close(self):
        """ Close the underlying file in preparation for shutdown """
        self.handle.flush()  # sync any buffers to disk
        self.handle.close()

    def read_block(self, block_num, buff):
        """
        Half of the action of a block device: read a block
        :param block_num: which block to read
        :param buff:      bytearray to read the data in to, assumed to be blocksize long
        """
        assert block_num < self.num_blocks, "read_block past end of device"
        assert len(buff) == self.blocksize, "bad buff size to read_block"
        self.handle.seek(block_num * self.blocksize)
        num_read = self.handle.readinto(buff)
        assert num_read == self.blocksize, "ERROR: read_block buffer / file not block aligned"

    def write_block(self, block_num, buff, pad=False):
        """
        Other half of the action end of a block device: write a block
        :param block_num: which block to write
        :param buff:      bytearray holding data to write, assumed to be blocksize long
        :param pad:       if this is true, add null bytes to pad input up to blocksize
        """
        assert block_num < self.num_blocks, "write_block past end of device"

        if pad and (len(buff) < self.blocksize):
            pad_len = self.blocksize - len(buff)
            buff.extend(pad_len*b'\x00')
            # print("padded buffer to {}".format(len(buff)))

        assert len(buff) == self.blocksize, "bad buff size to write_block"
        # todo: keep track of the file handle's seek location, and only seek when needed
        self.handle.seek(block_num * self.blocksize)
        num_written = self.handle.write(buff)
        assert num_written == self.blocksize, (
                "ERROR: write_block buffer / file not block aligned {}".format(num_written))

    def blocks_to_bytes(self, blocknum):
        return blocknum * self.blocksize

# Nosetests
def test_create_device():
    bc = 100
    bs = 2048
    bd = BlockDevice('block.dev', bc, create=True, blocksize=bs)
    bd.close()
    info = os.stat(bd.filename)  # exception is reported as test failure
    assert info.st_size == bc * bs, "create device bad file size"

def test_write_read_block():
    bd = BlockDevice('block.dev', 2, create=True)
    buff = bytearray(bd.blocksize)
    for i in range(bd.blocksize):
        buff[i] = i % 256
    bd.write_block(1, buff)
    bd.close()
    bd = BlockDevice('block.dev')
    buff = bytearray(bd.blocksize)
    bd.read_block(1, buff)
    for i in range(bd.blocksize):
        assert buff[i] == i % 256, "data mismatch in test_write_read_block"

