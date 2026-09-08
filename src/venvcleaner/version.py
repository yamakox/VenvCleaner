from importlib.metadata import version, metadata

# MARK: package version
_package_name = metadata(__package__).get('Name')  # type: ignore
version_number = version(_package_name)
