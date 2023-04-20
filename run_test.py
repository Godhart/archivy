import sys
from tests.test_render import *

if __name__ == "__main__":
    if len(sys.argv) > 1:
        output_path = None
        if len(sys.argv) > 2:
            output_path = sys.argv[2]
        test = sys.argv[1]
        if test in tests:
            tests[test](output_path)
        else:
            raise ValueError(f"Test '{test}' is not found!")
