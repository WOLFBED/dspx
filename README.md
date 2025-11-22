![img/dspx_Screenshot_shaved](img/dspx_Screenshot_shaved.avif "screnshoot")
# DSPX
PySide6 Data Store Pruner & Compressor Linux Application

### <span style='color: yellow;'>!!!</span> <span style='color: red;'>DO NOT USE THIS SOFTWARE UNDER ANY CIRCUMSTANCES : IT MAY DESTROY YOUR PROPERTY</span> <span style='color: yellow;'>!!!</span>





***

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
cd "$HOME/Desktop/" && \
git clone https://github.com/WOLFBED/dspx && cd dspx/ && \
chmod +x install.sh zyngInstaller.py && \
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

- [ ] make settings/configs saved to ~/.config/dspx, otherwise can't easily update app via 'git pull'
- [ ] decouple the UI from the processes, to ensure the GUI doesn't freeze
- [ ] look for ways to speed it up, it's still super slow.
- [x] merge tabs 2 and 3 since there's no longer the need to have them separated. (it used to make sense, but this is no longer the case.) -- nov 5 2025
- [x] make it so patterns can be enabled or disabled. -- nov 5 2025
- [ ] add spinner when process is running, otherwise confusing.
- [ ] Get a life. 

&nbsp;

## Development Journal

<span style='color: green;'>--- <b>21/11/2025 22:25</b> ---</span>
<p>Breaking it all down...</p>
<p>I'm starting with the given dirs as input -- these are grouped by block device so that optimizations per-device can be used.  Each device is identified as HDD or SSD and filesystem --where there are some specializations for BTRFS and ZFS---.  First it's device type, HDD or SSD that is identified, because it needs to know this first, then depending on filesystem, there may be some tweaks available.  So when DSPX knows how to deal with the devices, it will count the number of files and time this process with a files-per-seconds tracking and size of total amount of data to deal with -- this will be used to assess how big the task will be.  Based on this, it will use either In-memory querying for smaller amount, query streaming comparison with TigerBeetle, or use random access lookup with SQLite.</p>
<p>Need to finish the plan before writing app.  To be continued...</p>


&nbsp;
&nbsp;

<span style='color: green;'>--- <b>06/11/2025 13:50</b> ---</span>
<p>I will restructure the program around: 1. sessions; 2. de-coupling the 'processing' from the GUI code, to avoid freezing.</p>
<p>Sessions :: when the app is launched it starts a new dir under ~/.cache/dspx/sessions/ where it would use a fast database to write task lists, e.g.
list of files to get hashes for, their individual sizes, their storage device locations (which storage device they're on), etc. -- so that when the hashing task starts, it ca be done in batches and not take-up all the RAM and freeze everything up.  A copy of the settings and parameters used for the task.</p>
<p>This database should be fast -- maybe tigerbeetle, if appropriate ? </p>
<p>Settings and patterns should be verified by user before processing.  patterns should be audited before deploying.  there should be an examination of patterns TO MAKE REALLY SURE that the user won't accidentally delete their whole system -- maybe some pattern presets, like "SUPER SAFE" and "YOUR WISH IS MY COMMAND" or something</p>
<p>The first step in processing should just be counting files and number of storage devices -- so that there can be a superficial assessment of the task at hand, e.g. if there's 25 million files - this is likely a large job, are you sure? -- if so ...<br>
should make sure that, after measuring the total size of files to operate on, there will be enough space to run tasks on in ~/.cache, otherwise ask to reduce scope of task, or use another location for session storage.  default would be ~/.cache</p>
<p>After that, there should be a read/write throughput test on the devices in the task -- to have a vague idea/calculation for how long the task might take to complete, on tiny (tons), small (tons), medium (many), large (many), and xxx-large (few) files. </p>
<p>Research if fetching files and sizes at once may be too slow and should be separated into two tasks, one for just fetching the files, counting them, and the two, fetching their sizes -- maybe this is negligible and should be done at once, but for an extremely large number of extremely large files, maybe not.</p>
<p>Fetching file paths should be done in batches of size appropriate for speed of devices</p>
<p>File hashing :: before processing, should have a test made for tiny (tons), small (tons), medium (many), large (many), and xxx-large (few) files -- per device(s) to have/caclculate a vague idea how many files in batch to process at a time.</p></p>
<p>Automatically determined defaults for CPU and RAM usage, based on enumerated hardware -- with slider for increasing or decreasing percentage of CPUs and RAM to use -- Warn if setting above 80% that this is a bad idea</p>
<p>If session dir is located on same device as task to be performed, take this into consideration for potential performance bottleneck</p>
<p>Ensure that even the selection of which files to keep/delete is done in batches (because this will also freeze-up the app if there are loads) AND also when deleting files is done in batches too -- this will also be slow -- and none of these high number of things should ever be in RAM above specified capacity percentage</p>
<p>---OPTIONAL BUT DARN NICE--- when selecting files to keep/delete, ability to select/reject duplicates from specific devices, i.e. if the files you want to keep are on drive sda and duplicates may be on both drives sda and sdb -- rejecting any from sdb -- in many contexts, this would be extremely useful</p>
<p>So in the session db, for each file to work on, its device should be taken into account/recorded in db</p>
<p>Phew!</p>

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
- ~~This has been, in several parts, "vibe" coded.  Dear Lord.  I can write programs, I just don't like to.  ..But hey!  It works!~~
- Fun!  

