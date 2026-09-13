import os

def list_files(directory="."):
    for root, dirs, files in os.walk(directory):
        for f in files:
            print(os.path.join(root, f))

if __name__ == "__main__":
    list_files(".")