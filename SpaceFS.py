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
    def __init__(self,disk):
        self.diskname=disk
        self.disksize=os.path.getsize(self.diskname)
        if self.disksize==0:
            self.disksize=shutil.disk_usage(self.diskname)[0]
        self.disk=open(self.diskname,'rb+')
        self.sectorsize=2**(int.from_bytes(self.disk.read(1),'big')+9)
        self.tablesectorcount=int.from_bytes(self.disk.read(4),'big')+1
        self.sectorcount=self.disksize//self.sectorsize-self.tablesectorcount
        t=self.disk.read(self.sectorsize*self.tablesectorcount-5).split(b'\xfe')[0].split(b'\xff')
        self.table=decode(t[0]).split('.')
        self.filenames=[i.decode() for i in t[1:-1]]
        if self.table[-1]==len(self.table[-1])*'0':
            self.table[-1]=''
        self.table='.'.join(self.table)
        self.disk.seek(0)
        self.lst=[]
        self.lstindex=-1
        self.missinglst=[]
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
                    tmplstpart+=list(range(int(u[0].split(';')[0])+1,int(u[1].split(';')[0])))
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
    def findnewblock(self,part=False,pop=False):
        if part:
            table=self.table
            table=[i for i in table.replace(',','.').split('.') if i]
            self.part={}
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
                self.part[i]=sorted(self.part[i])
                for o in self.part[i]:
                    if self.part[i].count(o)>1:
                        tmp.add(o)
                for o in tmp:
                    for p in range(0,self.part[i].count(o)):
                        self.part[i].remove(o)
                if self.part[i][0]==0:
                    self.part[i].pop(0)
                else:
                    self.part[i]=[0]+self.part[i]
                if len(self.part[i])%2!=0:
                    self.part[i]+=[self.sectorsize]
                if self.part[i]==[self.sectorsize]*2:
                    t+=[i]
            for i in t:
                self.part.pop(i)
        if self.missinglst==[]:
            table=self.table
            table=[i for i in table.replace(',','.').split('.') if i]
            if len(table)==0:
                return 0
            lst=[]
            for i in table:
                if '-' in i:
                    p=i.split('-')
                    lst+=list(range(int(p[0].split(';')[0]),int(p[1].split(';')[0])+1))
                else:
                    if int(i.split(';')[0]) not in lst:
                        lst+=[int(i.split(';')[0])]
            self.missinglst+=set(range(0,max(lst)+10000)).difference(set(lst))
        if pop:
            return self.missinglst.pop(0)
        return self.missinglst[0]
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
        elst=encode(lst)
        filenames=b'\xff'
        for i in self.filenames:
            filenames+=i.encode()+b'\xff'
        filenames+=b'\xfe'
        self.disk.seek(5)
        self.disk.write(elst+filenames)
        self.tablesectorcount=(len(elst+filenames)+self.sectorsize-1)//self.sectorsize-1
        self.disk.seek(1)
        self.disk.write(self.tablesectorcount.to_bytes(4,'big'))
        self.tablesectorcount+=1
        self.sectorcount=self.disksize//self.sectorsize-self.tablesectorcount
        self.disk.flush()
        t=self.disk.read(self.sectorsize*self.tablesectorcount-5).split(b'\xfe')[0].split(b'\xff')
        self.table=decode(t[0]).split('.')
        self.filenames=[i.decode() for i in t[1:-1]]
        if self.table[-1]==len(self.table[-1])*'0':
            self.table[-1]=''
        self.table='.'.join(self.table)
        self.disk.seek(0)
        self.lst=[]
        self.lstindex=-1
    def createfile(self,filename):
        if filename in self.filenames:
            raise FileExistsError
        self.filenames+=[filename]
        self.table+='.'
        self.simptable()
    def deletefile(self,filename):
        if filename not in self.filenames:
            raise FileNotFoundError
        lst=self.readtable()
        lst.pop(self.filenames.index(filename))
        self.table='.'
        for i in lst:
            for o in i:
                if self.table[-1]=='.':
                    self.table+=str(o)
                else:
                    self.table+=','+str(o)
            self.table+='.'
        self.table=self.table[1:]
        self.filenames.pop(self.filenames.index(filename))
        self.simptable()
        self.missinglst=[]
    def renamefile(self,oldfilename,newfilename):
        if oldfilename not in self.filenames:
            raise FileNotFoundError
        if newfilename in self.filenames:
            raise FileExistsError
        self.filenames[self.filenames.index(oldfilename)]=newfilename
        self.simptable()
    def readfile(self,filename,start,amount):
        if filename not in self.filenames:
            raise FileNotFoundError
        lst=self.readtable()[self.filenames.index(filename)][start//self.sectorsize:(start+amount)//self.sectorsize+1]
        data=b''
        try:
            i=lst[0]
        except IndexError:
            return
        if type(i)==int:
            self.disk.seek(-(i*self.sectorsize+(start%self.sectorsize)+self.sectorsize),2)
            data+=self.disk.read(self.sectorsize-(start%self.sectorsize))
        else:
            self.disk.seek(-(int(i.split(';')[0])*self.sectorsize+(start%self.sectorsize)-int(i.split(';')[1])+self.sectorsize),2)
            data+=self.disk.read(int(i.split(';')[2])-int(i.split(';')[1]))
        for i in lst[1:]:
            if type(i)==int:
                self.disk.seek(-(i*self.sectorsize+self.sectorsize),2)
                data+=self.disk.read(self.sectorsize)
            else:
                self.disk.seek(-(int(i.split(';')[0])*self.sectorsize-int(i.split(';')[1])+self.sectorsize),2)
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
                lst=[str(self.findnewblock(pop=True))+';0;'+str(size%self.sectorsize)]
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
        self.missinglst=[]
    def writefile(self,filename,start,data):
        if filename not in self.filenames:
            raise FileNotFoundError
        if (self.lst!=[])&(self.lstindex==self.filenames.index(filename)):
            pass
        else:
            self.lst=self.readtable()[self.filenames.index(filename)]
            self.lstindex=self.filenames.index(filename)
        minblocks=(start+len(data))//self.sectorsize
        m=0
        c=(start+len(data))%self.sectorsize
        if c!=0:
            m=1
        try:
            n=self.lst[-1].split(';')
            if int(n[2])-int(n[1])!=c:
                m=1
            else:
                m=2
        except AttributeError:
            pass
        except IndexError:
            pass
        odata=None
        tlst=self.table.split('.')
        tmp=tlst[self.filenames.index(filename)]
        if m!=2:
            if ';' in tmp:
                tmp=tmp.split(';')
                self.disk.seek(-(int(tmp[0])*self.sectorsize+self.sectorsize),2)
                odata=self.disk.read(self.sectorsize)[int(tmp[1]):int(tmp[2])]
                d=self.lst[self.filenames.index(filename)].index(self.readtable()[self.filenames.index(filename)][-1])
                self.lst.pop()
                tlst[self.filenames.index(filename)]=','.join(tlst[self.filenames.index(filename)].split(',')[:-1])
                self.table='.'.join(tlst)
        while minblocks-m>len(self.lst):
            tlst=self.table.split('.')
            block=self.findnewblock(part=False,pop=True)
            if len(self.lst)==0:
                tlst[self.filenames.index(filename)]=str(block)
            else:
                tlst[self.filenames.index(filename)]+=','+str(block)
            self.table='.'.join(tlst)
            self.lst+=[block]
            if c!=0:
                m=1
        if m==1:
            if self.trunfile(filename)<start+len(data):
                f=self.findnewblock(part=True,pop=False)
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
                                if len(o)==1:
                                    o+=[o[0]+1]
                                if o[1]-o[0]>=c:
                                    f=[i,o[0],o[0]+c]
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
                    f=[f,0,c]
                tlst=self.table.split('.')
                if len(self.lst)==minblocks:
                    tlst[self.filenames.index(filename)]=','.join(tlst[self.filenames.index(filename)].split(',')[:-1])
                    self.lst=self.lst[:-1]
                if (f[1]==0)&(f[2]==self.sectorsize):
                    e=f[0]
                else:
                    e=str(f[0])+';'+str(f[1])+';'+str(f[2])
                if len(self.lst)==0:
                    tlst[self.filenames.index(filename)]=str(e)
                else:
                    tlst[self.filenames.index(filename)]+=','+str(e)
                self.lst+=[e]
                self.table='.'.join(tlst)
        if odata!=None:
            try:
                f=self.readtable()[self.filenames.index(filename)][d*self.sectorsize+int(tmp[1])].split(';')
                self.disk.seek(-(int(f[0])+self.sectorsize),2)
                self.disk.write(odata[:int(f[2])-int(f[1])])
            except AttributeError:
                self.disk.seek(-(int(self.readtable()[self.filenames.index(filename)][d*self.sectorsize+int(tmp[1])])+self.sectorsize),2)
                self.disk.write(odata)
        st=start-(start//self.sectorsize*self.sectorsize)
        end=(start+len(data))//self.sectorsize+1
        data=[data[:self.sectorsize-st]]+[data[i:i+self.sectorsize] for i in range(self.sectorsize-st,len(data),self.sectorsize)]
        for i in enumerate(self.lst[start//self.sectorsize:end]):
            u=0
            if type(i[1])==str:
                u=int(i[1].split(';')[1])
            if i[0]==0:
                try:
                    self.disk.seek(-(int(i[1].split(';')[0])*self.sectorsize+self.sectorsize-st-u),2)
                except AttributeError:
                    self.disk.seek(-(i[1]*self.sectorsize+self.sectorsize-st-u),2)
            else:
                try:
                    self.disk.seek(-(int(i[1].split(';')[0])*self.sectorsize+self.sectorsize-u),2)
                except AttributeError:
                    self.disk.seek(-(i[1]*self.sectorsize+self.sectorsize-u),2)
            self.disk.write(data[i[0]])
        self.disk.flush()
        self.disk.seek(0)
