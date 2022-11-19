#!/usr/bin/env python3
import os
import errno
import struct
from sys import argv
from time import sleep,time
from SpaceFS import SpaceFS
from threading import Thread,Lock
from fuse import FUSE,FuseOSError,Operations,fuse_get_context
class FuseTran(Operations):
    def __init__(self,mount,disk,bs=None):
        self.s=SpaceFS(disk)
        if bs!=None:
            i=0
            while bs>512:
                i+=1
                bs=bs>>1
            self.s.disk.write(i.to_bytes(1,'big')+b'\x00'*4+b'\xff\xfe')
            self.s.disk.flush()
            self.s=SpaceFS(disk)
        self.mount=mount
        self.tmpfolders=[]
        self.oldtmpfolders=[]
        self.tmpf=[]
        self.rwlock=Lock()
        Thread(target=self.autosimp,daemon=True).start()
    def autosimp(self):
        while True:
            with self.rwlock:
                self.s.simptable()
            sleep(60)
    # Helpers
    # =======
    def _full_path(self,partial):
        if partial.startswith('/'):
            partial=partial[1:]
        path = os.path.join(self.mount+'-TMP/',partial)
        return path
    # Filesystem methods
    # ==================
    def access(self,path,mode):
        pass
    def chmod(self,path,mode):
        return 0
    def chown(self,path,uid,gid):
        return 0
    getxattr=None
    def getattr(self,path,fh=None):
        guid=1000
        ti=time()
        t=[ti]*3
        if (self.mount[0]!='/')&(self.mount[1:3]==':\\'):
            guid=545
        try:
            with self.rwlock:
                s=self.s.trunfile(path)
            mode=33188
            index=self.s.filenamesdic[path]
            t=self.s.times[index*24:index*24+24]
            if t==b'':
                t=struct.pack('!d',ti)*3
                self.s.times+=t
            t=[struct.unpack('!d',t[i:i+8])[0] for i in range(0,24,8)]
        except ValueError:
            s=0
            mode=16877
            if path!='/':
                if path+'/' not in self.tmpfolders:
                    if self.tmpfolders!=self.oldtmpfolders:
                        self.tmpf=['/'.join(i.split('/')[:-1]) for i in self.s.filenamesdic]
                        self.oldtmpfolders=self.tmpfolders
                    if path not in self.tmpf:
                        full_path=self._full_path(path)
                        st=os.lstat(full_path)
                        return dict((key,getattr(st,key)) for key in ('st_blocks','st_atime','st_mtime','st_ctime','st_birthtime','st_size','st_mode','st_gid','st_uid'))
        return {'st_blocks':(s+self.s.sectorsize-1)//self.s.sectorsize,'st_atime':t[0],'st_mtime':t[1],'st_ctime':t[2],'st_birthtime':t[2],'st_size':s,'st_mode':mode,'st_gid':guid,'st_uid':guid}
    def readdir(self,path,fh):
        dirents = ['.','..']
        if path[-1]!='/':
                path+='/'
        for i in self.s.filenamesdic:
            if i.startswith(path):
                if path.count('/')==i.count('/'):
                    dirents+=[i[1:].split('/')[-1]]
                if path.count('/')+1==i.count('/'):
                    if i[1:].split('/')[-2] not in dirents:
                        dirents+=[i[1:].split('/')[-2]]
                        self.tmpfolders+=['/'.join(i.split('/')[:-1])+'/']
                if path.count('/')+1<=i.count('/'):
                    c=i.split('/')[path.count('/')]
                    if c not in dirents:
                        d='/'.join(i.split('/')[:path.count('/')+1])+'/'
                        dirents+=[c]
                        if d not in self.tmpfolders:
                            self.tmpfolders+=[d]
        for i in self.tmpfolders:
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
        if path+'/' in self.tmpfolders:
            self.tmpfolders.pop(self.tmpfolders.index(path+'/'))
        return 0
    def mkdir(self,path,mode):
        if path+'/' not in self.tmpfolders:
            self.tmpfolders+=[path+'/']
        return 0
    def statfs(self,path):
        c={}
        with self.rwlock:
            avail=self.s.findnewblock(whole=True)
        if avail<0:
            avail=0
        c['f_bavail']=c['f_bfree']=c['f_favail']=c['f_ffree']=avail
        c['f_bsize']=c['f_flag']=c['f_frsize']=self.s.sectorsize
        c['f_blocks']=self.s.sectorcount
        c['f_files']=16777216
        c['f_namemax']=255
        return c
    def unlink(self,path):
        with self.rwlock:
            self.s.deletefile(path)
    def symlink(self,name,target):
        pass
    def rename(self,old,new):
        with self.rwlock:
            tmp=self.s.filenameslst
            if old not in tmp:
                for i in tmp:
                    if i.startswith(old+'/'):
                        self.s.renamefile(i,i.replace(old,new,1))
                self.tmpfolders=[new+'/']
            else:
                self.s.renamefile(old,new)
    def link(self,target,name):
        pass
    def utimens(self,path,times=None):
        return 0
    # File methods
    # ============
    def open(self,path,flags):
        return 0
    def create(self,path,mode,fi=None):
        with self.rwlock:
            self.s.createfile(path)
            if '/'.join(path.split('/')[:-1]) in self.tmpfolders:
                self.tmpfolders.pop(self.tmpfolders.index('/'.join(path.split('/')[:-1])))
            return 0
    def read(self,path,length,offset,fh):
        with self.rwlock:
            return self.s.readfile(path,offset,length)
    def write(self,path,data,offset,fh):
        with self.rwlock:
            if self.s.writefile(path,offset,data)==0:
                raise FuseOSError(errno.ENOSPC)
            return len(data)
    def truncate(self,path,length,fh=None):
        with self.rwlock:
            self.s.trunfile(path,length)
    def flush(self,path,fh):
        pass
    def release(self,path,fh):
        pass
    def fsync(self,path,fdatasync,fh):
        with self.rwlock:
            self.s.simptable()
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
    FUSE(FuseTran(mount,disk,bs),mount,nothreads=False,foreground=fg,allow_other=True,big_writes=True,intr=True)
if __name__=='__main__':
    main()
