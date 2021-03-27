import sys
import os
import fileinput

class Shell:
    """ Simple Python shell """

def repl():
    prompt = '> '
    cmd = ''
    sys.stdout.write(prompt)
    sys.stdout.flush()
    for line in sys.stdin:
        words = line.split()
        if len(words) == 0:
            pass
        elif words[0] in ('exit', 'quit'):
            break
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
