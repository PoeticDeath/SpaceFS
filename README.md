How to use SpaceFS:  
You can replace the first input with your file or drive that you want to use, and where you want to mount second.  
Note: Windows can not currently mount SpaceFS to its own disk and cannot mount a rawdisk like Linux can.  
Use the (NoWindow) as 1 or 0, 1 will hide the running FS window while 0 will run the FS window in the foreground.  
Only Specifiy (BlockSize) when formatting the file or drive, or else you will lose all of your data.  
The blocksize will be rounded to the next highest power of 2 at or after 512 automatically.  
  Windows:  
    SpaceFS.exe "C:\Space FS.bin" "C:\Space FS" (NoWindow) (BlockSize)  
  Linux:  
    ./SpaceFS /Space\ FS.bin /mnt/Space\ FS/ (NoWindow) (BlockSize)
