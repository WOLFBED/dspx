# DSPX
data store pruner and compressor

&nbsp;

## Current Features & Stuff

1. takes a dir path as input
2. looks in given dir for any OS residual files, recursively, and lists them -- at which point you're given the choice to delete them.
3. does file deduplication in given dir
4. deletes any empty subdirs in given dir
5. write all operations to a log file where the program is run

&nbsp;

## TODO List

- [x] fix current methods to not break-out in Traceback errors when any kind of problem arises :: *(posted jul 21 2025)*
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
- fdupes - see [this page](https://github.com/adrianlopezroche/fdupes) for more info.  This is what I use for deduplication.  If not installed on your system dspx will suggest a means of rectification, like a command to run.
- modules:
  - rich
  - ???
