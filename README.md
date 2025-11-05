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

### Install

1. in your terminal, go in parent directory where you want to install dspx
2. paste the below snippet, press enter, and follow the prompts -> it will create new dir and install dspx within:
```bash
git clone https://github.com/WOLFBED/dspx && \
cd dspx/ && \
chmod +x install.sh && chmod +x uninstall.sh && chmod +x install-ubuntu.sh && chmod +x install-arch.sh && \
./install.sh
```
3. you should now have a desktop icon and a launcher script named dspx-launcher.sh
5. you will also be able to find it in your applications menu, or you can run the launcher script directly

### Update to latest version

1. go in dspx/ directory
2. do:
```bash
git pull
```
3. should update to current version

### Uninstall

1. go into dspx/ install directory
2. do:
```bash
./uninstall.sh
```
3. follow the prompts
4. u gud bra

&nbsp;

## TODO List

- [ ] look for ways to speed it up, it's still super slow.
- [ ] merge tabs 2 and 3 since there's no longer the need to have them separated. (it used to make sense, but this is no longer the case.)
- [ ] make it so patterns can be enabled or disabled.
- [ ] add spinner when process is running, otherwise confusing.
- [ ] Get a life. 

&nbsp;

## Future Features
- option to compress all:
  - audio files to opus
  - image files to avif or jxl
  - video files to av1/opus
- analyze task throughput and approximate a completion time, i.e. "should be done in x time"
- ---OPTIONAL--- compares files that are extremely similar but not identical, and displays them -- at which point you're given the choice to delete them, one at a time.  This would be especially useful for images.
- ~~use argparse instead of diarrhea~~

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

