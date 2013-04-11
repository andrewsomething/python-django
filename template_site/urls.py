import glob
from os.path import abspath, dirname, join

PROJECT_DIR = abspath(dirname(__file__))

urlfiles = glob.glob(join(PROJECT_DIR, 'urls', '*.py'))
urlfiles.sort()

for f in urlfiles:
    execfile(abspath(f))
