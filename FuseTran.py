#!/usr/bin/env python3
import os
import errno
import struct
from sys import argv
from time import sleep,time
from threading import Thread,Lock
from SpaceFS import SpaceFS,RawDisk
from refuse.high import FUSE,FuseOSError,Operations
class FuseTran(Operations):
    def __init__(self,mount,disk,bs=None):
        if bs!=None:
            i=0
            while bs>512:
                i+=1
                bs=bs>>1
            RawDisk(open(disk,'rb+')).write(i.to_bytes(1,'big')+bytes(4)+b'\xff\xfe')
        self.s=SpaceFS(disk)
        self.rwlock=Lock()
        self.mount=mount
        self.fd=0
    def init(self,path):
        Thread(target=self.autosimp,daemon=True).start()
    def autosimp(self):
        while True:
            with self.rwlock:
                self.s.simptable()
            sleep(60)
    # Filesystem methods
    # ==================
    def access(self,path,mode):
        if os.name=='nt':
            with self.rwlock:
                if mode!=self.s.modes[path]:
                    raise FuseOSError(errno.EACCES)
    def chflags(self,path,flags):
        with self.rwlock:
            self.s.winattrs[path]=flags
        return 0
    def chmod(self,path,mode):
        with self.rwlock:
            c=[i for i in self.s.symlinks if (path.startswith(i+'/'))|(path==i)]
            if len(c)>0:
                path=path.replace(c[0],self.s.symlinks[c[0]],1)
            self.s.modes[path]&=0o770000
            self.s.modes[path]|=mode
        return 0
    def chown(self,path,uid,gid):
        with self.rwlock:
            c=[i for i in self.s.symlinks if (path.startswith(i+'/'))|(path==i)]
            if len(c)>0:
                path=path.replace(c[0],self.s.symlinks[c[0]],1)
            self.s.guids[path]=(gid,uid)
    def getxattr(self,path,name,position=0):
        raise FuseOSError(errno.ENOTSUP)
    def setxattr(self,path,name,value,options,position=0):
        raise FuseOSError(errno.ENOTSUP)
    def listxattr(self,path):
        return []
    def removexattr(self,path,name):
        raise FuseOSError(errno.ENOTSUP)
    def getattr(self,path,fh=None,sym=False):
        c=[i for i in self.s.symlinks if path.startswith(i+'/')]
        if len(c)>0:
            path=path.replace(c[0],self.s.symlinks[c[0]],1)
        if path in self.s.symlinks:
            return self.getattr(self.s.symlinks[path],fh,True)
        else:
            with self.rwlock:
                ti=time()
                t=[ti]*3
                try:
                    s=self.s.trunfile(path)
                    gid,uid=self.s.guids[path]
                    mode=self.s.modes[path]
                    flags=self.s.winattrs[path]
                    index=self.s.filenamesdic[path]
                    t=[struct.unpack('!d',self.s.times[index*24:index*24+24][i:i+8])[0] for i in range(0,24,8)]
                except ValueError:
                    s=0
                    if os.name=='nt':
                        gid=uid=545
                    else:
                        gid=uid=1000
                    flags=0
                    mode=16877
                    if (path!='/')&(path!='/.'):
                        if not sym:
                            raise FuseOSError(errno.ENOENT)
                        mode=33206
                if bin(mode)[2:].zfill(14)[-14]=='1':
                    return {'st_blocks':(s+self.s.sectorsize-1)//self.s.sectorsize,'st_atime':t[0],'st_mtime':t[1],'st_ctime':t[2],'st_birthtime':t[2],'st_size':s,'st_mode':mode,'st_gid':gid,'st_uid':uid,'st_flags':flags,'st_rdev':int.from_bytes(self.s.readfile(path,0,s),'big')}
                return {'st_blocks':(s+self.s.sectorsize-1)//self.s.sectorsize,'st_atime':t[0],'st_mtime':t[1],'st_ctime':t[2],'st_birthtime':t[2],'st_size':s,'st_mode':mode,'st_gid':gid,'st_uid':uid,'st_flags':flags}
    def readdir(self,path,fh):
        c=[i for i in self.s.symlinks if (path.startswith(i+'/'))|(path==i)]
        if len(c)>0:
            path=path.replace(c[0],self.s.symlinks[c[0]],1)
        dirents=['.','..']
        if path[-1]!='/':
                path+='/'
        for i in list(self.s.filenamesdic.keys())+list(self.s.symlinks.keys()):
            if i.startswith(path):
                if path.count('/')==i.count('/'):
                    c=i[1:].split('/')[-1]
                    if c not in dirents:
                        dirents.append(c)
                if path.count('/')+1==i.count('/'):
                    if i[1:].split('/')[-2] not in dirents:
                        tmp=i[1:].split('/')[-2]
                        if tmp not in dirents:
                            dirents.append(tmp)
                if path.count('/')+1<=i.count('/'):
                    tmp=i.split('/')[path.count('/')]
                    if tmp not in dirents:
                        d='/'.join(i.split('/')[:path.count('/')+1])+'/'
                        dirents.append(tmp)
        for r in dirents:
            yield r
    def readlink(self,path):
        if path in self.s.symlinks:
            return self.s.symlinks[path]
        else:
            return path
    def mknod(self,path,mode,dev):
        with self.rwlock:
            self.s.createfile(path,mode)
            self.s.writefile(path,0,dev.to_bytes((dev.bit_length()+7)//8,'big'))
        return 0
    def rmdir(self,path):
        with self.rwlock:
            c=[i for i in self.s.symlinks if path.startswith(i+'/')]
            if len(c)>0:
                path=path.replace(c[0],self.s.symlinks[c[0]],1)
            if path in self.s.filenamesdic:
                if list(self.readdir(path,0))==['.','..']:
                    self.s.deletefile(path,16877)
            else:
                raise FuseOSError(errno.ENOENT)
            return 0
    def mkdir(self,path,mode):
        with self.rwlock:
            c=[i for i in self.s.symlinks if path.startswith(i+'/')]
            if len(c)>0:
                path=path.replace(c[0],self.s.symlinks[c[0]],1)
            try:
                self.s.createfile(path,16877)
            except FileExistsError:
                raise FuseOSError(errno.EEXIST)
            return 0
    def opendir(self,path):
        self.fd+=1
        return self.fd
    def statfs(self,path):
        with self.rwlock:
            c={}
            avail=len(self.s.findnewblock(whole=True))
            if avail<0:
                avail=0
            c['f_bavail']=c['f_bfree']=c['f_favail']=avail
            c['f_bsize']=c['f_frsize']=self.s.sectorsize
            c['f_blocks']=self.s.sectorcount
            c['f_files']=len(self.s.filenamesdic)
            c['f_namemax']=255
            return c
    def unlink(self,path):
        with self.rwlock:
            self.s.deletefile(path)
    def symlink(self,name,target):
        with self.rwlock:
            c=os.path.normpath(self.mount+'/'.join(name.split('/')[:-1])+'/'+target).replace(self.mount,'',1).replace('\\','/')
            if os.path.exists(c):
                self.s.symlinks[name]=c
            else:
                if target[0]!='/':
                    target='/'+target
                self.s.symlinks[name]=target
    def rename(self,old,new):
        with self.rwlock:
            c=[i for i in self.s.symlinks if old.startswith(i+'/')]
            if len(c)>0:
                old=old.replace(c[0],self.s.symlinks[c[0]],1)
                new=new.replace(c[0],self.s.symlinks[c[0]],1)
            if old in self.s.symlinks:
                try:
                    self.s.renamefile(old,new)
                except IndexError:
                    raise FuseOSError(errno.ENOSPC)
            else:
                tmp=list(self.s.filenamesdic.keys())
                if self.s.modes[old]==16877:
                    tmp.pop(tmp.index(old))
                if old not in tmp:
                    for i in tmp:
                        if i.startswith(old+'/'):
                            try:
                                self.s.renamefile(i,i.replace(old,new,1))
                            except IndexError:
                                raise FuseOSError(errno.ENOSPC)
                try:
                    self.s.renamefile(old,new)
                except IndexError:
                    raise FuseOSError(errno.ENOSPC)
    def link(self,target,name):
        pass
    def lock(self,path,fh,cmd,lock):
        pass
    def utimens(self,path,times=[time()]*2):
        with self.rwlock:
            index=self.s.filenamesdic[path]
            self.s.times[index*24:index*24+16]=struct.pack('!d',times[0])+struct.pack('!d',times[1])
        return 0
    # File methods
    # ============
    def open(self,path,flags):
        self.fd+=1
        if type(flags)==int:
            return self.fd
        else:
            flags.fh=self.fd
            return 0
    def create(self,path,mode,fi=None):
        try:
            with self.rwlock:
                self.s.createfile(path,mode)
        except FileExistsError:
            raise FuseOSError(errno.EEXIST)
        except IndexError:
            raise FuseOSError(errno.ENOSPC)
        self.fd+=1
        if fi==None:
            return self.fd
        else:
            fi.fh=self.fd
            return 0
    def read(self,path,length,offset,fh):
        try:
            with self.rwlock:
                return self.s.readfile(path,offset,length)
        except EOFError:
            pass
    def write(self,path,data,offset,fh):
        with self.rwlock:
            if self.s.writefile(path,offset,data)==0:
                raise FuseOSError(errno.ENOSPC)
        return len(data)
    def truncate(self,path,length,fh=None):
        with self.rwlock:
            if self.s.trunfile(path,length)==0:
                raise FuseOSError(errno.ENOSPC)
    def setchgtime(self,path,time):
        with self.rwlock:
            index=self.s.filenamesdic[path]
            self.s.times[index*24+8:index*24+16]=struct.pack('!d',time)
        return 0
    def setcrtime(self,path,time):
        with self.rwlock:
            index=self.s.filenamesdic[path]
            self.s.times[index*24+16:index*24+24]=struct.pack('!d',time)
        return 0
    def destroy(self,path):
        with self.rwlock:
            self.s.simptable(F=True)
    def flush(self,path,fh):
        return 0
    def release(self,path,fh):
        return 0
    def fsync(self,path,fdatasync,fh):
        return 0
def main():
    try:
        disk=str(argv[1])
    except IndexError:
        disk='SpaceFS.bin'
    try:
        mount=str(argv[2])
    except IndexError:
        mount='/home/akerr/SpaceFS'
    try:
        fg=not int(argv[3])
    except IndexError:
        fg=True
    try:
        bs=int(argv[4])
    except IndexError:
        bs=None
    f=FuseTran(mount,disk,bs)
    if os.name=='nt':
        if fg==False:
            os.system('powershell "start \''+argv[0]+'\' -Args \''+argv[1]+' '+argv[2]+'\' -WindowStyle Hidden"')
        else:
            FUSE(f,mount,raw_fi=True,nothreads=False,foreground=fg,allow_other=True,big_writes=True,ExactFileSystemName='SpaceFS',SectorSize=512,SectorsPerAllocationUnit=f.s.sectorsize//512)
    else:
        FUSE(f,mount,raw_fi=True,nothreads=False,foreground=fg,allow_other=True,big_writes=True,fsname='SpaceFS')
if __name__=='__main__':
    main()
