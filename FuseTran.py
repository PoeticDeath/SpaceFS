#!/usr/bin/env python3
import os
import errno
from SpaceFS import SpaceFS
from fuse import FUSE,FuseOSError,Operations,fuse_get_context
class FuseTran(Operations):
    def __init__(self,mount):
        self.s=SpaceFS()
        self.mount=mount
        self.tmpfolders=[]
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
    def getattr(self,path,fh=None):
        try:
            s=self.s.trunfile(path)
            mode=33188
        except ValueError:
            s=0
            mode=16877
            if path!='/':
                if path not in self.tmpfolders:
                    if path not in ['/'.join(i.split('/')[:-1]) for i in self.s.filenames]:
                        full_path = self._full_path(path)
                        st = os.lstat(full_path)
                        return dict((key,getattr(st,key)) for key in ('st_size','st_mode','st_gid','st_uid'))
        return {'st_size':s,'st_mode':mode,'st_gid':1000,'st_uid':1000}
    def readdir(self,path,fh):
        dirents = ['.','..']
        if path[-1]!='/':
                path+='/'
        for i in self.s.filenames:
            if i.startswith(path):
                if path.count('/')==i.count('/'):
                    c=i[1:].split('/')[-1]
                    dirents+=[c]
                if path.count('/')+1==i.count('/'):
                    c=i[1:].split('/')[-2]
                    dirents+=[c]
                    if '/'+c not in self.tmpfolders:
                        self.tmpfolders+=['/'+c]
        for i in self.tmpfolders:
            if i.split('/')[-1] not in dirents:
                if i.startswith(path):
                    if path.count('/')==i.count('/'):
                        dirents+=[i.split('/')[-1]]
        for r in dirents:
            yield r
    def readlink(self,path):
        pass
    def mknod(self,path,mode,dev):
        return 0
    def rmdir(self,path):
        if path in self.tmpfolders:
            self.tmpfolders.pop(self.tmpfolders.index(path))
        return 0
    def mkdir(self,path,mode):
        if path not in self.tmpfolders:
            self.tmpfolders+=[path]
        return 0
    def statfs(self,path):
        c={}
        c['f_bavail']=c['f_bfree']=c['f_favail']=c['f_ffree']=self.s.sectorcount-self.s.findnewblock(False)
        c['f_bsize']=c['f_flag']=c['f_frsize']=self.s.sectorsize
        c['f_blocks']=self.s.sectorcount
        c['f_files']=16777216
        c['f_namemax']=255
        return c
    def unlink(self,path):
        self.s.deletefile(path)
    def symlink(self,name,target):
        pass
    def rename(self,old,new):
        if old not in self.s.filenames:
            for i in self.s.filenames:
                if i.startswith(old+'/'):
                    self.s.renamefile(i,i.replace(old,new))
            self.tmpfolders=[]
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
        self.s.createfile(path)
        if '/'.join(path.split('/')[:-1]) in self.tmpfolders:
            self.tmpfolders.pop(self.tmpfolders.index('/'.join(path.split('/')[:-1])))
        return 0
    def read(self,path,length,offset,fh):
        return self.s.readfile(path,offset,length)
    def write(self,path,data,offset,fh):
        self.s.writefile(path,offset,data)
        return len(data)
    def truncate(self,path,length,fh=None):
        self.s.trunfile(path,length)
    def flush(self,path,fh):
        pass
    def release(self,path,fh):
        pass
    def fsync(self,path,fdatasync,fh):
        pass
def main():
    mount='/home/akerr/SpaceFS'
    FUSE(FuseTran(mount),mount,nothreads=False,foreground=True,allow_other=True)
if __name__=='__main__':
    main()