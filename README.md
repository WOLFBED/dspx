![img/dspx_Screenshot_shaved](img/dspx_Screenshot_shaved.avif "screnshoot")
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

## How It Work ~ Install/Uninstall

### To install

1. go in parent directory where you want to install to
2. do 'git clone https://github.com/WOLFBED/dspx', this will create new dir and install dspx within
3. cd into dspx/
4. do 'chmod +x install.sh && chmod +x uninstall.sh && chmod +x install-ubuntu.sh && chmod +x install-arch.sh'
5. do './install.sh'
6. follow the prompts
7. you should now have a desktop icon and a launcher script named dspx-launcher.sh
8. run the launcher script
9. you will also be able to find it in your applications menu

### To Uninstall

1. do './install-ubuntu.sh' or './install-arch.sh'
1. to uninstall, do './uninstall.sh'
2. follow the prompts

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

