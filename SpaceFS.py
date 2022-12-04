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
        s=self.disk.read(self.sectorsize*self.tablesectorcount-5).split(b'\xfe')
        t=s[0].split(b'\xff')
        self.table=decode(t[0]).split('.')
        self.filenameslst=[i.decode() for i in t[1:-1]]
        self.filenamesdic={}
        for i in enumerate(self.filenameslst):
            self.filenamesdic[i[1]]=i[0]
        if self.table[-1]==len(self.table[-1])*'0':
            self.table[-1]=''
        self.table='.'.join(self.table)
        self.disk.seek(0)
        self.missinglst=[]
        self.oldsimptable=self.table
        self.oldreadtable=[]
        self.oldredtable=[]
        self.part={}
        self.findnewblock(part=True)
        self.flst=self.readtable()
        self.times=s[1][:len(self.filenamesdic)*24]
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
        self.oldredtable=tmplst
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
                            tmp.remove(o)
                    self.part[i]=list(tmp)
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
        if len(self.missinglst)==0:
            lst=[]
            table=self.table
            table=[i for i in table.replace(',','.').split('.') if i]
            if len(table)==0:
                if not whole:
                    return 0
                lst=[-1]
            for i in table:
                if '-' in i:
                    p=i.split('-')
                    lst+=list(range(int(p[0].split(';')[0]),int(p[1].split(';')[0])+1))
                else:
                    if int(i.split(';')[0]) not in lst:
                        lst+=[int(i.split(';')[0])]
            self.missinglst+=set(range(0,min(max(lst)+10000,self.sectorcount))).difference(set(lst))
        if pop:
            return self.missinglst.pop(0)
        if whole:
            return len(self.missinglst)
        return self.missinglst[0]
    def simptable(self):
        table=self.table
        if self.oldsimptable==table:
            return
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
        for i in self.filenameslst:
            filenames+=i.encode()+b'\xff'
        filenames+=b'\xfe'+self.times
        self.tablesectorcount=(len(elst+filenames)+self.sectorsize-1)//self.sectorsize-1
        self.disk.seek(1)
        self.disk.write(self.tablesectorcount.to_bytes(4,'big')+elst+filenames)
        self.tablesectorcount+=1
        self.sectorcount=self.disksize//self.sectorsize-self.tablesectorcount
        self.disk.flush()
        self.oldsimptable=table
    def createfile(self,filename):
        if filename in self.filenamesdic:
            raise FileExistsError
        self.filenameslst+=[filename]
        self.filenamesdic[filename]=len(self.filenamesdic)
        self.table+='.'
        self.flst+=[[]]
        self.times+=struct.pack('!d',time())*3
    def deletefile(self,filename):
        if filename not in self.filenamesdic:
            raise FileNotFoundError
        index=self.filenamesdic[filename]
        mlst=self.flst.pop(index)
        try:
            if type(mlst[-1])==str:
                m=mlst.pop(-1).split(';')
                try:
                    self.part[int(m[0])]+=[int(m[1]),int(m[2])]
                except KeyError:
                    self.part[int(m[0])]=[int(m[1]),int(m[2])]
        except IndexError:
            pass
        self.missinglst+=mlst
        self.table='.'.join([','.join(i) for i in self.flst])+'.'
        self.filenameslst.pop(index)
        del self.filenamesdic[filename]
        for i in enumerate(self.filenameslst[index:]):
            self.filenamesdic[i[1]]=i[0]+index
        self.times=self.times[:index*24]+self.times[index*24+24:]
    def renamefile(self,oldfilename,newfilename):
        if oldfilename not in self.filenamesdic:
            raise FileNotFoundError
        if newfilename in self.filenamesdic:
            raise FileExistsError
        oldindex=self.filenamesdic[oldfilename]
        self.filenameslst[oldindex]=newfilename
        del self.filenamesdic[oldfilename]
        self.filenamesdic[newfilename]=oldindex
    def readfile(self,filename,start,amount):
        index=self.filenamesdic[filename]
        if index==-1:
            raise FileNotFoundError
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
        self.times=self.times[:index*24]+struct.pack('!d',time())+self.times[index*24+8:]
        return data[:amount]
    def trunfile(self,filename,size=None):
        try:
            index=self.filenamesdic[filename]
        except KeyError:
            [].index(filename)
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
        if size<self.trunfile(filename):
            if len(lst)>0:
                try:
                    if type(lst[-1])==str:
                        part=lst[-1].split(';')
                        try:
                            self.part[int(part[0])]=sorted(self.part[int(part[0])]+[int(part[1]),int(part[2])])
                        except KeyError:
                            self.part[int(part[0])]=[int(part[1]),int(part[2])]
                        lst=lst[:-1]
                except TypeError:
                    pass
            newmiss=lst[(size+self.sectorsize-1)//self.sectorsize:]
            lst=lst[:(size+self.sectorsize-1)//self.sectorsize]
            self.flst[index]=lst
            nlst=','.join(lst)
            table=self.table.split('.')
            table[index]=nlst
            self.table='.'.join(table)
            self.missinglst+=newmiss
        if size>self.trunfile(filename):
            self.writefile(filename,self.trunfile(filename),bytes(size-self.trunfile(filename)),True)
        self.times=self.times[:index*24+8]+struct.pack('!d',time())+self.times[index*24+16:]
    def writefile(self,filename,start,data,T=False):
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
                if int(prtfull[1])-int(prtfull[0])>=c:
                    partfull=False
        except IndexError:
            pass
        if (self.findnewblock()>self.sectorcount)&partfull:
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
        odata=None
        if (m!=2)&(minblocks>len(lst)):
            tlst=self.table.split('.')
            tmp=tlst[index].split(',')[-1]
            if ';' in tmp:
                tmp=tmp.split(';')
                self.disk.seek(-(int(tmp[0])*self.sectorsize+self.sectorsize),2)
                odata=self.disk.read(self.sectorsize)[int(tmp[1]):int(tmp[2])]
                d=self.flst[index].index(self.readtable()[index][-1])
                self.flst[index].pop()
                tlst[index]=','.join(tlst[index].split(',')[:-1])
                self.table='.'.join(tlst)
        elif m==2:
            m=1
        while minblocks>len(lst):
            tlst=self.table.split('.')
            block=self.findnewblock(pop=True)
            if len(lst)==0:
                tlst[index]=str(block)
            else:
                tlst[index]+=','+str(block)
            self.table='.'.join(tlst)
            self.flst[index]+=[block]
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
                                    o+=[o[0]+1]
                                    l=False
                                if o[1]-o[0]>=c:
                                    f=[i,o[0],o[0]+c]
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
                self.flst[index]+=[e]
                self.table='.'.join(tlst)
        if odata!=None:
            try:
                self.disk.seek(self.disksize-(int(tmp[0])+self.sectorsize))
                self.disk.write(odata[:int(tmp[2])-int(tmp[1])])
            except AttributeError:
                self.disk.seek(self.disksize-(int(self.readtable()[index][d*self.sectorsize+int(tmp[1])])+self.sectorsize))
                self.disk.write(odata)
        st=start-(start//self.sectorsize*self.sectorsize)
        end=(start+len(data)+self.sectorsize-1)//self.sectorsize
        if T:
            data=[data[:self.sectorsize-st]]+[0 for i in range(self.sectorsize-st,len(data)//self.sectorsize*self.sectorsize,self.sectorsize)]
        else:
            data=[data[:self.sectorsize-st]]+[data[i:i+self.sectorsize] for i in range(self.sectorsize-st,len(data),self.sectorsize)]
        for i in enumerate(self.flst[index][start//self.sectorsize:end]):
            u=0
            if type(i[1])==str:
                u=int(i[1].split(';')[1])
            if i[0]==0:
                try:
                    self.disk.seek(self.disksize-(int(i[1].split(';')[0])*self.sectorsize+self.sectorsize-st-u))
                except AttributeError:
                    self.disk.seek(self.disksize-(i[1]*self.sectorsize+self.sectorsize-st-u))
            else:
                try:
                    self.disk.seek(self.disksize-(int(i[1].split(';')[0])*self.sectorsize+self.sectorsize-u))
                except AttributeError:
                    self.disk.seek(self.disksize-(i[1]*self.sectorsize+self.sectorsize-u))
            if type(data[i[0]])==bytes:
                self.disk.write(data[i[0]])
        self.times=self.times[:index*24+8]+struct.pack('!d',time())+self.times[index*24+16:]
        self.disk.flush()
