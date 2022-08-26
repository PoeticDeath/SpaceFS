import os
import shutil
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
    locstr=''
    for i in locbytes:
        locstr+=dmap[i]
    return locstr.replace(' ','')
def encode(locstr):
    locbytes=b''
    locstr+=' '*(len(locstr)%2)
    for i in [locstr[o:o+2] for o in range(0,len(locstr),2)]:
        locbytes+=emap[i].to_bytes(1,'big')
    return locbytes
class SpaceFS():
    def __init__(self):
        self.diskname='SpaceFS.bin'
        self.disksize=os.path.getsize(self.diskname)
        if self.disksize==0:
            self.disksize=shutil.disk_usage(self.diskname)[0]
        self.disk=open(self.diskname,'rb+')
        self.filecount=int.from_bytes(self.disk.read(4),'big')
        self.sectorsize=2**(int.from_bytes(self.disk.read(1),'big')+9)
        self.sectorcount=self.disksize//self.sectorsize
        self.filenames=[self.disk.read(256).replace(b'\x00',b'').decode() for i in range(0,self.filecount) if self.disk.seek(-256*i-256,2)]
        self.disk.seek(5)
        self.table=decode(self.disk.read(self.sectorsize-5)).split('.')
        if self.table[-1]==len(self.table[-1])*'0':
            self.table[-1]=''
        self.table='.'.join(self.table)
        self.disk.seek(0)
    def readtable(self):
        tmp=[i.split(',') for i in self.table.split('.')[:-1]]
        tmplst=[]
        for i in tmp:
            tmplstpart=[]
            for u in i:
                u=u.split('-')
                try:
                    [u[0],u[1]]
                    try:
                        tmplstpart+=[int(u[0])]
                    except ValueError:
                        tmplstpart+=[u[0]]
                    for o in range(int(u[0].split(';')[0])+1,int(u[1].split(';')[0])):
                        tmplstpart+=[o]
                    try:
                        tmplstpart+=[int(u[1])]
                    except ValueError:
                        tmplstpart+=[u[1]]
                except IndexError:
                        if ';' in u[0]:
                            tmplstpart+=[u[0]]
                        else:
                            try:
                                tmplstpart+=[int(u[0])]
                            except ValueError:
                                pass
                except ValueError:
                        pass
            tmplst+=[tmplstpart]
        return tmplst
    def findnewpart(self,i):
        i=i.split(';')
        try:
            try:
                self.part[int(i[0])]+=[int(i[1]),int(i[2])]
            except KeyError:
                self.part[int(i[0])]=[int(i[1]),int(i[2])]
        except IndexError:
            pass
    def multipart(self):
        for i in self.part:
            self.part[i]=sorted(self.part[i])
            for o in self.part[i]:
                if self.part[i].count(o)>1:
                    while self.part[i].count(o)!=0:
                        self.part[i].pop(self.part[i].index(o))
            try:
                if self.part[i][0]==0:
                    if self.part[i][1]==self.sectorsize:
                        del self.part[i]
            except IndexError:
                pass
    def findnewblock(self,part):
        table=self.table
        table=[i for i in table.replace(',','.').split('.') if i]
        if len(table)==0:
            return 0
        if part:
            self.part={}
            parttable=[i for i in table if ';' in i]
            for i in parttable:
                if '-' in i:
                    i=i.split('-')
                    for o in i:
                        self.findnewpart(o)
                else:
                    self.findnewpart(i)
            while True:
                try:
                    self.multipart()
                except RuntimeError:
                    continue
                break
            for i in self.part:
                self.part[i]=[list(range(self.part[i][o],self.part[i][o+1])) for o in range(0,len(self.part[i]),2)]
                tmp=[]
                for o in self.part[i]:
                    tmp+=o
                self.part[i]=[]
                for o in range(0,self.sectorsize+1):
                    if o not in tmp:
                        self.part[i]+=[o]
                tmp=[]
                d=True
                for o in range(min(self.part[i]),max(self.part[i])):
                    if o not in self.part[i]:
                        if not d:
                            tmp+=[o]
                        d=True
                    else:
                        if d:
                            tmp+=[o]
                        d=False
                if len(tmp)%2!=0:
                    tmp+=[self.sectorsize]
                self.part[i]=tmp
        lst=[]
        for i in table:
            if '-' in i:
                p=i.split('-')
                lst+=list(range(int(p[0]),int(p[1])))
            else:
                if int(i.split(';')[0]) not in lst:
                    lst+=[int(i.split(';')[0])]
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
            try:
                rold=int(i[0].split(';')[0])-2
            except AttributeError:
                rold=i[0]-2
            if len(i)==1:
                lst+=str(i[0])
            else:
                try:
                    if int(i[0].split(';')[0])+1!=i[1]:
                        lst+=str(i[0])+','
                except AttributeError:
                    if i[0]+1!=i[1]:
                        lst+=str(i[0])+','
            for o in i[1:]:
                if type(o)==str:
                    y=int(o.split(';')[0])
                else:
                    y=o
                try:
                    if int(old.split(';')[0])==y-1:
                        if rold+2!=y:
                            tmp=str(old)+','
                            if lst[-len(tmp):]==tmp:
                                lst=lst[:-len(tmp)]
                                try:
                                    if lst[-1]==',':
                                        lst=lst[:-1]
                                except IndexError:
                                    pass
                            lst+=str(old)+'-'
                        rold=int(old.split(';')[0])
                        old=o
                    else:
                        if rold+1==old:
                            lst+=str(old)+','+str(o)+','
                        else:
                            lst+=str(o)+','
                        rold=int(old.split(';')[0])
                        old=o
                except AttributeError:
                    if old==y-1:
                        if rold+2!=y:
                            tmp=str(old)+','
                            if lst[-len(tmp):]==tmp:
                                lst=lst[:-len(tmp)]
                                try:
                                    if lst[-1]==',':
                                        lst=lst[:-1]
                                except IndexError:
                                    pass
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
        self.disk.seek(5)
        elst=encode(lst)
        self.disk.write(elst+b'\x00'*(self.sectorsize-5-len(elst)))
        self.disk.flush()
        self.disk.seek(5)
        self.table=decode(self.disk.read(self.sectorsize-5)).split('.')
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
        self.table=''
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
        if start+amount>self.trunfile(filename):
            return
        i=lst[0]
        if type(i)==int:
            self.disk.seek(i*self.sectorsize+self.sectorsize+(start%self.sectorsize))
            data+=self.disk.read(self.sectorsize-(start%self.sectorsize))
        else:
            self.disk.seek(int(i.split(';')[0])*self.sectorsize+self.sectorsize+(start%self.sectorsize)+int(i.split(';')[1]))
            data+=self.disk.read(int(i.split(';')[2])-int(i.split(';')[1]))
        for i in lst[1:]:
            if type(i)==int:
                self.disk.seek(i*self.sectorsize+self.sectorsize)
                data+=self.disk.read(self.sectorsize)
            else:
                self.disk.seek(int(i.split(';')[0])*self.sectorsize+self.sectorsize+int(i.split(';')[1]))
                data+=self.disk.read(int(i.split(';')[2])-int(i.split(';')[1]))
        self.disk.seek(0)
        return data[:amount]
    def trunfile(self,filename,size=None):
        table=self.table.split('.')
        lst=self.readtable()[self.filenames.index(filename)]
        if size==None:
            if len(lst)!=0:
                s=(len(lst)-1)*self.sectorsize
                try:
                    tlst=lst[-1].split(';')
                    return s+int(tlst[2])-int(tlst[1])
                except AttributeError:
                    return s+self.sectorsize
            return 0
        lst=lst[:(size+self.sectorsize-1)//self.sectorsize]
        if len(lst)==0:
            if size%self.sectorsize!=0:
                lst=[str(self.findnewblock(False))+';0;'+str(size%self.sectorsize)]
        else:
            if size%self.sectorsize!=0:
                try:
                    tlst=lst[-1].split(';')[1]
                    lst[-1]=','+str(lst[-1]).split(';')[0]+';'+tlst+';'+str(int(tlst)+size%self.sectorsize)
                except AttributeError:
                    lst[-1]=','+str(lst[-1])+';0;'+str(size%self.sectorsize)
        nlst=''
        for i in lst:
            nlst+=str(i)
        table[self.filenames.index(filename)]=nlst
        self.table='.'.join(table)
        self.simptable()
    def writefile(self,filename,start,data):
        if filename not in self.filenames:
            raise FileNotFoundError
        end=(start+len(data))//self.sectorsize+1
        lst=self.readtable()[self.filenames.index(filename)]
        minblocks=(start+len(data))//self.sectorsize
        m=0
        c=(start+len(data))%self.sectorsize
        if c!=0:
            m+=1
        odata=None
        while minblocks-m>len(lst):
            tlst=self.table.split('.')
            try:
                if ';' in tlst[self.filenames.index(filename)][-1]:
                    tmp=tlst[self.filenames.index(filenames)][-1].split(';')
                    self.disk.seek(int(tmp[0])*self.sectorsize+self.sectorsize)
                    odata=self.disk.read(self.sectorsize)[int(tmp[1]):int(tmp[2])]
                    d=tlst[self.filenames.index(filename)].index(tlst[self.filenames.index(filename)][-1])
                    tlst[self.filenames.index(filename)]=','.join(tlst[self.filenames.index(filename)].split(',')[:-1])
            except IndexError:
                pass
            if len(lst)==0:
                tlst[self.filenames.index(filename)]+=str(self.findnewblock(False))
            else:
                tlst[self.filenames.index(filename)]+=','+str(self.findnewblock(False))
            self.table='.'.join(tlst)
            lst=self.readtable()[self.filenames.index(filename)]
            if c!=0:
                m=1
        try:
            n=self.readtable()[self.filenames.index(filename)][-1].split(';')
            if int(n[2])-int(n[1])!=c:
                m=1
        except AttributeError:
            pass
        except IndexError:
            pass
        if m==1:
            f=self.findnewblock(True)
            try:
                for i in self.part:
                    for o in [self.part[i][p:p+2] for p in range(0,len(self.part[i]),2)]:
                        if len(o)==2:
                            for p in self.filenames:
                                try:
                                    n=self.readtable()[self.filenames.index(p)][-1].split(';')
                                    if (int(n[0])==i)&(int(n[2])==o[0]):
                                        if o[1]-o[0]>=c:
                                            f=[i,o[0],o[0]+c]
                                            break
                                    if type(f)==list:
                                        break
                                except IndexError:
                                    pass
                    if type(f)!=list:
                        break
            except AttributeError:
                pass
            if type(f)!=list:
                f=[f,0,c]
            tlst=self.table.split('.')
            if len(lst)==minblocks:
                tlst[self.filenames.index(filename)]=','.join(tlst[self.filenames.index(filename)].split(',')[:-1])
            if len(lst)==0:
                tlst[self.filenames.index(filename)]+=str(f[0])+';'+str(f[1])+';'+str(f[2])
            else:
                tlst[self.filenames.index(filename)]+=','+str(f[0])+';'+str(f[1])+';'+str(f[2])
            self.table='.'.join(tlst)
            lst=self.readtable()[self.filenames.index(filename)]
        if odata!=None:
            self.disk.seek(self.readtable()[self.filenames.index(filename)][d]*self.sectorsize+self.sectorsize+int(tmp[1]))
            self.disk.write(odata)
        st=start-(start//self.sectorsize*self.sectorsize)
        data=[data[:self.sectorsize-st]]+[data[i:i+self.sectorsize] for i in range(self.sectorsize-st,len(data),self.sectorsize)]
        for i in enumerate(lst[start//self.sectorsize:end]):
            u=0
            if type(i[1])==str:
                u=int(i[1].split(';')[1])
            if i[0]==0:
                try:
                    self.disk.seek(int(i[1].split(';')[0])*self.sectorsize+self.sectorsize+st+u)
                except AttributeError:
                    self.disk.seek(i[1]*self.sectorsize+self.sectorsize+st+u)
            else:
                try:
                    self.disk.seek(int(i[1].split(';')[0])*self.sectorsize+self.sectorsize+u)
                except AttributeError:
                    self.disk.seek(i[1]*self.sectorsize+self.sectorsize+u)
            self.disk.write(data[i[0]])
        self.disk.flush()
        self.disk.seek(0)
