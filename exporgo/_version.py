from importlib_metadata import metadata as _metadata


_meta = _metadata("exporgo")


#: str: The name of the package.
name = _meta["name"]

#: str: The version of the package.
version = _meta["version"]
