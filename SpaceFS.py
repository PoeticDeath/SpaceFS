import os
import shutil
charmap=[('0001','0'),('0010','1'),('0011','2'),('0100','3'),('0101','4'),('0110','5'),('0111','6'),('1000','7'),('1001','8'),('1010','9'),('1011','-'),('1100',','),('1101','.'),('1110',';')]
dmap={}
for char in charmap:
        dmap[char[0]]=char[1]
emap={}
for char in charmap:
        emap[char[1]]=char[0]
def decode(locbytes):
    locbytes=bin(int.from_bytes(locbytes,'big'))[2:]
    locbytes=locbytes.zfill((len(locbytes)+3)//4*4)
    if locbytes == '0000':
        locbytes=''
    return ''.join(dmap.get(c,c) for c in [locbytes[i:i+4] for i in range(0,len(locbytes),4)])
def encode(locstr):
    try:
        c=int(''.join(emap.get(c,c) for c in locstr),2)
    except ValueError:
        c=0
    return c.to_bytes((c.bit_length()+7)//8,'big')
class SpaceFS():
    def __init__(self):
        self.diskname='SpaceFS.bin'
        self.disksize=os.path.getsize(self.diskname)
        if self.disksize==0:
            self.disksize=shutil.disk_usage(self.diskname)[0]
        self.disk=open(self.diskname,'rb+')
        self.filecount=int.from_bytes(self.disk.read(4),'big')
        self.sectorsize=int.from_bytes(self.disk.read(4),'big')
        self.sectorcount=self.disksize//self.sectorsize
        self.filenames=[self.disk.read(256).replace(b'\x00',b'').decode() for i in range(0,self.filecount) if self.disk.seek(-256*i-256,2)]
        self.disk.seek(8)
        self.table=decode(self.disk.read(self.sectorsize-8)).split('.')
        if self.table[-1]==len(self.table[-1])*'0':
            self.table[-1]=''
        self.table='.'.join(self.table)
        self.disk.seek(0)
    def readtable(self):
        tmp=[i.split(',') for i in self.table.replace(';','').split('.')[:-1]]
        tmplst=[]
        for i in tmp:
            tmplstpart=[]
            for u in i:
                u=u.split('-')
                try:
                    for o in range(int(u[0]), int(u[1])+1):
                        tmplstpart+=[o]
                except IndexError:
                        tmplstpart+=[int(u[0])]
                except ValueError:
                        pass
            tmplst+=[tmplstpart]
        return tmplst
    def findnewblock(self):
        table=self.table
        table=[i for i in table.replace(',','.').split('.') if i]
        if len(table)==0:
            return 0
        lst=[]
        for i in table:
            if '-' in i:
                p=i.split('-')
                for o in range(int(p[0]),int(p[1])+1):
                    lst+=[int(o)]
            else:
                lst+=[int(i)]
        lst=sorted(lst)
        for i in range(lst[0],lst[-1]):
            if i not in lst:
                return i
        return max(lst)+1
    def simptable(self):
        tmplst=self.readtable()
        lst=''
        for i in tmplst:
            if len(i)==0:
                lst+='.'
                continue
            old=i[0]
            rold=i[0]-2
            if len(i)==1:
                lst+=str(i[0])
            else:
                if i[0]+1!=i[1]:
                    lst+=str(i[0])+','
            for o in i[1:]:
                if old==o-1:
                    if rold+2!=o:
                        tmp=','+str(old)+','
                        if lst[-len(tmp):]==tmp:
                            lst=lst[:-len(tmp)+1]
                        lst+=str(old)+'-'
                    rold=old
                    old=o
                else:
                    if rold+1==old:
                        lst+=str(old)+','+str(o)+','
                    else:
                        lst+=str(o)+','
                    rold=old
                    old=o
            if rold+1==old==o:
                lst+=str(o)
            if lst[-1]==',':
                lst=lst[:-1]
            lst+='.'
        self.disk.seek(8)
        elst=encode(lst)
        self.disk.write(elst+b'\x00'*(self.sectorsize-8-len(elst)))
        self.disk.flush()
        self.disk.seek(8)
        self.table=decode(self.disk.read(self.sectorsize-8)).split('.')
        if self.table[-1]==len(self.table[-1])*'0':
            self.table[-1]=''
        self.table='.'.join(self.table)
        self.disk.seek(0)
    def writefilenames(self):
        for i in enumerate(self.filenames):
            self.disk.seek(-256*i[0]-256,2)
            filename=i[1].encode()
            self.disk.write(b'\x00'*(256-len(filename))+filename)
        self.disk.flush()
        self.disk.seek(0)
    def createfile(self,filename):
        if filename in self.filenames:
            raise FileExistsError
        self.filecount+=1
        self.disk.seek(0)
        self.disk.write(self.filecount.to_bytes(4,'big'))
        self.disk.flush()
        self.filenames+=[filename]
        self.writefilenames()
        self.table+='.'
        self.simptable()
        self.disk.seek(0)
    def deletefile(self,filename):
        if filename not in self.filenames:
            raise FileNotFoundError
        self.filecount-=1
        self.disk.seek(0)
        self.disk.write(self.filecount.to_bytes(4,'big'))
        self.disk.flush()
        lst=self.readtable()
        lst.pop(self.filenames.index(filename))
        for i in lst:
            for o in i:
                self.table+=str(o)
            self.table+='.'
        self.simptable()
        self.filenames.pop(self.filenames.index(filename))
        self.writefilenames()
        self.disk.seek(0)
    def renamefile(self,oldfilename,newfilename):
        if oldfilename not in self.filenames:
            raise FileNotFoundError
        if newfilename in self.filenames:
            raise FileExistsError
        self.filenames[self.filenames.index(oldfilename)]=newfilename
        self.writefilenames()
    def readfile(self,filename,start,amount):
        if filename not in self.filenames:
            raise FileNotFoundError
        lst=self.readtable()[self.filenames.index(filename)][start//self.sectorsize:(start+amount)//self.sectorsize+1]
        data=b''
        for i in lst:
            self.disk.seek(i*self.sectorsize+self.sectorsize)
            data+=self.disk.read(self.sectorsize)
        self.disk.seek(0)
        return data[:amount]
    def writefile(self,filename,start,data):
        if filename not in self.filenames:
            raise FileNotFoundError
        end=(start+len(data))//self.sectorsize+1
        lst=self.readtable()[self.filenames.index(filename)]
        minblocks=(start+len(data))//self.sectorsize+1
        while minblocks>len(lst):
            tlst=self.table.split('.')
            if len(lst)==0:
                tlst[self.filenames.index(filename)]+=str(self.findnewblock())
            else:
                tlst[self.filenames.index(filename)]+=','+str(self.findnewblock())
            self.table='.'.join(tlst)
            lst=self.readtable()[self.filenames.index(filename)]
        self.simptable()
        st=start-(start//self.sectorsize*self.sectorsize)
        fdata=[data[:self.sectorsize-st]]
        data=[data[i:i+self.sectorsize] for i in range(st,len(data),self.sectorsize)]
        if st>0:
            data=fdata+data
        for i in enumerate(lst[start//self.sectorsize:end]):
            if i[0]==0:
                self.disk.seek(i[1]*self.sectorsize+self.sectorsize+st)
            else:
                self.disk.seek(i[1]*self.sectorsize+self.sectorsize)
            self.disk.write(data[i[0]])
        self.disk.flush()
        self.disk.seek(0)
