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
            # show current directory's contents,
            # or show contents of given directories
            if len(words) == 1:
                for f in os.listdir():
                    print(f)
            else:
                for arg in words[1:]:
                    if len(words) > 2:
                        print(arg+":")
                    try:
                        for f in os.listdir(arg):
                            print(f)
                        print()
                    except FileNotFoundError:
                        if words[0] == 'ls':
                            cmd = "ls: "
                        else:
                            cmd = "dir: "
                        print(cmd+arg+": No such file")
        elif words[0] == 'cat':
            # if argument is a file, print it, else report a nice error
            if len(words) > 2:
                if os.path.isfile(words[1]):
                    with open(words[1],"r") as f:
                        f.seek(0)
                        for line in f.readlines():
                            print(line)
                else:
                    print("cat: "+words[1]+": No such file")
        elif words[0] == 'mkdir':
            # create an empty directory
            if len(words) > 1:
                try:
                    os.mkdir(os.getcwd()+"/"+words[1])
                except FileExistsError:
                    print("mkdir: "+words[1]+": File exists")
        elif words[0] == 'touch':
            # Creates a file if it doesn't already exist
            # If it does (and it's not empty), reports that a file with the given name already exists
            if len(words) > 1:
                with open(words[1],"a+") as f:
                    f.seek(0)
                    if f.read(1):
                        print("touch: "+words[1]+": File exists")
        elif words[0] == 'cd':
            # change directory
            if len(words) > 1:
                try:
                    os.chdir(os.getcwd()+"/"+words[1])
                except FileNotFoundError:
                    print("cd: "+words[1]+": No such file or directory")
            else:
                # No argument given, go to home directory
                os.chdir(os.path.expanduser("~"))
        elif words[0] == 'echo':
            print(" ".join(words[1:]))
        elif words[0] == 'pwd':
            print(os.getcwd())
        else:
            print("unknown command {}".format(words[0]))

        sys.stdout.write(prompt)
        sys.stdout.flush()

    # all done, clean exit
    print("bye!")

assert sys.version_info >= (3,0), "This program requires Python 3"

if __name__ == '__main__':
    repl()
