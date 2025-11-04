![dspx_Screenshot_shaved](dspx_Screenshot_shaved.avif "screnshoot")
# DSPX
data store pruner and compressor

&nbsp;

## Desired Features & Stuff

1. takes a list of dir paths as input
2. looks in given dir(s) for any OS residual files, recursively, and lists them -- at which point you're given the choice to delete them.
3. does file deduplication in given dir(s)
4. deletes any empty subdirs in given dir(s)
5. write all operations to a log file where the program is run

&nbsp;

## How It Work

1. takes list of dirs and looks for any OS residual files, recursively, and lists them -- at which point you're given the choice to delete them.
2. gets file signatures for all remaining files
3. finds and displays all files with same names that also have same signature (who are identical in other words) -- at which point you're given the choice to delete the duplicates.
4. finds and displays all other files, whether they have the same name or not, that have the same signatures -- at which point you're given the choice to delete the duplicates.
5. ---OPTIONAL--- compares files that are extremely similar but not identical, and displays them -- at which point you're given the choice to delete them, one at a time.
6. deletes any empty subdirs in given dir(s)
7. writes all operations to a log file where the program is run, showing everything that happened


&nbsp;

## TODO List

- ~~[ ] logging() is missing from newly added: FastFileDeleter class, and get_dir_size() method (and related methods) :: *(posted jul 23 2025)*~~
- ~~[ ] Need to keep track of before/after sizes to offer comparison at the end :: *(posted jul 23 2025)*~~
- ~~[x] fix current methods to not break-out in Traceback errors when any kind of problem arises :: *(posted jul 21 2025)*~~
- [ ] Get a life. 

&nbsp;

## Future Features
- option to compress all:
  - audio files to opus
  - image files to avif or jxl
  - video files to av1/opus
- analyze task throughput and approximate a completion time, i.e. "should be done in x time"
- use argparse instead of diarrhea

&nbsp;

## Requirements
- x86_64 linux 6+
- python 3.12+
- ~~fdupes - see [this page](https://github.com/adrianlopezroche/fdupes) for more info.  This is what I use for deduplication.  If not installed on your system dspx will suggest a means of rectification, like a command to run.~~ -- going to make my own deduplicator
- modules:
  - rich
  - ???
