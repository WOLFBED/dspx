![img/dspx_Screenshot_shaved](img/dspx_Screenshot_shaved.avif "screnshoot")
# DSPX
PySide6 Data Store Pruner & Compressor Linux Application

&nbsp;

## Features & Stuff

1. takes a list of dir paths as input
2. looks in given dir(s) for any OS residual files, recursively, and gives the choice to delete them individually or all at once
3. does file deduplication in given dir(s), and gives the choice to delete them individually or all at once
4. deletes any empty subdirs in given dir(s), and gives the choice to delete them individually or all at once
5. write all operations to a log file where the program is run
6. uses AsyncIO and Blake3 for parallelized multithreaded hashing and pattern matching so it runs faster
7. pattern-matching settings is configurable, like a spreadsheet, and can be saved
8. CPU threads and RAM usage are configurable, and these settings can be saved
9. has installer which creates a virtual environment and installs all dependencies, and a launcher script with desktop icon

&nbsp;

## How to Install / Update / Uninstall

### Install

1. in your terminal, go in parent directory where you want to install dspx
2. paste the below snippet, press enter, and follow the prompts -> it will create new dspx dir and install it within:
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

- [ ] decouple the UI from the processes, to ensure the GUI doesn't freeze
- [ ] look for ways to speed it up, it's still super slow.
- [x] merge tabs 2 and 3 since there's no longer the need to have them separated. (it used to make sense, but this is no longer the case.) -- nov 5 2025
- [x] make it so patterns can be enabled or disabled. -- nov 5 2025
- [ ] add spinner when process is running, otherwise confusing.
- [ ] Get a life. 

&nbsp;

## Future Features
- NUMA-aware asyncio + io_uring reference implementation :: use numactl or libnuma to bind memory to a NUMA node
- adjustable MAX_INFLIGHT to control how many simultaneous outstanding reads we allow
  grouping by file size to avoid comparing hashes across different sizes
- use SQPOLL (IORING_SETUP_SQPOLL) to have submissions without syscalls
- use O_DIRECT to avoid page cache and gives more deterministic behavior
- use io_uring binding to expose a way to read into preallocated bytearray/mmap buffers and reuse those buffers, to eliminate extra allocations and GC pressure
- spawn one process per NUMA node - this avoids Python GIL contention and allows memory + CPU affinity to be set per process
- add settings: best for ssd, best for hdd, best fpr both, best for large RAM, best for more/less CPU cores --- and manual specifications
- for collecting results use an on-disk key-value store (LMDB) or append-only files and then an external merge step
- use O_DIRECT + aligned reads + preallocated posix_memalign buffers for minimal kernel copies
- use IORING_SETUP_SQPOLL with an appropriately tuned SQ poll thread to obliterate syscall overhead on high QD
- for multiple physical spindles, schedule disk access per-device (group files by device) to avoid head thrash across devices
- replace python-level process spawning with a lightweight C supervisor that uses liburing directly and hands hashing work to worker threads in a tight loop (lowest overhead)
- option to compress all:
  - audio files to opus
  - image files to avif or jxl
  - video files to av1/opus
- analyze task throughput and approximate a completion time, i.e. "should be done in x time"
- ---OPTIONAL--- compares files that are extremely similar but not identical, and displays them -- at which point you're given the choice to delete them, one at a time.  This would be especially useful for images.
- ~~use argparse instead of diarrhea~~
<br>
*(see joplin doc for more details)

&nbsp;

## Requirements
- x86_64 linux 6+
- Arch or Ubuntu based distro
- python 3.12+
- git
- ~~rust~~ _(not yet needed)_
- python modules:
  - PySide6>=6.5.0
  - blake3>=0.4.1

&nbsp;

## Nota Bene
- This has been, in several parts, "vibe" coded.  Dear Lord.  I can write programs, I just don't like to.  ..But hey!  It works!

