import os
import pathlib
import shutil
from os import remove

project_dir = os.getcwd()

<% if not model_names %>
remove(os.path.join(project_dir, "forms.py"))
<% endif %>

def _check_before_remove(path):
    if not pathlib.Path(path).is_relative_to(project_dir):
        raise Exception(f"Trying to remove a file that isn't in the project directory: {path} not in {project_dir}")


# see https://github.com/audreyr/cookiecutter/issues/723 for more on this approach
def remove(filepath):
    _check_before_remove(filepath)

    if os.path.isfile(filepath):
        os.remove(filepath)
    elif os.path.isdir(filepath):
        shutil.rmtree(filepath)
