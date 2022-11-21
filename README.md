How to use SpaceFS:  
You can replace the first input with your file or drive that you want to use, and where you want to mount second.  
Note: Windows can not currently mount SpaceFS to its own disk and cannot mount a rawdisk like Linux can.  
Note: (NoWindow) was added during release V1.1.1 don't specifiy it on earlier releases or you will format your drive.  
Use the (NoWindow) as 1 or 0, 1 will hide the running FS window while 0 will run the FS window in the foreground.  
Note: (NoWindow) Is not supported on Windows but must be specified to specifiy (BlockSize).  
Only Specifiy (BlockSize) when formatting the file or drive, or else you will lose all of your data.  
The blocksize will be rounded to the next highest power of 2 at or after 512 automatically.  
  Windows:  
    SpaceFS.exe "C:\Space FS.bin" "C:\Space FS" (NoWindow) (BlockSize)  
  Linux:  
    ./SpaceFS /Space\ FS.bin /mnt/Space\ FS (NoWindow) (BlockSize)
Storage Efficiency:
![F82FCD64-6CE6-412B-8F98-350532021035](https://user-images.githubusercontent.com/46275713/203096681-daefd933-c199-4d6a-8a18-50a56b1fc219.png)
4GB File Size:
![58153C56-625A-4AA8-8165-7785226B9FF9](https://user-images.githubusercontent.com/46275713/203096357-3b4f10d9-8ab8-491a-af5b-68e0a333f25d.png)
64MB File Size:
![image](https://user-images.githubusercontent.com/46275713/202867530-989db682-4a97-44f4-b816-ae910b9036ce.png)
![image](https://user-images.githubusercontent.com/46275713/202867527-d3442e51-1c1d-4f2e-9cb0-c20cf0456319.png)
