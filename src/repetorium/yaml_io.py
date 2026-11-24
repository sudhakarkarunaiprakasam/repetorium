"""Safe YAML loading with LibYAML acceleration when available."""

import yaml

_SAFE_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_SAFE_DUMPER = getattr(yaml, "CSafeDumper", yaml.SafeDumper)


def safe_load(stream):
    return yaml.load(stream, Loader=_SAFE_LOADER)


def safe_dump(data, **kwargs) -> str:
    return yaml.dump(data, Dumper=_SAFE_DUMPER, **kwargs)
