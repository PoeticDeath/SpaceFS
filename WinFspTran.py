#A file system implemented on top of winfspy. Useful for efficiently storing files.

import os
import sys
import logging
import argparse
import threading
import multiprocessing
from pathlib import Path
from functools import wraps

import struct
from time import sleep,time
from SpaceFS import SpaceFS,RawDisk

from winfspy import (
    FileSystem,
    BaseFileSystemOperations,
    enable_debug_log,
    FILE_ATTRIBUTE,
    CREATE_FILE_CREATE_OPTIONS,
    NTStatusObjectNameNotFound,
    NTStatusDirectoryNotEmpty,
    NTStatusNotADirectory,
    NTStatusObjectNameCollision,
    NTStatusAccessDenied,
    NTStatusEndOfFile,
    NTStatusMediaWriteProtected,
    NTStatusNotAReparsePoint,
    NTStatusReparsePointNotResolved,
)

from winfspy.plumbing.security_descriptor import SecurityDescriptor

# Because `encode('UTF16')` appends a BOM a the begining of the output
_STRING_ENCODING='UTF-16-LE' if sys.byteorder=='little' else 'UTF-16-BE'
_BYTE_ENCODING='big' if 'BE' in _STRING_ENCODING else 'little'

def attrtoATTR(attr):
    ATTR=0
    for i in [(-2,32768),(-1,4096),(-3,128),(-6,2048),(-5,8192),(-11,1024)]:
        try:
            if attr[i[0]]=='1':
                ATTR+=i[1]
        except IndexError:
            pass
    return ATTR
def ATTRtoattr(ATTR):
    attr=0
    for i in [(-16,FILE_ATTRIBUTE.FILE_ATTRIBUTE_HIDDEN),(-13,FILE_ATTRIBUTE.FILE_ATTRIBUTE_READONLY),(-8,FILE_ATTRIBUTE.FILE_ATTRIBUTE_SYSTEM),
              (-12,FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE),(-14,FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY),(-11,FILE_ATTRIBUTE.FILE_ATTRIBUTE_REPARSE_POINT)]:
        try:
            if ATTR[i[0]]=='1':
                attr+=i[1]
        except IndexError:
            pass
    return attr
def operation(fn):
    #Decorator for file system operations. Provides both logging and thread-safety
    name=fn.__name__
    @wraps(fn)
    def wrapper(self,*args,**kwargs):
        head=args[0] if args else None
        tail=args[1:] if args else ()
        if logging.root.level>=logging.INFO:
            try:
                with self._thread_lock:
                    result=fn(self,*args,**kwargs)
            except Exception as exc:
                logging.info(f'NOK | {name:20} | {head!r:20} | {tail!r:20} | {exc!r}')
                raise
            else:
                logging.info(f'OK! | {name:20} | {head!r:20} | {tail!r:20} | {result!r}')
                return result
        else:
            with self._thread_lock:
                return fn(self,*args,**kwargs)
    return wrapper
class SpaceFSOperations(BaseFileSystemOperations):
    def __init__(self,disk,sectorsize,label,read_only=False):
        super().__init__()
        if sectorsize!=-1:
            i=0
            while sectorsize>512:
                i+=1
                sectorsize=sectorsize>>1
            RawDisk(open(disk,'rb+')).write(i.to_bytes(1,'big')+bytes(4)+b'\xff\xfe')
        self.s=SpaceFS(disk)
        if '/' not in self.s.filenamesdic:
            self.s.createfile('/',16877)
        else:
            print('Careful the disk was unmounted improperly.')
        self.s.winattrs['/']=attrtoATTR(bin(FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY)[2:])
        if '' not in self.s.filenamesdic:
            self.s.createfile('',448)
            self.s.writefile('',0,b'O:WDG:WDD:P(A;;FA;;;WD)')
        if ':' not in self.s.filenamesdic:
            self.s.createfile(':',448)
            self.s.writefile(':',0,b'SpaceFS')
        if label!='':
            self.label=label
            self.s.trunfile(':',len(label.encode()))
            self.s.writefile(':',0,label.encode())
        else:
            self.label=self.s.readfile(':',0,self.s.trunfile(':')).decode()
        self.read_only=read_only
        self._thread_lock=threading.Lock()
        threading.Thread(target=self.autosimp,daemon=True).start()
        self.allocsizes={}
        self.opened=[]
        self.lowerfilenamesdic=dict([[i.lower(),self.s.filenamesdic[i]] for i in self.s.filenameslst if i.startswith('/')])
    def autosimp(self):
        ofc=len(self.s.filenamesdic)
        omc=len(self.s.missinglst)
        while True:
            if (abs(len(self.s.filenamesdic)-ofc)>10000)|(abs(len(self.s.missinglst)-omc)>10):
                with multiprocessing.Pool(1) as P:
                    S=P.map(self.s.smptable,[[self.s.table,self.s.readtable(),self.s.filenameslst,self.s.guids,self.s.modes,self.s.winattrs,self.s.symlinks,self.s.times]])[0]
                    self.s.simptable(elst=S[0],filenames=S[1])
                ofc=len(self.s.filenamesdic)
                omc=len(self.s.missinglst)
            sleep(60)
    @operation
    def get_volume_info(self):
        avail=len(self.s.missinglst)
        if avail<0:
            avail=0
        return {'total_size':self.s.sectorcount*self.s.sectorsize,'free_size':avail*self.s.sectorsize,'volume_label':self.label}
    @operation
    def set_volume_label(self,label):
        self.label=label
        self.s.trunfile(':',len(label.encode()))
        self.s.writefile(':',0,label.encode())
    @operation
    def get_security_by_name(self,file_name):
        file_name=file_name.replace('\\','/')
        dir_name='/'.join(file_name.split('/')[:-1])
        if file_name not in self.s.filenamesdic:
            try:
                file_name=self.s.filenameslst[self.lowerfilenamesdic[file_name.lower()]]
            except KeyError:
                while dir_name not in self.s.filenamesdic:
                    dir_name='/'.join(dir_name.split('/')[:-1])
                if self.s.winattrs[dir_name]&FILE_ATTRIBUTE.FILE_ATTRIBUTE_REPARSE_POINT:
                    SD=SecurityDescriptor.from_string(self.s.readfile(dir_name.split(':')[0][1:],0,self.s.trunfile(dir_name.split(':')[0][1:])).decode())
                    return (ATTRtoattr(bin(self.s.winattrs[dir_name])[2:]),SD.handle,SD.size)
                raise NTStatusObjectNameNotFound()
        if file_name.split(':')[0][1:] not in self.s.filenamesdic:
            self.s.createfile(file_name.split(':')[0][1:],448)
            self.s.writefile(file_name.split(':')[0][1:],0,self.s.readfile(dir_name[1:],0,self.s.trunfile(dir_name[1:])))
        SD=SecurityDescriptor.from_string(self.s.readfile(file_name.split(':')[0][1:],0,self.s.trunfile(file_name.split(':')[0][1:])).decode())
        return (ATTRtoattr(bin(self.s.winattrs[file_name])[2:]),SD.handle,SD.size)
    @operation
    def create(self,file_name,create_options,granted_access,file_attributes,security_descriptor,allocation_size):
        if file_name=='\\Exit':
            self.s.deletefile('/')
            self.s.simptable(F=True)
            raise NTStatusAccessDenied()
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        file_name=file_name.replace('\\','/')
        dir_name='/'.join(file_name.split('/')[:-1])
        if file_name in self.s.filenamesdic:
            raise NTStatusObjectNameCollision()
        try:
            if bin(file_attributes)[2:].zfill(32)[-5]=='1':
                self.s.createfile(file_name,16877)
            else:
                self.s.createfile(file_name,448)
            self.lowerfilenamesdic[file_name.lower()]=self.s.filenamesdic[file_name]
            if file_name.split(':')[0][1:] not in self.s.filenamesdic:
                self.s.createfile(file_name.split(':')[0][1:],448)
                SD=security_descriptor.to_string()
                if 'D:P' in SD:
                    self.s.writefile(file_name.split(':')[0][1:],0,SD.encode())
                else:
                    self.s.writefile(file_name.split(':')[0][1:],0,self.s.readfile(dir_name[1:],0,self.s.trunfile(dir_name[1:])))
            self.s.winattrs[file_name]|=attrtoATTR(bin(file_attributes)[2:])
        except IndexError:
            raise NTStatusEndOfFile()
        self.allocsizes[file_name]=allocation_size
        self.opened.append(file_name)
        return file_name
    @operation
    def get_security(self,file_context):
        return SecurityDescriptor.from_string(self.s.readfile(file_context.split(':')[0][1:],0,self.s.trunfile(file_context.split(':')[0][1:])).decode())
    @operation
    def set_security(self,file_context,security_information,modification_descriptor):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        SD=SecurityDescriptor.from_string(self.s.readfile(file_context.split(':')[0][1:],0,self.s.trunfile(file_context.split(':')[0][1:])).decode())
        SD=SD.evolve(security_information>>1<<1,modification_descriptor).to_string()
        if security_information%2!=0:
            S=SecurityDescriptor.from_cpointer(modification_descriptor).to_string()
            if 'G:' not in S:
                SD=S+SD[SD.index('G:'):]
            else:
                SD=S[:S.index('G:')]+SD[SD.index('G:'):]
        self.s.trunfile(file_context.split(':')[0][1:],0)
        self.s.writefile(file_context.split(':')[0][1:],0,SD.encode())
    @operation
    def rename(self,file_context,file_name,new_file_name,replace_if_exists):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        file_name=file_name.replace('\\','/')
        new_file_name=new_file_name.replace('\\','/')
        c=[i for i in self.s.symlinks if file_name.startswith(i+'/')]
        if len(c)>0:
            file_name=file_name.replace(c[0],self.s.symlinks[c[0]],1)
            new_file_name=new_file_name.replace(c[0],self.s.symlinks[c[0]],1)
        if (new_file_name in self.s.filenamesdic)&(file_name in self.s.filenamesdic):
            if self.s.modes[file_name]==16877:
                if self.readdir(file_name,'..')!=[]:
                    raise NTStatusAccessDenied()
        if not replace_if_exists:
            if new_file_name in self.s.filenamesdic:
                raise NTStatusObjectNameCollision()
        if file_name in self.s.symlinks:
            try:
                self.s.renamefile(file_name,new_file_name)
                self.s.renamefile(file_name[1:],new_file_name[1:])
            except IndexError:
                raise NTStatusEndOfFile()
        else:
            tmp=list(self.s.filenamesdic.keys())
            if self.s.modes[file_name]==16877:
                tmp.pop(tmp.index(file_name))
            if file_name not in tmp:
                for i in tmp:
                    if i.startswith(file_name+'/'):
                        try:
                            self.s.renamefile(i,i.replace(file_name,new_file_name,1))
                            if ':' not in i:
                                self.s.renamefile(i[1:],i[1:].replace(file_name[1:],new_file_name[1:],1))
                            del self.lowerfilenamesdic[i.lower()]
                            self.lowerfilenamesdic[i.replace(file_name,new_file_name,1).lower()]=self.s.filenamesdic[i.replace(file_name,new_file_name,1)]
                            self.allocsizes[i.replace(file_name,new_file_name,1)]=self.allocsizes[i]
                            del self.allocsizes[i]
                        except IndexError:
                            raise NTStatusEndOfFile()
            try:
                self.s.renamefile(file_name,new_file_name)
                if ':' not in file_name:
                    self.s.renamefile(file_name[1:],new_file_name[1:])
                del self.lowerfilenamesdic[file_name.lower()]
                self.lowerfilenamesdic[new_file_name.lower()]=self.s.filenamesdic[new_file_name]
                self.allocsizes[new_file_name]=self.allocsizes[file_name]
                del self.allocsizes[file_name]
            except IndexError:
                raise NTStatusEndOfFile()
    @operation
    def open(self,file_name,create_options,granted_access):
        file_name=file_name.replace('\\','/')
        if file_name not in self.s.filenamesdic:
            file_name=self.s.filenameslst[self.lowerfilenamesdic[file_name.lower()]]
        self.opened.append(file_name)
        return file_name
    @operation
    def close(self,file_context):
        self.opened.remove(file_context)
    def gfi(self,file_context):
        index=self.s.filenamesdic[file_context.split(':')[0]]
        t=[int(struct.unpack('!d',self.s.times[index*24:index*24+24][i:i+8])[0]*10000000+116444736000000000) for i in range(0,24,8)]
        for i in range(3):
            if t[i]>116444736000000000:
                t[i]+=2
            elif t[i]==279172874304:
                t[i]+=1
            elif t[i]==287762808896:
                t[i]+=3
        if file_context not in self.allocsizes:
            self.allocsizes[file_context]=(self.s.trunfile(file_context)+self.s.sectorsize-1)//self.s.sectorsize*self.s.sectorsize
        ATTR=ATTRtoattr(bin(self.s.winattrs[file_context])[2:])
        return {'file_attributes':ATTR,
                'reparse_tag':int.from_bytes(self.s.readfile(file_context,0,4),_BYTE_ENCODING) if bin(ATTR)[2:].zfill(32)[-11]=='1' else 0,
                'allocation_size':self.allocsizes[file_context],
                'file_size':self.s.trunfile(file_context),
                'creation_time':t[2],
                'last_access_time':t[0],
                'last_write_time':t[1],
                'change_time':t[1],
                'index_number':index}
    @operation
    def get_file_info(self,file_context):
        try:
            return self.gfi(file_context)
        except KeyError:
            raise NTStatusObjectNameNotFound()
    @operation
    def set_basic_info(self,file_context,file_attributes,creation_time,last_access_time,last_write_time,change_time,file_info):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        index=self.s.filenamesdic[file_context.split(':')[0]]
        if file_attributes!=FILE_ATTRIBUTE.INVALID_FILE_ATTRIBUTES:
            self.s.winattrs[file_context]=attrtoATTR(bin(file_attributes)[2:])
        if last_access_time&last_write_time&creation_time:
            self.s.times[index*24:index*24+24]=struct.pack('!d',(last_access_time-116444736000000000)/10000000)+struct.pack('!d',(last_write_time-116444736000000000)/10000000)+struct.pack('!d',(creation_time-116444736000000000)/10000000)
        else:
            if last_access_time:
                self.s.times[index*24:index*24+8]=struct.pack('!d',(last_access_time-116444736000000000)/10000000)
            if last_write_time:
                self.s.times[index*24+8:index*24+16]=struct.pack('!d',(last_write_time-116444736000000000)/10000000)
            if creation_time:
                self.s.times[index*24+16:index*24+24]=struct.pack('!d',(creation_time-116444736000000000)/10000000)
        return self.gfi(file_context)
    @operation
    def set_file_size(self,file_context,new_size,set_allocation_size):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        if set_allocation_size:
            self.allocsizes[file_context]=(new_size+self.s.sectorsize-1)//self.s.sectorsize*self.s.sectorsize
            if new_size<self.s.trunfile(file_context):
                self.s.trunfile(file_context,new_size)
        else:
            if self.s.trunfile(file_context,new_size)==0:
                raise NTStatusEndOfFile()
    @operation
    def can_delete(self,file_context,file_name):
        if self.s.modes[file_context]==16877:
            if self.readdir(file_context,'..')!=[]:
                raise NTStatusDirectoryNotEmpty()
    def readdir(self,file_context,marker):
        c=[i for i in self.s.symlinks if (file_context.startswith(i+'/'))|(file_context==i)]
        if len(c)>0:
            file_context=file_context.replace(c[0],self.s.symlinks[c[0]],1)
        if file_context[-1]!='/':
            file_context+='/'
        dirents=[{'file_name':'.',**self.gfi('/'+'/'.join(file_context.split('/')[1:-1]))},{'file_name':'..',**self.gfi('/'+'/'.join(file_context.split('/')[1:-2]))}]
        for i in list(self.s.filenamesdic.keys())+list(self.s.symlinks.keys()):
            if (i!='/')&(':' not in i)&(i.startswith(file_context)):
                if file_context.count('/')==i.count('/'):
                    c=i[1:].split('/')[-1]
                    o=self.gfi(i)
                    if {'file_name':c,**o} not in dirents:
                        dirents.append({'file_name':c,**o})
                if i[-1]=='/':
                    if file_context.count('/')+1==i.count('/'):
                        tmp=i[1:].split('/')[-2]
                        o=self.gfi(i)
                        if {'file_name':tmp,**o} not in dirents:
                            tmp=i[1:].split('/')[-2]
                            if {'file_name':tmp,**o} not in dirents:
                                dirents.append({'file_name':tmp,**o})
                    if file_context.count('/')+1<=i.count('/'):
                        tmp=i.split('/')[file_context.count('/')]
                        o=self.gfi(i)
                        if {'file_name':tmp,**o} not in dirents:
                            d='/'.join(i.split('/')[:file_context.count('/')+1])+'/'
                            dirents.append({'file_name':tmp,**o})
        dirents=sorted(dirents,key=lambda x:x['file_name'])
        if marker is None:
            return dirents
        for i,dirent in enumerate(dirents):
            if dirent['file_name']==marker:
                return dirents[i+1:]
    @operation
    def read_directory(self,file_context,marker):
        return self.readdir(file_context,marker)
    @operation
    def get_dir_info_by_name(self,file_context,file_name):
        if file_context[-1]!='/':
            file_context+='/'
        file=file_context+file_name
        if file not in self.s.filenamesdic:
            try:
                file=self.s.filenameslst[self.lowerfilenamesdic[file.lower()]]
            except KeyError:
                raise NTStatusObjectNameNotFound()
        return {'file_name':file,**self.gfi(file)}
    @operation
    def read(self,file_context,offset,length):
        try:
            return self.s.readfile(file_context,offset,length)
        except EOFError:
            raise NTStatusEndOfFile()
    @operation
    def write(self,file_context,buffer,offset,write_to_end_of_file,constrained_io):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        if write_to_end_of_file:
            offset=self.s.trunfile(file_context)
        if self.s.writefile(file_context,offset,buffer)==0:
            raise NTStatusEndOfFile()
        return len(buffer)
    @operation
    def cleanup(self,file_context,file_name,flags):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        if self.s.modes[file_context]!=16877:
            self.s.winattrs[file_context]|=attrtoATTR(bin(FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE)[2:])
        index=self.s.filenamesdic[file_context.split(':')[0]]
        t=time()
        FspCleanupDelete=0x01
        FspCleanupAllocationSize=0x02
        FspCleanupSetLastAccessTime=0x20
        FspCleanupSetLastWriteTime=0x40
        FspCleanupSetChangeTime=0x80
        if flags&FspCleanupDelete:
            if self.s.modes[file_context]==16877:
                if self.readdir(file_context,'..')!=[]:
                    raise NTStatusDirectoryNotEmpty()
            self.s.deletefile(file_context)
            del self.lowerfilenamesdic[file_context.lower()]
            for i in enumerate(self.s.filenameslst[index:]):
                if i[1].startswith('/'):
                    self.lowerfilenamesdic[i[1].split(',')[0].lower()]=i[0]+index
            if ':' not in file_context:
                self.s.deletefile(file_context[1:])
                for i in list(self.s.filenamesdic.keys()):
                    if i.startswith(file_context+':'):
                        rindex=self.s.filenamesdic[i]
                        self.s.deletefile(i)
                        del self.lowerfilenamesdic[i.lower()]
                        for i in enumerate(self.s.filenameslst[rindex:]):
                            if i[1].startswith('/'):
                                self.lowerfilenamesdic[i[1].split(',')[0].lower()]=i[0]+index
        if flags&FspCleanupAllocationSize:
            self.allocsizes[file_context]=(self.s.trunfile(file_context)+self.s.sectorsize-1)//self.s.sectorsize*self.s.sectorsize
        if (flags&FspCleanupSetLastAccessTime)&(not flags&FspCleanupDelete):
            self.s.times[index*24:index*24+8]=struct.pack('!d',t)
        if ((flags&FspCleanupSetLastWriteTime)|(flags&FspCleanupSetChangeTime))&(not flags&FspCleanupDelete):
            self.s.times[index*24+8:index*24+16]=struct.pack('!d',t)
    @operation
    def overwrite(self,file_context,file_attributes,replace_file_attributes,allocation_size):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        for i in list(self.s.filenamesdic.keys()):
            if i.startswith(file_context+':'):
                if i not in self.opened:
                    rindex=self.s.filenamesdic[i]
                    self.s.deletefile(i)
                    del self.lowerfilenamesdic[i.lower()]
                    for i in enumerate(self.s.filenameslst[rindex:]):
                        if i[1].startswith('/'):
                            self.lowerfilenamesdic[i[1].split(',')[0].lower()]=i[0]+rindex
        if replace_file_attributes:
            self.s.winattrs[file_context]=attrtoATTR(bin(file_attributes)[2:])
        else:
            self.s.winattrs[file_context]|=attrtoATTR(bin(file_attributes)[2:])
        self.s.trunfile(file_context,allocation_size)
        index=self.s.filenamesdic[file_context.split(':')[0]]
        t=time()
        self.s.times[index*24:index*24+16]=struct.pack('!d',t)*2
    @operation
    def flush(self,file_context):
        pass
    @operation
    def resolve_reparse_points(self,file_name,reparse_point_index,resolve_last_path_component,p_io_status,buffer,p_size):
        file_context=file_name.replace('\\','/')
        dir_name='/'.join(file_context.split('/')[:-1])
        try:
            buf=self.s.readfile(file_context,0,self.s.trunfile(file_context))
        except ValueError:
            while dir_name not in self.s.filenamesdic:
                dir_name='/'.join(dir_name.split('/')[:-1])
            buf=self.s.readfile(dir_name,0,self.s.trunfile(dir_name))
            file_context=file_context.replace(dir_name,'',1)
        dire=dir_name+'/'
        T=buf[:4]
        if T==b'\x0c\x00\x00\xa0':
            SNO=int.from_bytes(buf[4:8],_BYTE_ENCODING)
            SNL=int.from_bytes(buf[8:10],_BYTE_ENCODING)
            PNO=int.from_bytes(buf[10:14],_BYTE_ENCODING)
            PNL=int.from_bytes(buf[14:16],_BYTE_ENCODING)
            F=int.from_bytes(buf[16:20],_BYTE_ENCODING)
            SN=buf[-PNO:].decode(_STRING_ENCODING).replace('..\\','..\\'*dir_name.count('/'))
            PN=buf[-PNO-PNL:-PNO].decode(_STRING_ENCODING).replace('..\\','..\\'*dir_name.count('/'))
            if len(file_context)!=len(file_name):
                SN+='\\'.join(file_context.split('/'))
                PN+='\\'.join(file_context.split('/'))
            if '?' not in SN+PN:
                NSN=os.path.normpath(os.path.join(dire,SN))
                NPN=os.path.normpath(os.path.join(dire,PN))
            else:
                NSN=SN
                NPN=SN
            if (NSN==file_name)|(NPN==file_name):
                raise NTStatusReparsePointNotResolved()
            return T+len(SNL.to_bytes(2,_BYTE_ENCODING)+PNO.to_bytes(4,_BYTE_ENCODING)+PNL.to_bytes(2,_BYTE_ENCODING)+F.to_bytes(4,_BYTE_ENCODING)+(NPN+NSN).encode(_STRING_ENCODING)).to_bytes(4,_BYTE_ENCODING)+len(NPN.encode(_STRING_ENCODING)).to_bytes(2,_BYTE_ENCODING)+len(NSN.encode(_STRING_ENCODING)).to_bytes(4,_BYTE_ENCODING)+len(NPN.encode(_STRING_ENCODING)).to_bytes(2,_BYTE_ENCODING)+F.to_bytes(4,_BYTE_ENCODING)+(NPN+NSN).encode(_STRING_ENCODING)
        else:
            return buf
    @operation
    def get_reparse_point(self,file_context,file_name):
        if self.s.winattrs[file_context]&attrtoATTR(bin(FILE_ATTRIBUTE.FILE_ATTRIBUTE_REPARSE_POINT)[2:]):
            return self.s.readfile(file_context,0,self.s.trunfile(file_context))
        raise NTStatusNotAReparsePoint()
    @operation
    def set_reparse_point(self,file_context,file_name,buf):
        self.s.trunfile(file_context,len(buf))
        self.s.writefile(file_context,0,buf)
        self.s.winattrs[file_context]|=attrtoATTR(bin(FILE_ATTRIBUTE.FILE_ATTRIBUTE_REPARSE_POINT)[2:])
    @operation
    def delete_reparse_point(self,file_context,file_name,buf):
        if self.s.winattrs[file_context]&attrtoATTR(bin(FILE_ATTRIBUTE.FILE_ATTRIBUTE_REPARSE_POINT)[2:]):
            self.s.trunfile(file_context,0)
            self.s.winattrs[file_context]^=attrtoATTR(bin(FILE_ATTRIBUTE.FILE_ATTRIBUTE_REPARSE_POINT)[2:])
        else:
            raise NTStatusNotAReparsePoint()
    @operation
    def get_stream_info(self,file_context,buffer,length,p_bytes_transferred):
        pass
def create_file_system(path,mountpoint,sectorsize,label='',prefix='',verbose=True,debug=False,testing=False):
    if debug:
        enable_debug_log()
    logging.basicConfig(stream=sys.stdout,level=logging.INFO)
    if verbose:
        logging.root.level=logging.INFO
    else:
        logging.root.level=logging.NOTSET
    #The avast workaround is not necessary with drives
    #Also, it is not compatible with winfsp-tests
    mountpoint=Path(mountpoint)
    is_drive=mountpoint.parent==mountpoint
    reject_irp_prior_to_transact0=not is_drive and not testing
    operations=SpaceFSOperations(path,sectorsize,label)
    fs=FileSystem(
        str(mountpoint),
        operations,
        sector_size=512,
        sectors_per_allocation_unit=operations.s.sectorsize//512,
        volume_creation_time=int(time()*10000000+116444736000000000),
        volume_serial_number=0,
        file_info_timeout=1000,
        case_sensitive_search=1,
        case_preserved_names=1,
        unicode_on_disk=1,
        persistent_acls=1,
        reparse_points=1,
        reparse_points_access_check=1,
        named_streams=1,
        post_cleanup_when_modified_only=1,
        um_file_context_is_user_context2=1,
        file_system_name='SpaceFS',
        prefix=prefix,
        debug=debug,
        reject_irp_prior_to_transact0=reject_irp_prior_to_transact0,
        wsl_features=1,
        #security_timeout_valid=1,
        #security_timeout=10000,
    )
    return fs
def main(path,mountpoint,sectorsize,label,prefix,verbose,debug):
    fs=create_file_system(path,mountpoint,sectorsize,label,prefix,verbose,debug)
    try:
        print('Starting FS')
        fs.start()
        print('FS started, keep it running forever')
        while True:
            result=input('Toggle read-only flag (r) Toggle Verbose (v) Change MountPoint (m) Quit (q)?: ').lower()
            if result=='r':
                if fs.operations.read_only==True:
                    fs.operations.read_only=False
                    fs.restart(read_only_volume=False)
                else:
                    fs.operations.read_only=True
                    fs.restart(read_only_volume=True)
            elif result=='v':
                if logging.root.level!=logging.NOTSET:
                    logging.root.level=logging.NOTSET
                else:
                    logging.root.level=logging.INFO
            elif result=='m':
                fs.mountpoint=input('New MountPoint: ')
                fs.restart()
            elif result=='q':
                break
    finally:
        print('Stopping FS')
        fs.stop()
        fs.operations.s.deletefile('/')
        fs.operations.s.simptable(F=True)
        print('FS stopped')
if __name__=='__main__':
    multiprocessing.freeze_support()
    parser=argparse.ArgumentParser()
    parser.add_argument('path')
    parser.add_argument('mountpoint')
    parser.add_argument('-s','--sectorsize',type=int,default=-1)
    parser.add_argument('-v','--verbose',action='store_true')
    parser.add_argument('-d','--debug',action='store_true')
    parser.add_argument('-l','--label',type=str, default='')
    parser.add_argument('-p','--prefix',type=str, default='')
    args=parser.parse_args()
    main(args.path,args.mountpoint,args.sectorsize,args.label,args.prefix,args.verbose,args.debug)
