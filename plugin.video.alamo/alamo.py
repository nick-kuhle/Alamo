# -*- coding: utf-8 -*-
"""The Alamo - plugin entry point."""
import sys

from resources.lib import router

if __name__ == '__main__':
    router.dispatch(sys.argv)
