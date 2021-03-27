import sys
import os
import fileinput
from FileSystem import *

class Shell:
    """ Simple Python shell """

def repl():
    prompt = '> '
    cmd = ''
    sys.stdout.write(prompt)
    sys.stdout.flush()
    file_systems = {}       # dict of FS names and block sizes
    for line in sys.stdin:
        words = line.split()
        
        if len(words) == 0:
            pass
        elif words[0] in ('exit', 'quit'):
            break


        # File system manipulation/stuff
        elif words[0] == 'newfs':
            if len(words) < 3 or len(words) > 4:
                print("newfs: expected 2-3 arguments")
            else:
                if len(words) == 4:
                    filename = FileSystem.createFileSystem(words[1],int(words[2]),int(words[3])).filename
                else:
                    filename = FileSystem.createFileSystem(words[1],int(words[2])).filename
                parts = filename.split(".")
                file_systems[parts[0]] = filename
        
        elif words[0] == 'mount':
            if len(words) != 2:
                print("mount: expected 1 argument")
            else:
                try:
                    filename = file_systems[words[1]]
                    fs,status = FileSystem.mount(filename)
                    if not status:
                        print("warning: contents of file system may be out of sync")
                except KeyError:
                    print("mount: file system not found")
        
        elif words[0] == 'blockmap':
            try:
                if fs.bd != None:
                    print(fs.bmap.rep())
            except NameError:
                print("blockmap: no device mounted")
        
        elif words[0] == 'alloc_block':
            try:
                if fs.bd != None:
                    r = fs.bmap.alloc_block()
                    if r != -1:
                        print(r)
                    else:
                        print("alloc_block: no blocks free")
            except NameError:
                print("alloc_block: no device mounted")
        
        elif words[0] == 'free_block':
            if len(words) != 2:
                    print("free_block: expected 1 argument")
            try:
                if fs.bd != None:
                    fs.bmap.free_block(int(words[1]))
            except NameError:
                print("free_block: no device mounted")
        
        elif words[0] == 'inode_map':
            try:
                if fs.bd != None:
                    print(fs.imap.rep())
            except NameError:
                print("inode_map: no device mounted")
        
        elif words[0] == 'alloc_inode':
            if len(words) != 2:
                    print("alloc_inode: expected 1 argument")
            try:
                if fs.bd != None:
                    r = fs.imap.alloc_inode(words[1])
                    if r != -1:
                        print(r)
                    else:
                        print("alloc_inode: could not complete operation -- argument must be one of f, s, or d")
            except NameError:
                print("alloc_inode: no device mounted")
        
        elif words[0] == 'free_inode':
            if len(words) != 2:
                    print("free_inode: expected 1 argument")
            try: 
                if fs.bd != None:
                    fs.imap.free_inode(int(words[1]))
            except NameError:
                print("free_inode: no device mounted")
        
        elif words[0] == 'unmount':
            try:
                fs.unmount()
            except NameError:
                print("unmount: no device mounted")


        # File traversal/manipulation
        elif words[0] in ('ls', 'dir'):
            print("show current directory's contents")
        elif words[0] == 'cat':
            print("if argument is a file, print it, else report a nice error")
        elif words[0] == 'mkdir':
            print("create an empty directory goes here")
        elif words[0] == 'touch':
            print("create an empty file goes here")
        elif words[0] == 'cd':
            print("cd implementation goes here")
        elif words[0] == 'echo':
            print("echo implementation goes here")
        elif words[0] == 'pwd':
            print("pwd implementation goes here")


        else:
            print("unknown command {}".format(words[0]))

        sys.stdout.write(prompt)
        sys.stdout.flush()

    # all done, clean exit
    print("bye!")

assert sys.version_info >= (3,0), "This program requires Python 3"

if __name__ == '__main__':
    repl()