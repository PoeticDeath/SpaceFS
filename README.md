How to use SpaceFS:  
You can replace the first input with your file or drive that you want to use, and where you want to mount second.  
Note: (NoWindow) was added during release V1.1.1 don't specifiy it on earlier releases or you will format your drive.  
Use (NoWindow) as 1 or 0, 1 will hide the running FS window while 0 will leave the FS window in the foreground.  
Only Specifiy (BlockSize) when formatting the file or drive, or else you will lose all of your data.  
The blocksize will be rounded to the next highest power of 2 at or after 512 automatically.  
Mode can be either FUSE or WinFsp.  
  Windows:  
    (Mode)SpaceFS.exe "C:\Space FS.bin" "C:\Space FS" (NoWindow) (BlockSize)  
  Linux:  
    ./SpaceFS /Space\ FS.bin /mnt/Space\ FS (NoWindow) (BlockSize)  
As of Version 1.6.5:  
Storage Efficiency:  
![SpaceEff](https://user-images.githubusercontent.com/46275713/213942347-c400bc6a-6e8d-42a5-8748-a5be8d45655d.png)  
SpaceFS:  
![SpaceFS](https://user-images.githubusercontent.com/46275713/218371555-be3fd2b6-2dc0-4e59-8502-be0e583b7396.png)  
NTFS:  
![NTFS](https://user-images.githubusercontent.com/46275713/218371590-5d0647e5-af09-47bf-87ca-533b2c29ab56.png)  
