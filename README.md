How to use SpaceFS:  
You can replace the first input with your file or drive that you want to use, and where you want to mount second.  
Note: Windows can not mount a rawdisk like Linux can.  
Note: (NoWindow) was added during release V1.1.1 don't specifiy it on earlier releases or you will format your drive.  
Use the (NoWindow) as 1 or 0, 1 will hide the running FS window while 0 will run the FS window in the foreground.  
Only Specifiy (BlockSize) when formatting the file or drive, or else you will lose all of your data.  
The blocksize will be rounded to the next highest power of 2 at or after 512 automatically.  
  Windows:  
    SpaceFS.exe "C:\Space FS.bin" "C:\Space FS" (NoWindow) (BlockSize)  
  Linux:  
    ./SpaceFS /Space\ FS.bin /mnt/Space\ FS (NoWindow) (BlockSize)  
As of Version 1.5.9:  
Storage Efficiency:  
![SpaceEff](https://user-images.githubusercontent.com/46275713/213942347-c400bc6a-6e8d-42a5-8748-a5be8d45655d.png)  
ATTO:  
![ATTO](https://user-images.githubusercontent.com/46275713/213942366-bc901beb-8a7c-4167-ad48-48f25b986183.png)  
CrystalDiskMark:  
![CrystalDiskMark](https://user-images.githubusercontent.com/46275713/213942389-dae2fe25-113b-4690-acea-d69874f6bd29.png)  
