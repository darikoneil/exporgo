from pathlib import Path
from exporgo.experiment import Experiment
from exporgo.files import FileTree
from exporgo.pipeline import Pipeline
from exporgo.types import Priority, Status


# Params
name = "Beanstalk"
base = Path(R'C:\Users\Yuste\Desktop\Jack')
keys = ("Fairy", "Tale")
file_sets = ["results", "figures"]
priority = Priority.CRITICAL

# make path
base.mkdir(exist_ok=True)
base.joinpath(name).mkdir(exist_ok=True)

# Factory things
file_tree = FileTree(base.joinpath(name), file_sets, index=True)
pipeline = Pipeline(print, priority, Status.SOURCE)

# Create the experiment
experiment = Experiment(name, base, keys, file_tree, pipeline, priority)
