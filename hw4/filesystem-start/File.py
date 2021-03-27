import FileSystem
from enum import Enum
from INode import *

class FileSeek(Enum):
    BEGINNING = 0
    CURRENT   = 1
    END       = 2

def inode_to_object(filesystem, inode:INode, parent, mode="r"):
    """ takes an INode - if it's a file, creates a File
        object, if it's a directory, creates a directory object.
        todo: support symlinks
    """
    if inode.flags == INodeType.FILE:
        return File(filesystem, parent, inode, mode)
    if inode.flags == INodeType.DIRECTORY:
        return Directory(filesystem, parent, mode, inode)
    print("unknown inode type in inode_to_object")
    return None

class File(object):
    """ A File is a wrapper for an iNode that provides arbitrary-
        length / non-aligned reads, and keeps track of the current
        read (/write) offset.
    """
    def __init__(self, fs, parent: INode, my_inode, mode, offset=0):
        self.inode  = my_inode
        self.offset = offset
        self.parent = parent
        self.fs     = fs
        self.mode   = mode

    def read(self, buff):
        num_read = self.inode.read(self.offset, buff)
        self.offset += num_read
        return num_read

    def write(self, buff):
        if self.mode != "r":
            if self.mode == "a":
                self.offset = self.inode.length
            self.inode.write(self.offset, buff)
            self.offset += len(buff)
        else:
            print("permission denied")

    def seek(self, pos, from_what = FileSeek.BEGINNING):
        # if we didn't have from_what, it would just be:
        # self.offset = pos
        pass

    def sync(self):
        pass

    # truncate (or extend) the file length
    def truncate(self, len):
        self.inode.truncate(len)

class Directory(File):
    """ A Directory is a File that contains a mapping from
        file names to iNode numbers.
    """

    def __init__(self, fs, parent: INode, mode, my_inode: INode = 0):
        super(Directory, self).__init__(fs, parent, my_inode, mode)  # invoke File initializer
        self.children = None    # why not: = {".": self, "..": parent} ?
                                # hint: what is the state diagram of a
                                # directory.

    def add_child(self, child_name, child_inode:INode):
        # note: new children inherit permission of parent (so...write or append)
        child = None
        if child_inode == None:
            assert False, "missing iNode in add_child"
        elif child_inode.flags == INodeType.FILE:
            child = File(self.fs, self.inode, child_inode, self.mode)
        elif child_inode.flags == INodeType.DIRECTORY:
            child = Directory(self.fs, self.inode, self.mode, child_inode)
        else:
            assert False, "unknown inode type in add_child: {}".format(child_inode.type)
        # todo: what are the conditions where we need to check this?
        # do we have any invariants wrt. directories being cached?
        self.ensure_cached()
        self.children[child_name] = child
        self.fs.dirCache.append(self)

    def get_children(self):
        self.ensure_cached()
        return self.children

    def to_str(self):
        """ Create a linearization of the Directory dictionary, usually
            in preparation for writing it to disk.
            Note: we're careful here to linearize into a string, which is
            (/should be?) UTF-8, so filenames can have fancy characters.
            We translate those into byte arrays before writing to disk in flush.
        """
        strbuf = ''
        for key in self.children.keys():
            kid = self.children[key]
            # print("dir sync key:{}->{}".format(key, str(kid)))
            strbuf = strbuf + "\n{}|{}".format(key, self.children[key].inode.inode_num)
        # print(strbuf)
        return strbuf

    def flush(self):
        """ Write this directory out to its iNode
        """
        strbuf = self.to_str()
        byte_buff = bytearray(strbuf, "utf-8")
        self.inode.write(0, byte_buff)
        # print("syncing dir, {} bytes".format(str(len(byte_buff))))

    def ensure_cached(self):
        if self.children == None:
            self.read()

    def read(self):
        """ Read the directory from its iNode's contents """
        # print("fetching dir, {} bytes".format(str(self.inode.num_bytes)))
        buff = bytearray(self.inode.length)
        self.inode.read(0, buff) # read the whole file
        dir_as_string = buff.decode("utf-8")
        child_pipe_inode = dir_as_string.split("\n")
        self.children = {}
        # print("unmarshalling directory {}".format(dir_as_string))
        for child in child_pipe_inode:
            if len(child) == 0: continue
            # print("unmarshaling {} ({})".format(child, len(child)))
            entry = child.split("|")
            child_obj = inode_to_object(self.fs, self.fs.inode_map[int(entry[1])], self, self.mode)
            self.children[entry[0]] = child_obj

    def sync(self):
        self.flush()

# TODO: add unit tests here. :)
contents = bytearray(b'Lorem ipsum dolores umbridge yeah idr the rest of the latin placeholder thing')

def test_inode_rw():
    FileSystem.FileSystem.createFileSystem("nose_fs", block_count=200, block_size=1024)
    fs = FileSystem.FileSystem.mount("nose_fs")

    root = inode_to_object(fs, fs.inode_map[fs.root_dir_inode], None)
    f_index = fs.allocINode(INodeType.FILE)
    root.add_child("untitled", fs.inode_map[f_index])
    fs.unmount()

    fs = FileSystem.FileSystem.mount("nose_fs")
    print("writing...")
    untitled = fs.open("/untitled", "w")
    untitled.write(contents)
    assert untitled.inode.length == len(contents)
    fs.unmount()

    fs = FileSystem.FileSystem.mount("nose_fs")
    print("reading...")
    untitled = fs.open("/untitled", "r")
    read_buff = bytearray(len(contents))
    r = untitled.read(read_buff)
    print(read_buff, contents)
    assert read_buff == contents
    fs.unmount()

def test_namei():
    fs = FileSystem.FileSystem.mount("nose_fs")
    print("namei")
    read_buff = bytearray(len(contents))
    i_untitled = fs.namei("/untitled")
    i_untitled.read(0, read_buff)
    assert read_buff == contents
    # assert 1 == 0
    fs.unmount()