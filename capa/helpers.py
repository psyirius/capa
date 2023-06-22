# Copyright (C) 2020 Mandiant, Inc. All Rights Reserved.
# Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
# You may obtain a copy of the License at: [package root]/LICENSE.txt
# Unless required by applicable law or agreed to in writing, software distributed under the License
#  is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.
import os
import inspect
import logging
import contextlib
from typing import NoReturn

import tqdm

from capa.exceptions import UnsupportedFormatError
from capa.features.common import FORMAT_PE, FORMAT_SC32, FORMAT_SC64, FORMAT_CAPE, FORMAT_DOTNET, FORMAT_UNKNOWN, Format

EXTENSIONS_SHELLCODE_32 = ("sc32", "raw32")
EXTENSIONS_SHELLCODE_64 = ("sc64", "raw64")
EXTENSIONS_CAPE = ("json", "json_")
EXTENSIONS_ELF = "elf_"

logger = logging.getLogger("capa")


def hex(n: int) -> str:
    """render the given number using upper case hex, like: 0x123ABC"""
    if n < 0:
        return f"-0x{(-n):X}"
    else:
        return f"0x{(n):X}"


def get_file_taste(sample_path: str) -> bytes:
    if not os.path.exists(sample_path):
        raise IOError(f"sample path {sample_path} does not exist or cannot be accessed")
    with open(sample_path, "rb") as f:
        taste = f.read(8)
    return taste


def is_runtime_ida():
    try:
        import idc
    except ImportError:
        return False
    else:
        return True


def assert_never(value) -> NoReturn:
    assert False, f"Unhandled value: {value} ({type(value).__name__})"


def get_format_from_extension(sample: str) -> str:
    if sample.endswith(EXTENSIONS_SHELLCODE_32):
        return FORMAT_SC32
    elif sample.endswith(EXTENSIONS_SHELLCODE_64):
        return FORMAT_SC64
    elif sample.endswith(EXTENSIONS_CAPE):
        # once we have support for more sandboxes that use json-formatted reports,
        # we update this logic to ask the user to explicity specify the format
        return FORMAT_CAPE
    return FORMAT_UNKNOWN


def get_auto_format(path: str) -> str:
    format_ = get_format(path)
    if format_ == FORMAT_UNKNOWN:
        format_ = get_format_from_extension(path)
    if format_ == FORMAT_UNKNOWN:
        raise UnsupportedFormatError()
    return format_


def get_format(sample: str) -> str:
    # imported locally to avoid import cycle
    from capa.features.extractors.common import extract_format
    from capa.features.extractors.dnfile_ import DnfileFeatureExtractor

    with open(sample, "rb") as f:
        buf = f.read()

    for feature, _ in extract_format(buf):
        if feature == Format(FORMAT_PE):
            dnfile_extractor = DnfileFeatureExtractor(sample)
            if dnfile_extractor.is_dotnet_file():
                feature = Format(FORMAT_DOTNET)

        assert isinstance(feature.value, str)
        return feature.value

    return FORMAT_UNKNOWN


@contextlib.contextmanager
def redirecting_print_to_tqdm(disable_progress):
    """
    tqdm (progress bar) expects to have fairly tight control over console output.
    so calls to `print()` will break the progress bar and make things look bad.
    so, this context manager temporarily replaces the `print` implementation
    with one that is compatible with tqdm.
    via: https://stackoverflow.com/a/42424890/87207
    """
    old_print = print

    def new_print(*args, **kwargs):
        # If tqdm.tqdm.write raises error, use builtin print
        if disable_progress:
            old_print(*args, **kwargs)
        else:
            try:
                tqdm.tqdm.write(*args, **kwargs)
            except:
                old_print(*args, **kwargs)

    try:
        # Globally replace print with new_print.
        # Verified this works manually on Python 3.11:
        #     >>> import inspect
        #     >>> inspect.builtins
        #     <module 'builtins' (built-in)>
        inspect.builtins.print = new_print  # type: ignore
        yield
    finally:
        inspect.builtins.print = old_print  # type: ignore


def log_unsupported_format_error():
    logger.error("-" * 80)
    logger.error(" Input file does not appear to be a PE or ELF file.")
    logger.error(" ")
    logger.error(
        " capa currently only supports analyzing PE and ELF files (or shellcode, when using --format sc32|sc64)."
    )
    logger.error(" If you don't know the input file type, you can try using the `file` utility to guess it.")
    logger.error("-" * 80)


def log_unsupported_os_error():
    logger.error("-" * 80)
    logger.error(" Input file does not appear to target a supported OS.")
    logger.error(" ")
    logger.error(
        " capa currently only supports analyzing executables for some operating systems (including Windows and Linux)."
    )
    logger.error("-" * 80)


def log_unsupported_arch_error():
    logger.error("-" * 80)
    logger.error(" Input file does not appear to target a supported architecture.")
    logger.error(" ")
    logger.error(" capa currently only supports analyzing x86 (32- and 64-bit).")
    logger.error("-" * 80)


def log_unsupported_runtime_error():
    logger.error("-" * 80)
    logger.error(" Unsupported runtime or Python interpreter.")
    logger.error(" ")
    logger.error(" capa supports running under Python 3.7 and higher.")
    logger.error(" ")
    logger.error(
        " If you're seeing this message on the command line, please ensure you're running a supported Python version."
    )
    logger.error("-" * 80)
