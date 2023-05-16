import os
import struct
import shutil
from time import time
charmap='0123456789-,.; '
emap={}
dmap={}
p=0
for i in charmap:
    for o in charmap:
        emap[i+o]=p
        dmap[p]=i+o
        p+=1
def decode(locbytes):
    return ''.join([dmap[i] for i in locbytes]).replace(' ','')
def encode(locstr):
    locstr+=' '*(len(locstr)%2)
    locbytes=bytearray()
    [locbytes.append(emap[locstr[i:i+2]]) for i in range(0,len(locstr),2)]
    return locbytes
def isint(i):
    return type(i)==int
class RawDisk():
    def __init__(self,disk):
        self.disk=disk
        self.loc=0
    def seek(self,loc):
        self.loc=loc
        return self.disk.seek(loc//512*512)
    def read(self,amount):
        data=self.disk.read((self.loc%512+amount+511)//512*512)[self.loc%512:self.loc%512+amount]
        self.seek(self.loc+amount)
        return data
    def write(self,buf):
        loc=self.loc
        self.seek(self.loc//512*512)
        p1=self.read(loc%512)
        self.seek(loc+len(buf))
        p3=self.read(512-(loc+len(buf))%512)
        self.seek(loc)
        self.disk.write(p1+buf+p3)
        self.seek(loc+len(buf))
        return len(buf)
    def flush(self):
        return self.disk.flush()
    def close(self):
        return self.disk.close()
class SpaceFS():
    def __init__(self,disk):
        c=None
        self.diskname=disk
        self.disksize=os.path.getsize(self.diskname)
        if self.disksize==0:
            try:
                self.disksize=shutil.disk_usage(self.diskname)[0]
            except OSError:
                import wmi
                c=wmi.WMI()
                try:
                    [drive]=c.Win32_DiskDrive(Index=int(self.diskname[17:]))
                    self.disksize=int(drive.size)
                except ValueError:
                    for i in os.popen('powershell -Command "get-partition | fl -Property AccessPaths,DiskNumber,PartitionNumber"').read().split('\n\n')[1:-2]:
                        if self.diskname in i:
                            break
                    i='\n'.join(i.split('\n')[1:]).replace('Number      : ',' #').replace('\nPartitionNumber : ',', Partition #').split('#')
                    disk=i[1].split(',')[0]
                    diskstyle={}
                    for o in os.popen('powershell -Command "get-disk | fl -Property Number,PartitionStyle"').read().split('\n\n')[1:-2]:
                        o=o.split(':')
                        diskstyle[o[1].split('\n')[0].strip()]=o[2].strip()
                    if diskstyle[disk]=='MBR':
                        i[2]=str(int(i[2])-1)
                    elif diskstyle[disk]=='GPT':
                        i[2]=str(int(i[2])-2)
                    else:
                        print('Unsupported Disk Format!')
                        exit()
                    i='#'.join(i)
                    for p in os.popen('powershell -Command "wmic partition get DeviceID,Size"').read().split('\n\n')[1:-2]:
                        if i in p:
                            break
                    self.disksize=int(p.replace(i,'').strip())
        if c!=None:
            self.rawdisk=open(self.diskname,'rb+',buffering=512)
            self.flushdisk=open(self.diskname,'rb+',buffering=512)
            self.disk=RawDisk(self.rawdisk)
            self.fdisk=RawDisk(self.flushdisk)
        else:
            self.disk=open(self.diskname,'rb+')
            self.fdisk=open(self.diskname,'rb+')
        self.sectorsize=2**(int.from_bytes(self.disk.read(1),'big')+9)
        self.tablesectorcount=int.from_bytes(self.disk.read(4),'big')+2
        self.sectorcount=self.disksize//self.sectorsize-self.tablesectorcount
        s=self.disk.read(self.sectorsize*self.tablesectorcount-5).split(b'\xfe')
        t=s[0].split(b'\xff')
        s=b'\xfe'.join(s[1:])+b'\xfe'
        self.table=decode(t[0]).split('.')
        self.filenameslst=[i.decode() for i in t[1:-1]]
        self.filenamesdic={}
        self.symlinks={}
        for i in enumerate(self.filenameslst):
            filename=i[1].split('*')
            self.filenamesdic[filename[0]]=i[0]
            for o in filename[1:]:
                self.symlinks[o]=filename[0]
        if self.table[-1]==len(self.table[-1])*'0':
            self.table[-1]=''
        self.table='.'.join(self.table)
        self.disk.seek(0)
        self.missinglst=[]
        self.oldsimptable=self.table
        self.oldreadtable=[]
        self.oldredtable=[]
        self.oldsectorcount=self.sectorcount
        self.part={}
        try:
            self.findnewblock(part=True)
        except IndexError:
            pass
        self.flst=self.readtable()
        self.times=bytearray(s[:len(self.filenamesdic)*24])
        self.guids={}
        self.modes={}
        self.winattrs={}
        for i in enumerate(self.filenameslst):
            ofs=(len(self.filenamesdic)*24)+(i[0]*11)
            filename=i[1].split('*')[0]
            self.guids[filename]=(int.from_bytes(s[ofs:ofs+3],'big'),int.from_bytes(s[ofs+3:ofs+5],'big'))
            self.modes[filename]=int.from_bytes(s[ofs+5:ofs+7],'big')
            self.winattrs[filename]=int.from_bytes(s[ofs+7:ofs+11],'big')
        self.simptable()
    def readtable(self):
        if self.oldreadtable==self.table:
            return self.oldredtable
        self.oldreadtable=self.table
        tmp=[i.split(',') for i in self.table.split('.')[:-1]]
        tmplst=[]
        for i in tmp:
            tmplstpart=[]
            for u in i:
                u=u.split('-')
                try:
                    [u[0],u[1]]
                    tmplstpart.append(int(u[0]))
                    tmplstpart.extend(list(range(int(u[0].split(';')[0])+1,int(u[1].split(';')[0]))))
                    try:
                        tmplstpart.append(int(u[1]))
                    except ValueError:
                        tmplstpart.append(u[1])
                except IndexError:
                        if ';' in u[0]:
                            tmplstpart.append(u[0])
                        else:
                            try:
                                tmplstpart.append(int(u[0]))
                            except ValueError:
                                pass
            tmplst.append(tmplstpart)
        self.oldredtable=tmplst
        return tmplst
    def findnewpart(self,i):
        i=i.split(';')
        try:
            try:
                self.part[int(i[0])].extend([int(i[1]),int(i[2])])
            except KeyError:
                self.part[int(i[0])]=[int(i[1]),int(i[2])]
        except IndexError:
            pass
    def findnewblock(self,part=False,pop=False,whole=False):
        if part:
            t=True
            for i in self.part:
                if len(self.part[i])!=0:
                    t=False
            if t:
                self.part={}
            if self.part=={}:
                table=self.table
                table=[i for i in table.replace(',','.').split('.') if i]
                parttable=[i for i in table if ';' in i]
                for i in parttable:
                    if '-' in i:
                        i=i.split('-')
                        for o in i:
                            self.findnewpart(o)
                    else:
                        self.findnewpart(i)
                t=[]
                for i in self.part:
                    tmp=set()
                    tpt=set()
                    self.part[i]=sorted(self.part[i])
                    for o in self.part[i]:
                        if o not in tpt:
                            tmp.add(o)
                            tpt.add(o)
                        else:
                            if o in tmp:
                                tmp.remove(o)
                    self.part[i]=sorted(list(tmp))
                    if self.part[i][0]==0:
                        self.part[i].pop(0)
                    else:
                        self.part[i]=[0]+self.part[i]
                    if len(self.part[i])%2!=0:
                        self.part[i].append(self.sectorsize)
                    if self.part[i]==[self.sectorsize]*2:
                        t.append(i)
                for i in t:
                    self.part.pop(i)
        if self.sectorcount<self.oldsectorcount:
            self.missinglst=list(filter(lambda x:x<self.sectorcount,self.missinglst))
            self.oldsectorcount=self.sectorcount
        if len(self.missinglst)==0:
            lst=set()
            table=self.table
            table=[i for i in table.replace(',','.').split('.') if i]
            if len(table)==0:
                if not whole:
                    return 0
            for i in table:
                if '-' in i:
                    p=i.split('-')
                    [lst.add(i) for i in list(range(int(p[0].split(';')[0]),int(p[1].split(';')[0])+1))]
                else:
                    if int(i.split(';')[0]) not in lst:
                        lst.add(int(i.split(';')[0]))
            self.missinglst.extend(set(range(0,self.sectorcount)).difference(lst))
        else:
            try:
                self.missinglst.sort()
            except TypeError:
                self.missinglst=sorted(list(filter(isint,self.missinglst)))
        if pop:
            return self.missinglst.pop(0)
        if whole:
            return self.missinglst
        return self.missinglst[0]
    @classmethod
    def smptable(self,args):
        tmplst,filenameslst,guids,modes,winattrs,symlinks,times=args
        lst=''
        for i in tmplst:
            if len(i)==0:
                lst+='.'
                continue
            old=i[0]
            try:
                rold=int(i[0].split(';')[0])-2
            except AttributeError:
                rold=i[0]-2
            if len(i)==1:
                lst+=str(i[0])
            for o in i[1:]:
                if type(o)==str:
                    y=int(o.split(';')[0])
                else:
                    y=o
                if old==y-1:
                    if rold+2!=y:
                        tmp=str(old)+','
                        if lst[-len(tmp):]==tmp:
                            lst=lst[:-len(tmp)]
                        lst+=str(old)+'-'
                    rold=old
                    old=o
                else:
                    lst+=str(old)+','+str(o)+','
                    rold=old
                    old=o
            try:
                rold=int(rold.split(';')[0])
            except AttributeError:
                pass
            try:
                old=int(old.split(';')[0])
            except AttributeError:
                pass
            if rold+1==old==y:
                lst+=str(o)
            if lst[-1]==',':
                lst=lst[:-1]
            lst+='.'
        elst=encode(lst)
        filenames=bytearray(b'\xff')
        guidsmodes=bytearray()
        for i in filenameslst:
            i=i.split('*')[0]
            guidsmodes.extend(guids[i][0].to_bytes(3,'big')+guids[i][1].to_bytes(2,'big')+modes[i].to_bytes(2,'big')+winattrs[i].to_bytes(4,'big'))
            for p in symlinks:
                if symlinks[p]==i.split('*')[0]:
                    i+='*'+p
            filenames.extend(i.encode()+b'\xff')
        filenames.extend(b'\xfe'+times+guidsmodes)
        return elst,filenames
    def simptable(self,F=False,elst=None,filenames=None):
        if (elst==None)|(filenames==None):
            if (self.oldsimptable==self.table)&(not F):
                return
            elst,filenames=self.smptable([self.readtable(),self.filenameslst,self.guids,self.modes,self.winattrs,self.symlinks,self.times])
        self.tablesectorcount=(len(elst+filenames)+self.sectorsize-1)//self.sectorsize-1
        self.fdisk.seek(1)
        self.fdisk.write(self.tablesectorcount.to_bytes(4,'big')+elst+filenames)
        self.tablesectorcount+=2
        self.sectorcount=self.disksize//self.sectorsize-self.tablesectorcount
        self.fdisk.flush()
        self.disk.flush()
        self.oldsimptable=self.table
    def createfile(self,filename,mode):
        c=[i for i in self.symlinks if filename.startswith(i+'/')]
        if len(c)>0:
            filename=filename.replace(c[0],self.symlinks[c[0]],1)
        if filename in self.filenamesdic:
            raise FileExistsError
        if os.name=='nt':
            gid=uid=545
        else:
            gid=uid=1000
        if len(self.part)+self.tablesectorcount>=self.disksize//self.sectorsize-10:
            if self.findnewblock()>=self.sectorcount+1:
                raise IndexError
        self.guids[filename]=(gid,uid)
        self.modes[filename]=mode
        self.winattrs[filename]=2048
        self.filenamesdic[filename]=len(self.filenamesdic)
        self.filenameslst.append(filename)
        self.table+='.'
        self.flst.append([])
        self.times.extend(struct.pack('!d',time())*3)
        if len(self.part)+self.tablesectorcount>=self.disksize//self.sectorsize-10:
            self.simptable()
    def deletefile(self,filename,block=False):
        c=[i for i in self.symlinks if filename.startswith(i+'/')]
        if len(c)>0:
            filename=filename.replace(c[0],self.symlinks[c[0]],1)
        if (filename in self.symlinks)&(block==False):
            del self.symlinks[filename]
            return
        if filename in self.symlinks.values():
            for i in list(self.symlinks.keys()):
                if self.symlinks[i]==filename:
                    del self.symlinks[i]
        if filename not in self.filenamesdic:
            raise FileNotFoundError
        index=self.filenamesdic[filename]
        mlst=self.flst.pop(index)
        try:
            if type(mlst[-1])==str:
                m=mlst.pop(-1).split(';')
                try:
                    for i in range(1,3):
                        if int(m[i]) in self.part[int(m[0])]:
                            self.part[int(m[0])].remove(int(m[i]))
                        else:
                            self.part[int(m[0])].append(int(m[i]))
                    self.part[int(m[0])].sort()
                    if self.part[int(m[0])]==[0,self.sectorsize]:
                        del self.part[int(m[0])]
                        self.missinglst.append(int(m[0]))
                except KeyError:
                    u=self.table.count(','+m[0]+';')+self.table.count('.'+m[0]+';')
                    if u==1:
                        self.missinglst.append(int(m[0]))
                    elif u>1:
                        self.part[int(m[0])]=[int(m[1]),int(m[2])]
        except IndexError:
            pass
        self.missinglst.extend(mlst)
        self.table='.'.join([','.join([str(o) if type(o)==int else o for o in i])+',' for i in self.flst])+'.'
        self.filenameslst.pop(index)
        del self.filenamesdic[filename]
        del self.guids[filename]
        del self.modes[filename]
        del self.winattrs[filename]
        for i in enumerate(self.filenameslst[index:]):
            self.filenamesdic[i[1].split('*')[0]]=i[0]+index
        del self.times[index*24:index*24+24]
    def renamefile(self,oldfilename,newfilename):
        c=[i for i in self.symlinks if oldfilename.startswith(i+'/')]
        if oldfilename in self.symlinks:
            self.symlinks[newfilename]=self.symlinks[oldfilename]
            del self.symlinks[oldfilename]
            if newfilename in self.filenamesdic:
                self.deletefile(newfilename,block=True)
            return
        if len(c)>0:
            oldfilename=oldfilename.replace(c[0],self.symlinks[c[0]],1)
            newfilename=newfilename.replace(c[0],self.symlinks[c[0]],1)
        if oldfilename not in self.filenamesdic:
            raise FileNotFoundError
        if newfilename in self.filenamesdic:
            self.deletefile(newfilename)
        if self.findnewblock()>=self.sectorcount+1:
            raise IndexError
        oldindex=self.filenamesdic[oldfilename]
        self.filenameslst[oldindex]=newfilename
        del self.filenamesdic[oldfilename]
        self.filenamesdic[newfilename]=oldindex
        self.guids[newfilename]=self.guids[oldfilename]
        del self.guids[oldfilename]
        self.modes[newfilename]=self.modes[oldfilename]
        del self.modes[oldfilename]
        self.winattrs[newfilename]=self.winattrs[oldfilename]
        del self.winattrs[oldfilename]
    def readfile(self,filename,start,amount):
        c=[i for i in self.symlinks if filename.startswith(i+'/')]
        if len(c)>0:
            filename=filename.replace(c[0],self.symlinks[c[0]],1)
        if filename in self.symlinks:
            filename=self.symlinks[filename]
        index=self.filenamesdic[filename]
        filesize=self.trunfile(filename)
        if index==-1:
            raise FileNotFoundError
        if start>=filesize:
            raise EOFError
        amount=min(filesize,amount+start)-start
        end=(start+amount+self.sectorsize-1)//self.sectorsize
        lst=self.flst[self.filenamesdic[filename]][start//self.sectorsize:end]
        data=b''
        try:
            i=lst[0]
        except IndexError:
            return
        if type(i)==int:
            self.disk.seek(self.disksize-(i*self.sectorsize-(start%self.sectorsize)+self.sectorsize))
            data+=self.disk.read(min(self.sectorsize-(start%self.sectorsize),amount))
        else:
            self.disk.seek(self.disksize-(int(i.split(';')[0])*self.sectorsize-(start%self.sectorsize)-int(i.split(';')[1])+self.sectorsize))
            data+=self.disk.read(min(int(i.split(';')[2])-int(i.split(';')[1]),amount))
        for i in lst[1:]:
            if type(i)==int:
                self.disk.seek(self.disksize-(i*self.sectorsize+self.sectorsize))
                data+=self.disk.read(min(self.sectorsize,amount))
            else:
                self.disk.seek(self.disksize-(int(i.split(';')[0])*self.sectorsize-int(i.split(';')[1])+self.sectorsize))
                data+=self.disk.read(min(int(i.split(';')[2])-int(i.split(';')[1]),amount))
        self.times[index*24:index*24+8]=struct.pack('!d',time())
        return data[:amount]
    def trunfile(self,filename,size=None):
        c=[i for i in self.symlinks if filename.startswith(i+'/')]
        if len(c)>0:
            filename=filename.replace(c[0],self.symlinks[c[0]],1)
        if filename in self.symlinks:
            filename=self.symlinks[filename]
        try:
            index=self.filenamesdic[filename]
        except KeyError:
            raise ValueError
        try:
            lst=self.flst[index]
        except IndexError:
            if size==0:
                return 0
            self.flst=self.readtable()
            lst=self.flst[index]
        if size==None:
            if len(lst)!=0:
                s=(len(lst)-1)*self.sectorsize
                try:
                    tlst=lst[-1].split(';')
                    return s+int(tlst[2])-int(tlst[1])
                except AttributeError:
                    return s+self.sectorsize
            return 0
        s=self.trunfile(filename)
        if size<s:
            if len(lst)>0:
                try:
                    if type(lst[-1])==str:
                        m=lst[-1].split(';')
                        try:
                            for i in range(1,3):
                                if int(m[i]) in self.part[int(m[0])]:
                                    self.part[int(m[0])].remove(int(m[i]))
                                else:
                                    self.part[int(m[0])].append(int(m[i]))
                            self.part[int(m[0])].sort()
                            if self.part[int(m[0])]==[0,self.sectorsize]:
                                del self.part[int(m[0])]
                                self.missinglst.append(int(m[0]))
                        except KeyError:
                            pass
                        l=lst.pop(-1)
                except TypeError:
                    pass
            newmiss=lst[(size+self.sectorsize-1)//self.sectorsize:]
            try:
                p=lst[(size+self.sectorsize-1)//self.sectorsize-1]
                m=l.split(';')
                u=self.table.count(','+m[0]+';')+self.table.count('.'+m[0]+';')
                if u==1:
                    newmiss.append(int(m[0]))
                elif u>1:
                    if int(m[0]) not in self.part:
                        self.part[int(m[0])]=[int(m[1]),int(m[2])]
            except IndexError:
                p=l
            except UnboundLocalError:
                if type(lst[-1])==int:
                    newmiss.append(lst[-1])
            lst=lst[:(size+self.sectorsize-1)//self.sectorsize-1]
            if type(p)==int:
                o=size%self.sectorsize
                if o!=0:
                    lst.append(str(p)+';0;'+str(o))
            elif type(p)==str:
                lst.append(';'.join(p.split(';')[:2])+';'+str(int(p.split(';')[2])-(s%self.sectorsize-size%self.sectorsize)))
            self.flst[index]=lst
            nlst=','.join([str(i) for i in lst])
            table=self.table.split('.')
            table[index]=nlst
            self.table='.'.join(table)
            self.missinglst.extend(newmiss)
        if size>s:
            if self.writefile(filename,s,bytes(size-s),True)==0:
                return 0
        self.times[index*24+8:index*24+16]=struct.pack('!d',time())
    def writefile(self,filename,start,data,T=False):
        c=[i for i in self.symlinks if filename.startswith(i+'/')]
        if len(c)>0:
            filename=filename.replace(c[0],self.symlinks[c[0]],1)
        if filename in self.symlinks:
            filename=self.symlinks[filename]
        if filename not in self.filenamesdic:
            raise FileNotFoundError
        index=self.filenamesdic[filename]
        lst=self.flst[index]
        minblocks=(start+len(data))//self.sectorsize
        m=0
        c=(start+len(data))%self.sectorsize
        partfull=True
        try:
            if type(lst[-1])==str:
                prtfull=lst[-1].split(';')
                if int(prtfull[2])-int(prtfull[1])>=c:
                    partfull=False
        except IndexError:
            pass
        if partfull:
            try:
                d=self.findnewblock()
            except IndexError:
                return 0
            if d>self.sectorcount:
                self.findnewblock(part=True)
                full=True
                for i in self.part:
                    prt=self.part[i]
                    if prt[1]-prt[0]<=c:
                        full=False
                        break
                if full==True:
                    return 0
        if c!=0:
            m=1
        try:
            n=lst[-1].split(';')
            if int(n[2])-int(n[1])!=c:
                m=1
            else:
                m=2
        except AttributeError:
            pass
        except IndexError:
            pass
        h=None
        odata=None
        if (m!=2)&(start+len(data)>self.trunfile(filename)):
            tlst=self.table.split('.')
            try:
                self.findnewblock(part=True)
            except IndexError:
                return 0
            if ';' in tlst[index].split(',')[-1]:
                h=self.flst[index].pop()
                try:
                    self.part[int(h.split(';')[0])].append(int(h.split(';')[1]))
                    try:
                        self.part[int(h.split(';')[0])].remove(int(h.split(';')[2]))
                    except ValueError:
                        self.part[int(h.split(';')[0])].append(int(h.split(';')[2]))
                    self.part[int(h.split(';')[0])].sort()
                except KeyError:
                    self.part[int(h.split(';')[0])]=[0,self.sectorsize]
                tlst[index]=','.join(tlst[index].split(',')[:-1])
                self.table='.'.join(tlst)
        elif m==2:
            m=1
        while minblocks>len(lst):
            tlst=self.table.split('.')
            try:
                block=self.findnewblock(pop=True)
            except IndexError:
                return 0
            if len(lst)==0:
                tlst[index]=str(block)
            else:
                tlst[index]+=','+str(block)
            self.table='.'.join(tlst)
            self.flst[index].append(block)
            if c!=0:
                m=1
        if m==1:
            if self.trunfile(filename)<start+len(data):
                f=self.findnewblock(part=True)
                if c==0:
                    try:
                        self.missinglst.pop(self.missinglst.index(f))
                    except ValueError:
                        pass
                    f=[f,0,self.sectorsize]
                else:
                    try:
                        for i in self.part:
                            for o in [self.part[i][p:p+2] for p in range(0,len(self.part[i]),2)]:
                                l=True
                                if len(o)==1:
                                    o.append(o[0]+1)
                                    l=False
                                if o[1]-o[0]>=c:
                                    f=[i,o[0],o[0]+c]
                                    if h!=None:
                                        if (i!=int(h.split(';')[0]))|(o[0]!=int(h.split(';')[1])):
                                            u=int(h.split(';')[1])
                                            self.disk.seek(self.disksize-(int(h.split(';')[0])*self.sectorsize+self.sectorsize-u))
                                            odata=self.disk.read(int(h.split(';')[2])-int(h.split(';')[1]))
                                    if l:
                                        if o[1]-o[0]==c:
                                            self.part[i].remove(o[0])
                                            self.part[i].remove(o[1])
                                        else:
                                            self.part[i][self.part[i].index(o[0])]=o[0]+c
                                    else:
                                        self.part[i].remove(o[0])
                                if type(f)==list:
                                    break
                            if type(f)==list:
                                break
                    except AttributeError:
                        pass
                if type(f)!=list:
                    try:
                        self.missinglst.pop(self.missinglst.index(f))
                    except ValueError:
                        pass
                    self.part[f]=[c,self.sectorsize]
                    f=[f,0,c]
                tlst=self.table.split('.')
                if len(lst)==minblocks:
                    tlst[index]=','.join(tlst[index].split(','))
                if (f[1]==0)&(f[2]==self.sectorsize):
                    e=f[0]
                else:
                    e=str(f[0])+';'+str(f[1])+';'+str(f[2])
                if len(lst)==0:
                    tlst[index]=str(e)
                else:
                    tlst[index]+=','+str(e)
                self.flst[index].append(e)
                self.table='.'.join(tlst)
        st=start-(start//self.sectorsize*self.sectorsize)
        end=(start+len(data)+self.sectorsize-1)//self.sectorsize
        if not T:
            data=[data[:self.sectorsize-st]]+[data[i:i+self.sectorsize] for i in range(self.sectorsize-st,len(data),self.sectorsize)]
            for i in enumerate(self.flst[index][start//self.sectorsize:end]):
                u=0
                if type(i[1])==str:
                    u=int(i[1].split(';')[1])
                if i[0]==0:
                    if odata!=None:
                        try:
                            self.disk.seek(self.disksize-(int(i[1].split(';')[0])*self.sectorsize+self.sectorsize-u))
                        except AttributeError:
                            self.disk.seek(self.disksize-(i[1]*self.sectorsize+self.sectorsize-u))
                        self.disk.write(odata)
                    try:
                        self.disk.seek(self.disksize-(int(i[1].split(';')[0])*self.sectorsize+self.sectorsize-st-u))
                    except AttributeError:
                        self.disk.seek(self.disksize-(i[1]*self.sectorsize+self.sectorsize-st-u))
                else:
                    try:
                        self.disk.seek(self.disksize-(int(i[1].split(';')[0])*self.sectorsize+self.sectorsize-u))
                    except AttributeError:
                        self.disk.seek(self.disksize-(i[1]*self.sectorsize+self.sectorsize-u))
                for o in range(0,(len(data[i[0]])+16777215)//16777216):
                    self.disk.write(data[i[0]][o*16777216:o*16777216+16777216])
        self.times[index*24+8:index*24+16]=struct.pack('!d',time())
