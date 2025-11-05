![dspx_Screenshot_shaved](old/dspx_Screenshot_shaved.avif "screnshoot")
# DSPX
PySide6 Data Store Pruner & Compressor Linux Application

&nbsp;

## Features & Stuff

1. takes a list of dir paths as input
2. looks in given dir(s) for any OS residual files, recursively, and gives the choice to delete them individually or all at once.
3. does file deduplication in given dir(s), and gives the choice to delete them individually or all at once.
4. deletes any empty subdirs in given dir(s), and gives the choice to delete them individually or all at once.
5. write all operations to a log file where the program is run
6. uses AsyncIO and Blake3 for parallelized multithreaded hashing and pattern matching so it runs faster
7. pattern-matching is configurable, like a csv file, and these can be saved
8. CPU threads and RAM usage are configurable, and these settings can be saved
9. has installer which creates a virtual environment and installs all dependencies, and a launcher script with desktop icon

&nbsp;

## How It Work

1. Forget it, it's too complicated.
~~1. takes list of dirs and looks for any OS residual files, recursively, and lists them -- at which point you're given the choice to delete them.~~
~~2. gets file signatures (blake3) for all remaining files from the given dir(s)~~
~~3. finds and displays all files with same names that also have same blake3 signature (who are identical in other words) -- at which point you're given the choice to delete the duplicates.~~
~~4. finds and displays all other files, whether they have the same name or not, that have the same signatures -- at which point you're given the choice to delete the duplicates.~~
~~6. deletes any empty subdirs in given dir(s)~~
~~7. writes all operations to a log file where the program is run, showing everything that happened~~

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
- ---OPTIONAL--- compares files that are extremely similar but not identical, and displays them -- at which point you're given the choice to delete them, one at a time.
- use argparse instead of diarrhea

&nbsp;

## Requirements
- x86_64 linux 6+
- Arch or Ubuntu based distro
- python 3.12+
- modules:
  - PySide6>=6.5.0
  - blake3>=0.4.1

&nbsp;

## Nota Bene
- This has been, in large part, "vibe" coded.  Dear Lord.  I can write programs, I just don't like to.  ..But hey!  It works!

