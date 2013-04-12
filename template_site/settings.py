import glob
from os.path import abspath, dirname, join

PROJECT_DIR = abspath(dirname(__file__))

conffiles = glob.glob(join(PROJECT_DIR, 'settings', '*.py'))
conffiles.sort()

for f in conffiles:
    execfile(abspath(f))
