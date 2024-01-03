import os
import uuid
import time
import glob
import random

next_get = time.time()
def put(contents, dir_name):
    os.makedirs(dir_name, exist_ok=True)
    path = f"{dir_name}/{time.time()}.{str(uuid.uuid4())}"
    temp_path = f"{path}.tmp"
    final_path = f"{path}.item"
    
    try:
        with open(temp_path, 'w') as file:
            file.write(contents)
            file.flush()
            os.fsync(file.fileno())
        os.rename(temp_path, final_path)
    finally:
        try:
            os.remove(temp_path)
        except (IOError, OSError):
            pass

def get(dir_name):
    global next_get
    if next_get > time.time():
        return None
    os.makedirs(dir_name, exist_ok=True)

    files = list(filter(os.path.isfile, glob.glob(dir_name + "/*.item")))
    files.sort(key=lambda x: os.path.getmtime(x))
    if not files:
        return None
    file = files[0]
    with open(file, "r") as f:
        contents = f.read()
    os.remove(file)
    next_get = time.time()+random.randint(1,3)
    return contents


if __name__ == "__main__":
    for i in range(10):
        put(f"lol {i}".encode(), "foo")

    for i in range(10):
        print(get("foo"))

