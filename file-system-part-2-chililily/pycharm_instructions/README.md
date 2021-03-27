# Getting started with PyCharm

You've already checked out the repository (because you're reading
this).

In PyCharm, select "New Project".

Under "Location", select the path to the directory where you checked
out this repository.  In my case, I checked it out in my
PycharmProjects folder, so the Location: was
/Users/dylan/PycharmProjects/filesystem-start

It will say "The directory...is not empty. Would you like to create a
project from existing sources instead?" Click Yes.

In the bar at the top of the window, there's a pulldown next to a
triangle (run) and a bug (debug). Click that pulldown to create new
"configurations", which is how you run code in Pycharm.

Start by creating a Nosetests configuration:

 * Click the + in the upper left part of the window,
 * select Python Tests >> Nosetests,
 * give your configuration a name at the top of the window, like "nosetests"
 * near the middle of the screen, click the pulldown next to Python interpreter: and choose a Python 3 version
   * if there isn't anything to select, go to the Pycharm >> Preferences menu, 
   * click on Project >> Project Interpreter,
   * click on the Gear to the right of Project Interpreter: selection,
   * select Add Local and follow the instructions there.
 * leave the Target selected at Path (the default),
 * click the ... next to the path selector under that,
 * select the FileSystem.py in the folder of your project
 * choose your project folder again in the Working directory:
 * both "Add content roots..." and "Add source roots" should be checked
 * click "OK"

Nosetests should now be the selected item in the pulldown next to
the "Run" triangle. Click the triangle, and you'll hopefully see the
nosetests output in the console that pops up at the bottom of the
screen.

Adding a configuration for running your code is almost identical,
except you'd select "Python" instead of "Python Tests >> Nosetests" as
the type, and then Shell.py as the Target. Everything else should be
the same.

If Pycharm doesn't recognize your classes, in the files view on the
left of the Project, right-click on the "filesystem-start" folder and
select Mark Directory As >> Sources Root.
