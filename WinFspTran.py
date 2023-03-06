#A file system implemented on top of winfspy. Useful for efficiently storing files.

import sys
import logging
import argparse
import threading
from functools import wraps
from pathlib import Path

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
)

from winfspy.plumbing.security_descriptor import SecurityDescriptor

def attrtoATTR(attr):
    ATTR=0
    for i in [(-2,32768),(-1,4096),(-3,128),(-6,2048),(-5,8192)]:
        try:
            if attr[i[0]]=='1':
                ATTR+=i[1]
        except IndexError:
            pass
    return ATTR
def ATTRtoattr(ATTR):
    attr=0
    for i in [(-16,FILE_ATTRIBUTE.FILE_ATTRIBUTE_HIDDEN),(-13,FILE_ATTRIBUTE.FILE_ATTRIBUTE_READONLY),(-8,FILE_ATTRIBUTE.FILE_ATTRIBUTE_SYSTEM),(-12,FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE),(-14,FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY)]:
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
        self.s.createfile('/',16877)
        self.s.winattrs['/']=attrtoATTR(bin(FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY)[2:])
        if '' not in self.s.filenamesdic:
            self.s.createfile('',448)
            self.s.writefile('',0,'O:WDG:WDD:P(A;;FA;;;WD)'.encode())
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
    def autosimp(self):
        while True:
            with self._thread_lock:
                self.s.simptable()
            sleep(60)
    @operation
    def get_volume_info(self):
        avail=len(self.s.findnewblock(whole=True))
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
            raise NTStatusObjectNameNotFound()
        if file_name[1:] not in self.s.filenamesdic:
            self.s.createfile(file_name[1:],448)
            self.s.writefile(file_name[1:],0,self.s.readfile(dir_name[1:],0,self.s.trunfile(dir_name[1:])))
        try:
            SD=SecurityDescriptor.from_string(self.s.readfile(file_name[1:],0,self.s.trunfile(file_name[1:])).decode())
        except RuntimeError:
            self.s.trunfile(file_name[1:],0)
            self.s.writefile(file_name[1:],0,self.s.readfile(dir_name[1:],0,self.s.trunfile(dir_name[1:])))
            SD=SecurityDescriptor.from_string(self.s.readfile(file_name[1:],0,self.s.trunfile(file_name[1:])).decode())
        return (ATTRtoattr(bin(self.s.winattrs[file_name])[2:]),SD.handle,SD.size)
    @operation
    def create(self,file_name,create_options,granted_access,file_attributes,security_descriptor,allocation_size):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        file_name=file_name.replace('\\','/')
        dir_name='/'.join(file_name.split('/')[:-1])
        if file_name in self.s.filenamesdic:
            raise NTStatusObjectNameCollision()
        try:
            if bin(file_attributes)[2:].zfill(8)[-5]=='1':
                self.s.createfile(file_name,16877)
            else:
                self.s.createfile(file_name,448)
            self.s.createfile(file_name[1:],448)
            SD=security_descriptor.to_string()
            if 'D:P' in SD:
                self.s.writefile(file_name[1:],0,SD.encode())
            else:
                self.s.writefile(file_name[1:],0,self.s.readfile(dir_name[1:],0,self.s.trunfile(dir_name[1:])))
            self.s.winattrs[file_name]|=attrtoATTR(bin(file_attributes)[2:])
        except IndexError:
            raise NTStatusEndOfFile()
        self.allocsizes[file_name]=allocation_size
        return file_name
    @operation
    def get_security(self,file_context):
        dir_name='/'.join(file_context.split('/')[:-1])
        if file_context[1:] not in self.s.filenamesdic:
            self.s.createfile(file_context[1:],448)
            self.s.writefile(file_context[1:],0,self.s.readfile(dir_name[1:],0,self.s.trunfile(dir_name[1:])))
        return SecurityDescriptor.from_string(self.s.readfile(file_context[1:],0,self.s.trunfile(file_context[1:])).decode())
    @operation
    def set_security(self,file_context,security_information,modification_descriptor):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        dir_name='/'.join(file_context.split('/')[:-1])
        if file_context[1:] not in self.s.filenamesdic:
            self.s.createfile(file_context[1:],448)
            self.s.writefile(file_context[1:],0,self.s.readfile(dir_name[1:],0,self.s.trunfile(dir_name[1:])))
        SD=SecurityDescriptor.from_string(self.s.readfile(file_context[1:],0,self.s.trunfile(file_context[1:])).decode())
        if security_information!=1:
            SD=SD.evolve(security_information,modification_descriptor)
            SD=SD.to_string()
        else:
            SD=SD.to_string()
            NSD=SecurityDescriptor.from_cpointer(modification_descriptor).to_string()
            NSD=NSD+NSD.replace('O:','G:')
            SD=NSD+SD[SD.index('D:'):]
        if 'D:P' not in SD:
            SD=SD.replace('D:','D:P',1)
        self.s.trunfile(file_context[1:],0)
        self.s.writefile(file_context[1:],0,SD.encode())
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
                if self.read_directory(file_name,'..')!=[]:
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
                            self.s.renamefile(i[1:],i[1:].replace(file_name[1:],new_file_name[1:],1))
                            self.allocsizes[i.replace(file_name,new_file_name,1)]=self.allocsizes[i]
                            del self.allocsizes[i]
                        except IndexError:
                            raise NTStatusEndOfFile()
            try:
                self.s.renamefile(file_name,new_file_name)
                self.s.renamefile(file_name[1:],new_file_name[1:])
                self.allocsizes[new_file_name]=self.allocsizes[file_name]
                del self.allocsizes[file_name]
            except IndexError:
                raise NTStatusEndOfFile()
    @operation
    def open(self,file_name,create_options,granted_access):
        file_name=file_name.replace('\\','/')
        if file_name not in self.s.filenamesdic:
            raise NTStatusObjectNameNotFound()
        return file_name
    @operation
    def close(self,file_context):
        pass
    def gfi(self,file_context):
        index=self.s.filenamesdic[file_context]
        t=[int(struct.unpack('!d',self.s.times[index*24:index*24+24][i:i+8])[0]*10000000+116444736000000000) for i in range(0,24,8)]
        t[0]+=2
        t[1]+=2
        t[2]+=2
        if file_context not in self.allocsizes:
            self.allocsizes[file_context]=(self.s.trunfile(file_context)+self.s.sectorsize-1)//self.s.sectorsize*self.s.sectorsize
        return {'file_attributes':ATTRtoattr(bin(self.s.winattrs[file_context])[2:]),
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
        index=self.s.filenamesdic[file_context]
        if file_attributes!=FILE_ATTRIBUTE.INVALID_FILE_ATTRIBUTES:
            self.s.winattrs[file_context]=attrtoATTR(bin(file_attributes)[2:])
        if creation_time:
            self.s.times=self.s.times[:index*24+16]+struct.pack('!d',(creation_time-116444736000000000)/10000000)+self.s.times[index*24+24:]
        if last_access_time:
            self.s.times=self.s.times[:index*24]+struct.pack('!d',(last_access_time-116444736000000000)/10000000)+self.s.times[index*24+8:]
        if (last_write_time)|(change_time):
            self.s.times=self.s.times[:index*24+8]+struct.pack('!d',(last_write_time-116444736000000000)/10000000)+self.s.times[index*24+16:]
        return self.gfi(file_context)
    @operation
    def set_file_size(self,file_context,new_size,set_allocation_size):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        if set_allocation_size:
            self.allocsizes[file_context]=new_size
            if new_size<self.s.trunfile(file_context):
                self.s.trunfile(file_context,new_size)
        else:
            if self.s.trunfile(file_context,new_size)==0:
                raise NTStatusEndOfFile()
    @operation
    def can_delete(self,file_context,file_name):
        if self.s.modes[file_context]==16877:
            if self.read_directory(file_context,'..')!=[]:
                raise NTStatusDirectoryNotEmpty()
    def read_directory(self,file_context,marker):
        c=[i for i in self.s.symlinks if (file_context.startswith(i+'/'))|(file_context==i)]
        if len(c)>0:
            file_context=file_context.replace(c[0],self.s.symlinks[c[0]],1)
        if file_context[-1]!='/':
            file_context+='/'
        dirents=[{'file_name':'.',**self.gfi('/'.join(file_context.split('/')[:-1]))},{'file_name':'..',**self.gfi('/'.join(file_context.split('/')[:-2]))}]
        for i in list(self.s.filenamesdic.keys())+list(self.s.symlinks.keys()):
            if i!='/':
                if i.startswith(file_context):
                    if file_context.count('/')==i.count('/'):
                        c=i[1:].split('/')[-1]
                        if {'file_name':c,**self.gfi(i)} not in dirents:
                            dirents+=[{'file_name':c,**self.gfi(i)}]
                    if i[-1]=='/':
                        if file_context.count('/')+1==i.count('/'):
                            tmp=i[1:].split('/')[-2]
                            if {'file_name':tmp,**self.gfi(i)} not in dirents:
                                tmp=i[1:].split('/')[-2]
                                if {'file_name':tmp,**self.gfi(i)} not in dirents:
                                    dirents+=[{'file_name':tmp,**self.gfi(i)}]
                        if file_context.count('/')+1<=i.count('/'):
                            tmp=i.split('/')[file_context.count('/')]
                            if {'file_name':tmp,**self.gfi(i)} not in dirents:
                                d='/'.join(i.split('/')[:file_context.count('/')+1])+'/'
                                dirents+=[{'file_name':tmp,**self.gfi(i)}]
        dirents=sorted(dirents,key=lambda x:x['file_name'])
        if marker is None:
            return dirents
        for i,dirent in enumerate(dirents):
            if dirent['file_name']==marker:
                return dirents[i+1:]
    @operation
    def get_dir_info_by_name(self,file_context,file_name):
        if file_context[-1]!='/':
            file_context+='/'
        if file_context+file_name not in self.s.filenamesdic:
            raise NTStatusObjectNameNotFound()
        return {'file_name':file_context+file_name,**self.gfi(file_context+file_name)}
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
        if self.s.modes[file_context]==16877:
            if self.read_directory(file_context,'..')!=[]:
                raise NTStatusDirectoryNotEmpty()
        else:
            self.s.winattrs[file_context]|=attrtoATTR(bin(FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE)[2:])
        index=self.s.filenamesdic[file_context]
        t=time()
        FspCleanupDelete=0x01
        FspCleanupAllocationSize=0x02
        FspCleanupSetLastAccessTime=0x20
        FspCleanupSetLastWriteTime=0x40
        FspCleanupSetChangeTime=0x80
        if flags&FspCleanupDelete:
            self.s.deletefile(file_context)
            self.s.deletefile(file_context[1:])
            for i in list(self.s.filenamesdic.keys()):
                if i.startswith(file_context+':'):
                    self.s.deletefile(i)
                    self.s.deletefile(i[1:])
        if flags&FspCleanupAllocationSize:
            self.allocsizes[file_context]=self.s.trunfile(file_context)
        if (flags&FspCleanupSetLastAccessTime)&(not flags&FspCleanupDelete):
            self.s.times=self.s.times[:index*24]+struct.pack('!d',t)+self.s.times[index*24+8:]
        if ((flags&FspCleanupSetLastWriteTime)|(flags&FspCleanupSetChangeTime))&(not flags&FspCleanupDelete):
            self.s.times=self.s.times[:index*24+8]+struct.pack('!d',t)+self.s.times[index*24+16:]
    @operation
    def overwrite(self,file_context,file_attributes,replace_file_attributes,allocation_size):
        if self.read_only:
            raise NTStatusMediaWriteProtected()
        if replace_file_attributes:
            self.s.winattrs[file_context]=attrtoATTR(bin(file_attributes)[2:])
        else:
            self.s.winattrs[file_context]|=attrtoATTR(bin(file_attributes)[2:])
        self.s.trunfile(file_context,allocation_size)
        index=self.s.filenamesdic[file_context]
        t=time()
        self.s.times=self.s.times[:index*24]+struct.pack('!d',t)+self.s.times[index*24+8:]
        self.s.times=self.s.times[:index*24+8]+struct.pack('!d',t)+self.s.times[index*24+16:]
    @operation
    def flush(self,file_context):
        pass
    @operation
    def resolve_reparse_points(self,file_name,reparse_point_index,resolve_last_path_component,p_io_status,buffer,p_size):
        pass
    @operation
    def get_reparse_point(self,file_context,file_name,buffer,p_size):
        pass
    @operation
    def set_reparse_point(self,file_context,file_name,buffer,size):
        pass
    @operation
    def delete_reparse_point(self,file_context,file_name,buffer,size):
        pass
    @operation
    def get_stream_info(self,file_context,buffer,length,p_bytes_transferred):
        pass
def create_file_system(path,mountpoint,sectorsize,label='',prefix='',verbose=True,debug=False,testing=False):
    if debug:
        enable_debug_log()
    logging.root.level=logging.NOTSET
    if verbose:
        logging.basicConfig(stream=sys.stdout,level=logging.INFO)
        logging.root.level=logging.INFO
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
            result=input('Set read-only flag (y/n/q)?: ').lower()
            if result=='y':
                fs.operations.read_only=True
                fs.restart(read_only_volume=True)
            elif result=='n':
                fs.operations.read_only=False
                fs.restart(read_only_volume=False)
            elif result=='q':
                break
    finally:
        print('Stopping FS')
        fs.operations.s.deletefile('/')
        fs.operations.s.simptable(F=True)
        fs.stop()
        print('FS stopped')
if __name__=='__main__':
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
