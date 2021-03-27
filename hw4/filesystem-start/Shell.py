import sys
import readline
from FileSystem import FileSystem
import BlockDevice
from INode import INodeType

class Shell:
    """
    Simple Python shell / file system
    Basic readline integration gives us some cute features.
    """

def repl():
    prompt = '> '
    fs = None
    # saved_stdout = sys.stdout  # for I/O redirection
    while True:
        try:
            line = input(prompt)
        except EOFError:     # allow Ctrl-D to cleanly exit
            break

        words = line.split()

        if len(words) == 0:  # just pressing return gives you a new prompt
            pass

        # As 3: Don't need to handle I/O redirection, except as
        #       super-bonus extra credit. Requires some wizardry
        # mode = None
        # if '>' in words:
        #     mode = "wb"
        # if '>>' in words:
        #     mode = "ab"
        # if mode != None:
        #     sys.stdout = open(str(words[-1]), mode)

        elif words[0] in ('exit', 'quit'):
            break

        elif words[0] in ('newfs'):
            if len(words) < 2:
                print("usage: newfs <fs_name> [block count] [bytes per block]")
                continue
            bpb = BlockDevice.default_blocksize
            count = 200
            if len(words) > 2:
                count = int(words[2])
            if len(words) > 3:
                bpb = int(words[3])
            FileSystem.createFileSystem(words[1], block_count=count, block_size=bpb)

        elif words[0] in ('mount'):
            if len(words) != 2:
                print("usage: mount <fs_name>")
                continue
            fs = FileSystem.mount(words[1])

        elif words[0] in ('ls', 'dir'):
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            # TODO

        elif words[0] == 'cat':
            print("if argument is a file, print it, else report a nice error")

        elif words[0] == 'mkdir':
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            if len(words) != 2:
                print("usage: mkdir <dirname>")
                continue
            # TODO

        elif words[0] == 'unmount':
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            fs.unmount()
            fs = None

        elif words[0] == 'touch':
            if fs == None:   # todo: consider factoring out this check
                print("{} only works on mounted file systems".format(words[0]))
                continue
            if len(words) < 2:
                print("usage: touch <dirname> [dirname, ...]")
                continue
            for fname in words[1:]:
                pass
                # TODO - update "mdate" of each element

        elif words[0] == 'cd':
            print("cd implementation goes here")

        elif words[0] == 'echo':
            print("echo implementation goes here")

        elif words[0] == 'pwd':
            print("pwd implementation goes here")

        #
        # Temporary commands for troubleshooting the file system:
        #
        elif words[0] == 'blockmap':
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            as_str = fs.blockMapAsString()
            print(as_str)

        elif words[0] == 'inodemap':
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            as_str = fs.inodeMapAsString()
            print(as_str)

        elif words[0] == 'alloc_block':
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            bn = fs.allocBlock()
            if bn > 0:
                print("allocated {}".format(bn))
            else:
                print("disk full!")

        elif words[0] == 'find_block':
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            if len(words) != 3:
                print("usage: find_block <inode_num> <block_num>")
                continue
            num = int(words[1])
            block_no = int(words[2])
            inode = fs.inode_map[num]
            addr = inode.getDiskAddrOfBlock(fs, block_no, alloc_p = True)
            if addr > 0:
                print("block {} of inode {} is {}".format(block_no, num, addr))
            else:
                print("not found!")

        elif words[0] == 'print_tree':
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            if len(words) != 2:
                print("usage: print_tree <inode_num>")
                continue
            num = int(words[1])
            inode = fs.inode_map[num]
            inode.printBlocks(inode.level, inode.block_ptrs, fs)

        elif words[0] == 'free_block':
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            if len(words) != 2:
                print("usage: free_block <block_num>")
                continue
            fs.freeBlock(int(words[1]))

        elif words[0] == 'alloc_inode':
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            if len(words) != 2:
                print("usage: alloc_inode <1|2|3>")
                continue
            in_type = INodeType(int(words[1]))
            ret = fs.allocINode(in_type)
            if ret > 0:
                print("allocated {}".format(ret))
            else:
                print("out of inodes!")

        elif words[0] == 'free_inode':
            if fs == None:
                print("{} only works on mounted file systems".format(words[0]))
                continue
            if len(words) != 2:
                print("usage: free_inode <inode_num>")
                continue
            fs.freeINode(int(words[1]))

        else:
            print("unknown command {}".format(words[0]))

        # As 3: Don't need to handle redirect - tricky to integrate with Python stdout
        # sys.stdout.flush()
        # if sys.stdout != saved_stdout:
        #     sys.stdout.close()
        #     sys.stdout = saved_stdout

    # all done, clean exit, save history
    print("bye!")
    readline.write_history_file(histfile)

assert sys.version_info >= (3,0), "This program requires Python 3"

histfile = ".shell-history"

if __name__ == '__main__':
    try:
        readline.read_history_file(histfile)
    except FileNotFoundError:
        open(histfile, 'wb').close()

    repl()
