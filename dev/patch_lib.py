import re
import docker.utils.config

# We run our tests with `python -X warn_default_encoding`, this script patches
# an instance of an `open` in the docker library that makes our tests fail.

with open(docker.utils.config.__file__, 'r', encoding='UTF-8') as fh:
    i = fh.read()
o = re.sub(
    r'''^(\s+)with open\(config_file\) as f:\s*$''',
    r'''\1with open(config_file, 'rb') as f:''',
    i, flags=re.M )
with open(docker.utils.config.__file__, 'w', encoding='UTF-8') as fh:
    fh.write(o)
if i!=o:
    print(f"Patched {docker.utils.config.__file__}")
