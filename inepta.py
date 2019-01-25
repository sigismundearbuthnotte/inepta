import os
import sys
import re

#subdirs
rootSubDir=sys.argv[1]
tablesSubDir=rootSubDir+"/tables"#base subdirectory for tables
modelSubDir=rootSubDir+"/models"
exeSubDir=rootSubDir+"/exe"
outputSubDir=rootSubDir+"/output"

#dicts, sets etc.
modelInfos={}

#classes
class modelInfo(object):#persistent data for a model
    def __init__(self):
        self.name=""
        self.isArrayed=True
        self.isDataDriven=False
        self.numElts=0#for non-data-driven
        self.allVariants=[]#list of all combinations
        self.startField=""#which data field gives -elapsed
        self.termField=""#which data field gives term o/s
        self.dataFieldInfos={}#for data-driven only
        self.phases={}#indexed by name, returns dict of calcInfoObjects
        self.tableInfos={}

class dataFieldInfo(object):#covers derived fields as well
    def __init__(self):
        self.name = ""
        self.type=""
        self.arraySize=0
        self.expression=""#raw expression for derived

class calcInfoObject:
    def __init__(self):
        self.name = ""
        self.type="real"
        self.stores=0
        self.isArrayed=False
        self.numDims=1
        self.dimSizes=[]
        self.storeAtRebase=False
        self.code=[]
        self.initialisation=""

class tableInfoObject:
    def __init__(self):
        self.name = ""
        self.dims=[]
        self.basis="SINGLE"

#clear temp subdirectory
tempSubDir=rootSubDir+"/temp"
for fl in os.listdir(tempSubDir):
    os.remove(tempSubDir+"/"+fl)

#eliminate white space,capitalise,check if it's a comment and split on multiple delimiters
def nwscap(l,splits):
    l=l.strip()
    l=l.replace(" ","")
    l=l.replace("\t","")
    ls=[l]
    for c in range(0,len(splits)):
        ls1=[ll.split(splits[c]) for ll in ls]
        ls=[it for sl in ls1 for it in sl]
    return (ls,not(l[0:2]=="//" or l==""),[ll.upper() for ll in ls])#bool is whether it's a comment or empty

def readBasicModelInfo(mfn):
    mi=modelInfo()
    ift = open(mfn, 'r')
    section=""
    for l in ift.readlines():
        (ls, c,lsu) = nwscap(l, "=:,")
        if c:
            if ls[0][0] == "[":
                section = lsu[0][1:len(lsu[0]) - 1]
                continue
            if ls[0]=="###":
                ci=calcInfoObject()
                section="CALC"
                firstLine=True
                for i in range(0,len(ls)):
                    if lsu[i]=="REBASE":
                        ci.storeAtRebase=True
                    if lsu[i]=="STORE":
                        if ls[i+1].isnumeric():
                            ci.stores = int(ls[i + 1])
                        else:
                            ci.stores=-1
                    if lsu[i]=="ARRAYED":
                        (ll,_,_)=nwscap(ls[i+1],"[]")
                        ci.isArrayed=True
                        ci.numDims=len(ll)
                        ci.dimSizes=[int(lll) for lll in ll]
                    if lsu[i]=="TYPE":
                        ci.type=ls[i+1]
                continue
            if section=="BASIC":
                if lsu[0]=="NAME":
                    mi.name=ls[1]
                if lsu[0] == "ARRAYED":
                    if ls[1].isnumeric():
                        mi.isArrayed=True
                        mi.numElts=int(ls[1])
                    if lsu[1]=="DATA":
                        mi.isArrayed=True
                        mi.isDataDriven=True
                if lsu[0]=="TERM":
                    mi.termField=ls[1]
                if lsu[0]=="START":
                    mi.startField=ls[1]
            if section == "DATA" or section == "DERIVED":
                df=dataFieldInfo()
                df.name=ls[0]
                if  not ls[1].__contains__("["):#arrayed?
                    df.type=ls[1]
                else:
                    (ll,_,_)=nwscap(ls[1],"[]")
                    df.type=ll[0]
                    df.arraySize=int(ll[1])
                mi.dataFieldInfos[df.name]=df
            if section == "DERIVED":
                df.expression=ls[2]
            if section=="PHASE":
                if lsu[0]=="NAME":
                    currPhase={}
                    mi.phases[ls[1]]=currPhase#disc of calInfoObjects
            if section =="CALC":
                if lsu[0]=="INITIALISE":
                    ci.initialisation=l
                else:
                    if firstLine:
                        firstLine=False
                        currPhase[ls[0]]=ci
                        ci.name=ls[0]
                    ci.code.append(l)
            if section == "TABLES":
                t=tableInfoObject()
                inDims=False
                for i in range(0, len(ls)):
                    if lsu[i]=="BASIS":
                        t.basis=lsu[i+1]
                        inDims=False
                    if inDims:
                        dim=ls[i]
                        if dim[0]=="(":
                            dim=dim[1:]
                        if dim[len(dim)-1]==")":
                            dim=dim[0:len(dim)-1]
                        t.dims.append(dim)
                    if lsu[i]=="NAME":
                        t.name=ls[i]
                    if lsu[i]=="DIMS":
                        inDims=True
                mi.tableInfos[t.name]=t
    ift.close()
    return mi

#read basic model information
modelInfoFile=sys.argv[2]
ift = open(modelSubDir + "/" + modelInfoFile+".model", 'r')
for l in ift.readlines():
    (ls,c,lsu)=nwscap(l,"=")
    if c:
        #mode
        if lsu[0]=="MODE":
            isDependent=lsu[1]=="DEPENDENT"
        if lsu[0]=="MODEL":
            modelInfos[lsu[1]]=readBasicModelInfo(modelSubDir + "/" + ls[1] + ".model")

    #create dict of model infos
ift.close()
