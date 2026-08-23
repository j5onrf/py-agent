# File: ~/session-test/simulation.py
# Description: Runner file for testing velocity metrics
from physics import calculate_velocity


def run_test():
    speed = calculate_velocity(100, 5)
    print(f"Speed: {speed}")
