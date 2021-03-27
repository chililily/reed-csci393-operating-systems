import FileSystem
from enum import Enum
from INode import *

class FileSeek(Enum):
    BEGINNING = 0
    CURRENT   = 1
    END       = 2

def inode_to_object(filesystem, inode:INode, parent):
    """ takes an INode - if it's a file, creates a File
        object, if it's a directory, creates a directory object.
        todo: support symlinks
    """
    if inode.flags == INodeType.FILE:
        return File(inode, parent)
    if inode.flags == INodeType.DIRECTORY:
        return Directory(inode, parent)
    print("unknown inode type in inode_to_object")
    return None

class File(object):
    """ A File is a wrapper for an iNode that provides arbitrary-
        length / non-aligned reads, and keeps track of the current
        read (/write) offset.
    """
    def __init__(self, my_inode, parent:INode, offset=0):
        self.inode = my_inode
        self.offset = offset
        self.parent = parent

    def read(self, buff):
        num_read = self.inode.read(self.offset, buff)
        self.offset += num_read
        return num_read

    def write(self, buff):
        self.inode.write(self.offset, buff)
        self.offset += len(buff)

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

    def __init__(self, my_inode:INode, parent:INode):
        super(Directory, self).__init__(my_inode, parent) # invoke File initializer
        self.children = None    # why not: = {".": self, "..": parent} ?
                                # hint: what is the state diagram of a
                                # directory.

    def add_child(self, child_name, child_inode:INode):
        child = None
        if child_inode == None:
            assert False, "missing iNode in add_child"
        elif child_inode.type == INodeType.FILE:
            child = File(child_inode, self)
        elif child_inode.type == INodeType.DIRECTORY:
            child = Directory(child_inode, self)
        else:
            assert False, "unknown inode type in add_child: {}".format(child_inode.type)
        # todo: what are the conditions where we need to check this?
        # do we have any invariants wrt. directories being cached?
        self.ensure_cached()
        self.children[child_name] = child

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
            strbuf = strbuf + "\n{}|{}".format(key, self.children[key].inode.number)
        # print(strbuf)
        return strbuf

    def flush(self):
        """ Write this directory out to its iNode
        """
        strbuf = self.to_str()
        byte_buff = bytearray(strbuf, "utf-8")
        self.inode.write(byte_buff, 0)
        # print("syncing dir, {} bytes".format(str(len(byte_buff))))

    def ensure_cached(self):
        if self.children == None:
            self.read()

    def read(self):
        """ Read the directory from its iNode's contents """
        # print("fetching dir, {} bytes".format(str(self.inode.num_bytes)))
        buff = bytearray(self.inode.num_bytes)
        self.inode.read(buff, 0) # read the whole file
        dir_as_string = buff.decode("utf-8")
        child_pipe_inode = dir_as_string.split("\n")
        self.children = {}
        # print("unmarshalling directory {}".format(dir_as_string))
        for child in child_pipe_inode:
            if len(child) == 0: continue
            # print("unmarshaling {} ({})".format(child, len(child)))
            entry = child.split("|")
            child_obj = inode_to_object(self.inode.filesystem, int(entry[1]), self)
            self.children[entry[0]] = child_obj

    def sync(self):
        self.flush()

# TODO: add unit tests here. :)