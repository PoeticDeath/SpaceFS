#!/usr/bin/env python3
import os
import errno
import struct
from sys import argv
from time import sleep,time
from SpaceFS import SpaceFS
from threading import Thread,Lock
from fuse import FUSE,FuseOSError,Operations
class FuseTran(Operations):
    def __init__(self,mount,disk,bs=None):
        if bs!=None:
            i=0
            while bs>512:
                i+=1
                bs=bs>>1
            with open(disk,'rb+') as o:
                o.write(i.to_bytes(1,'big')+bytes(4)+b'\xff\xfe')
        self.s=SpaceFS(disk)
        self.mount=mount
        self.tmpfolders=[]
        self.oldtmpfolders=[]
        self.tmpf=[]
        self.rwlock=Lock()
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
        if mode!=self.s.modes[path]:
            raise FuseOSError(errno.EACCES)
    def chmod(self,path,mode):
        c=[i for i in self.s.symlinks if (path.startswith(i+'/'))|(path==i)]
        if len(c)>0:
            path=path.replace(c[0],self.s.symlinks[c[0]],1)
        self.s.modes[path]&=0o770000
        self.s.modes[path]|=mode
        return 0
    def chown(self,path,uid,gid):
        c=[i for i in self.s.symlinks if (path.startswith(i+'/'))|(path==i)]
        if len(c)>0:
            path=path.replace(c[0],self.s.symlinks[c[0]],1)
        self.s.guids[path]=(gid,uid)
    getxattr=None
    def getattr(self,path,fh=None):
        c=[i for i in self.s.symlinks if path.startswith(i+'/')]
        if len(c)>0:
            path=path.replace(c[0],self.s.symlinks[c[0]],1)
        if path in self.s.symlinks:
            return self.getattr(self.s.symlinks[path],fh)
        else:
            with self.rwlock:
                ti=time()
                t=[ti]*3
                try:
                    s=self.s.trunfile(path)
                    gid,uid=self.s.guids[path]
                    mode=self.s.modes[path]
                    index=self.s.filenamesdic[path]
                    t=[struct.unpack('!d',self.s.times[index*24:index*24+24][i:i+8])[0] for i in range(0,24,8)]
                except ValueError:
                    s=0
                    if os.name=='nt':
                        gid=uid=545
                    else:
                        gid=uid=1000
                    mode=16877
                    if path!='/':
                        if path+'/' not in self.tmpfolders:
                            if self.tmpfolders!=self.oldtmpfolders:
                                self.tmpf=['/'.join(i.split('/')[:-1]) for i in self.s.filenamesdic]
                                self.oldtmpfolders=self.tmpfolders
                            if path not in self.tmpf:
                                raise FuseOSError(errno.ENOENT)
                return {'st_blocks':(s+self.s.sectorsize-1)//self.s.sectorsize,'st_atime':t[0],'st_mtime':t[1],'st_ctime':t[2],'st_birthtime':t[2],'st_size':s,'st_mode':mode,'st_gid':gid,'st_uid':uid}
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
                    dirents+=[i[1:].split('/')[-1]]
                if path.count('/')+1==i.count('/'):
                    if i[1:].split('/')[-2] not in dirents:
                        dirents+=[i[1:].split('/')[-2]]
                        tmp='/'.join(i.split('/')[:-1])+'/'
                        if tmp not in self.tmpfolders:
                            self.tmpfolders+=[tmp]
                if path.count('/')+1<=i.count('/'):
                    c=i.split('/')[path.count('/')]
                    if c not in dirents:
                        d='/'.join(i.split('/')[:path.count('/')+1])+'/'
                        dirents+=[c]
                        if d not in self.tmpfolders:
                            self.tmpfolders+=[d]
        for i in self.tmpfolders:
            if i.count('/')==path.count('/')+1:
                if i.startswith(path):
                    ni=True
                    for o in self.s.filenamesdic:
                        if o.startswith(i):
                            ni=False
                            break
                    if ni:
                        dirents+=[i.split('/')[-2]]
        for r in dirents:
            yield r
    def readlink(self,path):
        pass
    def mknod(self,path,mode,dev):
        return 0
    def rmdir(self,path):
        c=[i for i in self.s.symlinks if path.startswith(i+'/')]
        if len(c)>0:
            path=path.replace(c[0],self.s.symlinks[c[0]],1)
        if path+'/' in self.tmpfolders:
            if list(self.readdir(path,0))==['.','..']:
                self.tmpfolders.pop(self.tmpfolders.index(path+'/'))
        else:
            raise FuseOSError(errno.ENOENT)
        return 0
    def mkdir(self,path,mode):
        c=[i for i in self.s.symlinks if path.startswith(i+'/')]
        if len(c)>0:
            path=path.replace(c[0],self.s.symlinks[c[0]],1)
        if path+'/' not in self.tmpfolders:
            self.tmpfolders+=[path+'/']
        else:
            raise FuseOSError(errno.EEXIST)
        return 0
    def opendir(self,path):
        self.fd+=1
        return self.fd
    def statfs(self,path):
        c={}
        with self.rwlock:
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
        self.s.symlinks[name]=os.path.normpath(self.mount+'/'.join(name.split('/')[:-1])+'/'+target).replace(self.mount,'',1).replace('\\','/')
    def renameguidmode(self,old,new):
        try:
            self.s.guids[new]=self.s.guids[old]
            del self.s.guids[old]
            self.s.modes[new]=self.s.modes[old]
            del self.s.modes[old]
        except KeyError:
            pass
    def rename(self,old,new):
        c=[i for i in self.s.symlinks if old.startswith(i+'/')]
        if len(c)>0:
            old=old.replace(c[0],self.s.symlinks[c[0]],1)
            new=new.replace(c[0],self.s.symlinks[c[0]],1)
        if old in self.s.symlinks:
            self.s.renamefile(old,new)
        else:
            with self.rwlock:
                tmp=list(self.s.filenamesdic.keys())
                if old not in tmp:
                    for i in tmp:
                        if i.startswith(old+'/'):
                            self.s.renamefile(i,i.replace(old,new,1))
                            self.renameguidmode(i,i.replace(old,new,1))
                    self.tmpfolders[self.tmpfolders.index(old+'/')]=new+'/'
                else:
                    self.s.renamefile(old,new)
                    self.renameguidmode(old,new)
    def link(self,target,name):
        pass
    def utimens(self,path,times=None):
        return 0
    # File methods
    # ============
    def open(self,path,flags):
        self.fd+=1
        return self.fd
    def create(self,path,mode,fi=None):
        with self.rwlock:
            try:
                self.s.createfile(path,mode)
            except FileExistsError:
                raise FuseOSError(errno.EEXIST)
            self.fd+=1
            return self.fd
    def read(self,path,length,offset,fh):
        with self.rwlock:
            try:
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
            self.s.trunfile(path,length)
    def destroy(self,path):
        with self.rwlock:
            self.s.simptable(F=True)
    def flush(self,path,fh):
        pass
    def release(self,path,fh):
        pass
    def fsync(self,path,fdatasync,fh):
        pass
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
    FUSE(FuseTran(mount,disk,bs),mount,nothreads=False,foreground=fg,allow_other=True,big_writes=True)
if __name__=='__main__':
    main()
