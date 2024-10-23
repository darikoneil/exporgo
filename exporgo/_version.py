from importlib_metadata import metadata as _metadata


_meta = _metadata("exporgo")


#: str: The name of the package.
__package_name__ = _meta["name"]

#: str: The version of the package.
__current_version__ = _meta["version"]
