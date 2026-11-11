"""Hace importables los módulos de bender/ (son hermanos de pruebas/) desde pytest."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
