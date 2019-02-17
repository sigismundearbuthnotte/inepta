import os
import sys
import re

#errors
def doErr(errStr,infoStr):
    print(errStr+" "+ infoStr, file=sys.stderr)
    sys.exit()

#constants
nl="\n"
userDefinedFns={"real","exp","sqrt","log","sum","prod","zeros1","zeros2","zeros3","backDisc1","backDisc2","backDisc3","sumprod","sum1","sum2","cumprod","cumsum","udne","interp","maxi","maxr"}
multiBracket={}#lots of []
br="[]"
multiBracket[0]=""
for i in range(1,100):
    multiBracket[i]=br
    br+="[]"
allowableSections=set(["BASIC","ESG","DATA","DERIVED","PHASE","END","TABLES","COMMON"])
allowableBasicParams=set(["NAME","ARRAYED","TERM","START","FORCE","FIRSTPROJECTIONPERIOD","LASTPROJECTIONPERIOD","BATCHSIZEEXTERNAL","BATCHSIZEINTERNAL"])
calcSettings={"STORE":True,"TYPE":True,"__NR":False,"__R":False,"OUTPUT":False,"OVERWRITES":True}#does a further value follow the setting name?
allowablecalcSettings=set(calcSettings.keys())
allowablePhaseSettings=set(["NAME","DIRECTION","START"])
allowableDirections=set(["FORWARDS","BACKWARDS","STATIC"])
allowableTableBases=set(["SINGLE","PREFIX","SUFFIX","SUBDIR"])
allowableTopSections=set(["BASIC","BASES","SUBBASE","REBASING","MODELS","END"])

#subdirs
rootSubDir=sys.argv[1]
dataSubDir=rootSubDir+"/data"
tablesSubDir=rootSubDir+"/tables"#base subdirectory for tables
modelSubDir=rootSubDir+"/models"
exeSubDir=rootSubDir+"/exe"
outputSubDir=rootSubDir+"/output"
libSubDir=rootSubDir+"/library"#base subdirectory for tables

#dicts, sets etc.
modelInfos={}#name->modelInfo
enums={}#name->(dict of names->integer)
bases={}#name->basisInfo
rebaseTimes=[]

#classes
class modelInfo(object):#persistent data for a model
    def __init__(self):
        self.name=""
        self.isArrayed=True
        self.isDataDriven=False
        self.numElts=0#for non-data-driven
        self.startField=""#which data or derived field gives -elapsed
        self.termField=""#which data or derived field gives term o/s
        self.dataFieldInfos={}#includes derived
        self.phases={}#indexed by name, returns dict of calcInfoObjects
        self.phaseDirections={"phase0":"backwards","phase1":"forwards"}
        self.phaseStart={}#name->int/firstprojectionperiod/ previous
        self.tableInfos={}
        self.hasData=False
        self.hasDerived=False
        self.esg={}#only top model should have one of these
        self.forceThese=[]#calcs to force
        self.maxStored=0#excluding store-alls
        self.firstProjectionPeriod=1
        self.lastProjectionPeriod=600
        self.commonCode=[]
        self.batchSizeExternal=1000000
        self.batchSizeInternal=50000
        self.storeAllPosn={}#calc name-> (tuple of store-all index (low,high)).

class dataFieldInfo(object):#covers derived fields as well
    def __init__(self):
        self.name = ""
        self.type=""
        self.arraySize=0
        self.expression=""#raw expression for derived


class tableInfoObject:
    def __init__(self):
        self.name = ""
        self.dims=[]#excludes basis, basis will be added if the next field != "single"
        self.basis="SINGLE"

class calcInfoObject:
    def __init__(self):
        self.name = ""#is concatenation of the fields returned whn returning a tuple
        self.fieldsCalcd=[]#One elt==name where returning one value
        self.lhs=""#for convenience, store the assignment lhs
        self.type="real"
        self.stores=0#number of past elements; -1 means all
        self.isArrayed=False#array within one basis; the difference between this and __NR is that the latter is created by multiple basis runs
        self.numDims=0
        self.dimSizes=[]
        self.code=[]
        self.initialisation=""#initialisation expression
        self.isCall=False
        self.isOutput=False#output from Experience (i.e. what reaches the outside world)
        self.isNonRebase=False#Needs a slot per basis because it's either a cflow from NRs or it's calculated by whole array calc from NR cashflows (once for each NR basis)
        self.overwrites=""#if the preceding is true, what calc does it overwrite.  Can only have an __NR overwriting another __NR
        self.isRebase=False#calculated by whole array calc by rebasing (once for each R basis)

class basisInfoObject:#might be OTT
    def __init__(self):
        self.name=""
        self.isRebase=False
        self.subBases=[]#list of names

#utilities
#eliminate white space,capitalise,check if it's a comment and split on multiple delimiters
def nwscap(l,splits):
    commPos=l.find("//")#find comment
    if commPos>0:
        l=l[0:commPos]
    l=l.strip()
    l=l.replace(" ","")
    l=l.replace("\t","")
    ls=[l]
    for c in range(0,len(splits)):
        ls1=[ll.split(splits[c]) for ll in ls]
        ls=[it for sl in ls1 for it in sl if it!=""]
    return ([ll for ll in ls if ll!=""],not(l[0:2]=="//" or l==""),[ll.upper() for ll in ls if ll!=""])#bool is whether it's a comment or empty

#eliminate EXCESS white space,capitalise,check if it's a comment and split on multiple delimiters
def newscap(l,splits):
    commPos=l.find("//")#find comment
    if commPos>0:
        l=l[0:commPos]
    l=l.strip()
    lOld=""
    while lOld!=l:
        lOld=l
        l=l.replace("  "," ")
    l=l.replace("\t"," ")
    ls=[l]
    for c in range(0,len(splits)):
        ls1=[ll.split(splits[c]) for ll in ls]
        ls=[it for sl in ls1 for it in sl if it!=""]
    return (l,[ll for ll in ls if ll!=""],not(l[0:2]=="//" or l==""),[ll.upper() for ll in ls if ll!=""])#bool is whether it's a comment or empty

#start generating Futhark
numBases=0#1 per basis
numActualBases=0#1 per subbasis
numRebased=0#1 per subbasis
numNonRebased=0#1 per subbasis
off=open(exeSubDir+"/"+"futhark.fut",'w')

#read enum info
ift = open(modelSubDir + "/" + "enums", 'r')
for l in ift.readlines():
    (ls,c,lsu)=nwscap(l,"^")#don't split by splitting on something that will not be there
    if c:
        if lsu[0]=="[END]":
            enums[enumName]=en
            continue
        if ls[0][0]=='[' and lsu[0]!="[END]":
            ecount=0
            enumName=ls[0][1:-1]
            en={}
            continue
        else:
            en[ls[0]]=ecount
            ecount+=1
            continue
ift.close()

def readBasicModelInfo(mfn):
    mi=modelInfo()
    ift = open(mfn, 'r')
    section=""
    for l in ift.readlines():
        (ls, c,lsu) = nwscap(l, "=:,;")
        if c:
            if ls[0][0] == "[":
                oldSection=section
                section = lsu[0][1:len(lsu[0]) - 1]
                if not section in allowableSections:
                    doErr("Unknown section ",ls[0])
                if oldSection!="" and oldSection!="END" and section!="END":
                    doErr("Unterminated section preceding ", ls[0])
                continue
            if l[0:3]=="###":
                if len(ls[0]) >= 4:
                    if l[3] != ',':
                        doErr("Have you forgotten the comma after the ###?", l)
            if ls[0]=="###":
                ci=calcInfoObject()
                section="CALC"
                firstLine=True
                skipItem=False
                for i in range(1,len(ls)):
                    if skipItem:#had a keyword, hence have entered the value following it, so skip that value
                        skipItem=False
                        continue
                    if lsu[i] not in allowablecalcSettings:
                        doErr("Unknown setting for calc: ",l)
                    skipItem=calcSettings[lsu[i]]#do we skip the next item?
                    if lsu[i]=="OUTPUT":
                        ci.isOutput = True
                        ci.stores=-1
                    if lsu[i]=="STORE":
                        if ls[i+1].isnumeric():
                            ci.stores = int(ls[i + 1])
                        elif lsu[i+1]=="ALL":
                            ci.stores=-1
                        else:
                            doErr("Unknown store setting for calc: ",l)
                    if lsu[i]=="TYPE":
                        if lsu[i+1].__contains__("["):
                            (ll, _, llu) = nwscap(ls[i + 1], "[]")
                            ci.isArrayed = True
                            ci.numDims = len(ll)-1
                            isOK = all(map((lambda x: x.isnumeric() or x == "NR" or x == "R"), ll[1:]))
                            if not isOK:
                                doErr("Unknown array bounds for calc: ", l)
                            ci.dimSizes = [(lambda x: int(x) if x.isnumeric() else (
                            numNonRebased if x=="NR" else numRebased))(lll) for lll in ll[1:]]
                            ci.type = ll[0]
                            if ci.type!="real" and ci.type!="int":
                                doErr("Unknown type for calc: ",l)
                        else:
                            ci.type = ls[i + 1]
                            if ci.type!="real" and ci.type!="int":
                                doErr("Unknown type for calc: ",l)
                    if lsu[i]=="__NR":
                        ci.stores=-1
                        ci.isNonRebase=True
                    if lsu[i] == "__R":
                        ci.stores = -1
                        ci.isRebase = True
                    if lsu[i]=="OVERWRITES":
                        ci.overwrites=ls[i+1]
                continue
            if section=="COMMON":
                mi.commonCode=mi.commonCode.__add__([l])
            if section=="BASIC":
                if not lsu[0] in allowableBasicParams:
                    doErr("Unknown basic parameter ",ls[0])
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
                if lsu[0]=="FORCE":
                    mi.forceThese=ls[1:]
                if lsu[0]=="FIRSTPROJECTIONPERIOD":
                    mi.firstProjectionPeriod=int(ls[1])
                if lsu[0] == "LASTPROJECTIONPERIOD":
                    mi.lastProjectionPeriod = int(ls[1])
                if lsu[0]=="BATCHSIZEEXTERNAL":
                    mi.batchSizeExternal=int(ls[1])
                if lsu[0] == "BATCHSIZEINTERNAL":
                    mi.batchSizeInternal = int(ls[1])
            if section == "DATA" or section == "DERIVED":
                mi.hasData=True
                df=dataFieldInfo()
                df.name=ls[0]
                typeOK=True
                if len(ls)==1 or ls[1]=="":
                    typeOK=False
                if typeOK:
                    if not ls[1].__contains__("["):
                        lTemp=ls[1]
                    else:
                        lTemp=ls[1][0:ls[1].find("[")]
                        if ls[1][-1]!="]" or not ls[1][ls[1].find("[")+1:-1].isnumeric():
                            typeOK=False
                    if not enums.__contains__(lTemp):
                        if len(lTemp)==3 and lTemp!="int":
                            typeOK=False
                        if len(lTemp)==4 and lTemp!="real":
                            typeOK=False
                        if len(lTemp)!=3 and len(lTemp)!=4:
                            typeOK=False
                if not typeOK:
                    doErr("Unknown type for data field: ",l)
                if  not ls[1].__contains__("["):#arrayed?
                    df.type=ls[1]
                else:
                    (ll,_,_)=nwscap(ls[1],"[]")
                    df.type=ll[0]
                    df.arraySize=int(ll[1])
                mi.dataFieldInfos[df.name]=df
            if section == "DERIVED":
                df.expression=l[l.find("=")+1:]
                mi.hasDerived=True
            if section=="PHASE":
                skipItem=False
                for i in range(0,len(ls)):
                    if skipItem:
                        skipItem=False
                        continue
                    if lsu[i] not in allowablePhaseSettings:
                        doErr("Unknown phase setting: ",l)
                    if lsu[i]=="NAME":
                        currPhase={}
                        currPhaseName=ls[i+1]
                        mi.phases[ls[i+1]]=currPhase#dict of calInfoObjects
                        skipItem=True
                    if lsu[i]=="DIRECTION":
                        if lsu[i+1] not in allowableDirections:
                            doErr("Unknown direction for phase: ",l)
                        mi.phaseDirections[currPhaseName]=ls[i+1]
                        skipItem = True
                    if lsu[i] == "START":
                        mi.phaseStart[currPhaseName] = ls[i + 1]
                        skipItem = True
            if section =="CALC":
                l=l.strip()
                if l[0:4].upper()=="CALL":
                    ci.isCall=True
                    ci.name=l[4:].strip()
                    currPhase[ls[0]] = ci
                    ci.stores=-2
                    continue
                elif lsu[0]=="INITIALISE":
                    ci.initialisation=l
                else:
                    if firstLine:
                        firstLine=False
                        ci.lhs = l
                        if l[0]!="(":
                            ci.name=ls[0]#not tuple
                            ci.fieldsCalcd=[ci.name]
                        else:#tuple
                            l2=l.replace("(","")
                            l2 = l2.replace(")", "")
                            l2=l2[:l2.find("=")]
                            ci.fieldsCalcd=l2.split(",")
                            ci.name=l2.replace(",","_")
                        currPhase[ci.name]=ci
                        l=l[l.find("=")+1:]#remove "calc="
                    if ci.type!="real" and ci.stores == -1:
                        doErr("Calc must be of type real for a store-all: ", ci.name)
                    if ci.isArrayed and len(ci.fieldsCalcd) > 1:
                        doErr("Calc cannot be arrayed and return >1 value: ", ci.name)
                    if ci.stores ==-1 and len(ci.fieldsCalcd) > 1:
                        doErr("Calc cannot return >1 value and store all values: ", ci.name)
                    if ci.stores==-1 and currPhaseName=="phase0":
                        doErr("Cannot have store-all within phase 0 ",ci.name)
                    ci.code.append(l)
            if section == "TABLES":
                t=tableInfoObject()
                inDims=False
                for i in range(0, len(ls)):
                    if lsu[i]=="BASIS":
                        if lsu[i+1] not in allowableTableBases:
                            doErr("Unknown table basis: ",l)
                        t.basis=lsu[i+1]
                        inDims=False
                    if inDims:
                        dim=ls[i]
                        if dim[0]=="(":
                            dim=dim[1:]
                        if dim[len(dim)-1]==")":
                            dim=dim[0:len(dim)-1]
                        if dim!="int" and not enums.__contains__(dim):
                            doErr("Unknown dimension for table: ",l)
                        t.dims.append(dim)
                    if lsu[i]=="NAME":
                        t.name=ls[i+1]
                    if lsu[i]=="DIMS":
                        inDims=True
                mi.tableInfos[t.name]=t
            if section=="ESG":
                (fieldInfo,_,_)=nwscap(l,"[]")
                if len(fieldInfo)==1:
                    mi.esg[fieldInfo[0]]=[1]
                else:
                    mi.esg[fieldInfo[0]] = [int(fieldInfo[i]) for i in range(1,len(fieldInfo))]

    ift.close()
    return mi

#read top-level model information
modelInfoFile=sys.argv[2]
ift = open(modelSubDir + "/" + modelInfoFile+".model", 'r')
section=""
sbVals={}#subbasis name->list of enum values
inSubBase=False
for l in ift.readlines():
    (ls,c,lsu)=nwscap(l,",=")
    if c:
        if ls[0][0] == "[":
            oldSection = section
            section = lsu[0][1:len(lsu[0]) - 1]
            if not section in allowableTopSections:
                doErr("Unknown section ", ls[0])
            if oldSection != "" and oldSection != "END" and section != "END":
                doErr("Unterminated section preceding ", ls[0])
            continue
        if section=="BASIC":
            if lsu[0] not in set(["MODE","STOCHASTIC","NUMSCENARIOS"]):
                doErr("Unknown basic setting for top level model file: ",l)
            if lsu[0]=="MODE":
                if lsu[1] not in set(["DEPENDENT","INDEPENDENT"]):
                    doErr("Unknown mode in top level model file: ",l)
                isDependent=lsu[1]=="DEPENDENT"
            if lsu[0] == "STOCHASTIC":
                isStochastic=lsu[1]=="TRUE"
            if lsu[0] == "NUMSCENARIOS":
                numScens=int(lsu[1])
        if section=="SUBBASE":
            if lsu[0]=="NAME":
                sbVals[ls[1]]=[]
                sbName=ls[1]
            else:
                sbVals[sbName]=sbVals[sbName].__add__([ls[0]])
            continue
        if section=="MODELS":
            modelInfos[ls[0]]=readBasicModelInfo(modelSubDir + "/" + ls[0] + ".model")
        if section=="BASES":
            if numBases==0 and ls[0]!="Experience":
                doErr("First basis must be Experience: ",l)
            bi=basisInfoObject()
            bases[ls[0]]=bi
            bi.name=ls[0]
            if bi.name=="Experience":
                numBases+=1
                numActualBases+=1
                continue
            else:
                numSBs=1
                for i in range(1,len(ls)):
                    if lsu[i]=="REBASED":
                        bi.isRebase=lsu[i+1]=="TRUE"
                    if lsu[i] == "SUB":
                        bi.subBases = sbVals[ls[i+1]]
                        numSBs=bi.subBases.__len__()
                numBases+=1
                numActualBases+=numSBs
                if bi.isRebase:
                    numRebased += numSBs
                else:
                    numNonRebased+=numSBs
        if section=="REBASING":
            if not l.__contains__("++"):
                rebaseTimes=ls
            else:
                incr=int(l[l.find("++")+2:])
                ll=l[0:l.find("++")]
                for i in range(int(ls[-2])+incr,1501,incr):
                    ll+=","+str(i)
                (rebaseTimes,_,_) = nwscap(ll,",")
            if not l.__contains__(","):
                print("Warning: No commas in rebase times.  Is this the intention?")

#enum for actual bases plus rebase info which may be read from run parameters instead in future developments
doRebase="["
comma=""
count=0
for (bn,bi) in bases.items():
    if bi.subBases==[]:
        off.write("let "+bn+":i32="+str(count)+nl)
        doRebase += comma + str(bi.isRebase).lower()
        comma = ","
        count+=1
    else:
        for sb in bi.subBases:
            off.write("let " + bn +"_"+sb+ ":i32=" + str(count) + nl)
            doRebase += comma + str(bi.isRebase).lower()
            comma = ","
            count += 1
doRebase+="]"
off.write("let doRebase="+doRebase+nl)
off.write("let rebaseTimes:[]i32=["+",".join(rebaseTimes)+"]"+nl)

#Process any continuation lines - zap an accumulation line and accumulate until we find a line with a normal ending
for mi in modelInfos.values():
    for ph in mi.phases.values():
        for ci in ph.values():
            lAccum = ""
            count=-1
            for l in ci.code:
                count+=1
                if not l[:-1].strip().endswith(" _"):
                    ci.code[count]=lAccum + l
                    lAccum = ""
                else:
                    ci.code[count]=""
                    lAccum += l[:-1].strip()[:-2]

#Library code - added verbatim
ift=open(libSubDir+"/"+"library.fut",'r')
for l in ift.readlines():
    off.write(l)
ift.close()

def convUserFn(l):
    #repeatedly look for user defined functions and replace f(,,) with (f () () )
    patt="[a-zA-Z]\w*\s*\("
    fnsDone=set()#TODO will not work if there's more than 1 instance of a given function per line!
    while True:
        itern=re.finditer(patt,l)#find candidate
        gotFn=False
        for m in itern:#have we already processed it?
            fn=m.group(0)
            fn=fn.replace("("," ").strip()
            if not userDefinedFns.__contains__(fn):
                continue
            gotFn=not fnsDone.__contains__(fn)
            if m.start()>0:
                if not gotFn:
                    gotFn=l[m.start()-1]!='('#todo won't work if original code had ( before fn name
            if gotFn:
                break
        if not gotFn:#done all
            break
        l2=l[:m.start()]+"("#add ( before call
        l2+=fn+" ("
        fnsDone.add(fn)
        parLevel=1
        i=m.end()-1
        while parLevel>0:#look for commas at the current parenthesis level
            i+=1
            c=l[i]
            if c=='(' or c=='[':
                parLevel+=1
            if c==')' or c==']':
                parLevel-=1
            s=""
            if c==',' and parLevel==1:
                s=") ("
            else:
                s+=c
            l2+=s
        l2+=") "
        l2+=l[i+1:]
        l=l2
    return l

def convCodeLine(l):
    #some useful code transformations in one place
    if l[0:3]=="fn ":#declare functions, add a let, convert (,,) to ()()
        l="let "+l+" = "
        l=l.replace(",",") (")
        l=l.replace("fn ","")
        return l
    l=re.sub("[a-zA-Z]\w*\s*=[^=]",lambda x: "let "+x.group(),l)#let in front of a binding
    l=re.sub("\s*return\s"," in ",l)#replace return with in
    l=convUserFn(l)#change format of calls to user functions
    return l

#convert line of code - used in both code and initialisation
def convCode(x,z):#print converted code and return the expression to call to get the value - this could be a function call for an arrayed calc
    return "googalumba"

#Global function code (this is user defined, so not read verbatim)
ift=open(modelSubDir+"/"+"functions",'r')
for l in ift.readlines():
    (l,ls,c,lsu)=newscap(l,"( ")
    if c:
        if ls[0] == "fn":
            off.write(nl)
            userDefinedFns.add(ls[1])
        l=convCodeLine(l)
        off.write(l+nl)
ift.close()
off.write(nl)

numOutputs=0#allow for array size (1d only)
for mi in modelInfos.values():
    for ph in mi.phases.values():
        for ci in ph.values():
            if ci.isOutput:
                if not ci.isArrayed:
                    numOutputs+=1
                else:
                    numOutputs+=ci.dimSizes[0]

if not isDependent:
    mName=list(modelInfos.keys())[0]

#enums
off.write(nl)
for enum in enums.values():
    for (k,v) in enum.items():
        off.write("let "+k+":i32="+str(v)+nl)

#other system constants
for mi in modelInfos.values():
    off.write("let firstProjectionPeriod=("+str(mi.firstProjectionPeriod)+")"+nl)
    off.write("let lastProjectionPeriod=(" + str(mi.lastProjectionPeriod) + ")" + nl)
    off.write("let numPeriods=lastProjectionPeriod-firstProjectionPeriod+1" + nl)
    off.write("let numScens="+str(numScens)+nl)
    numPeriods=mi.lastProjectionPeriod-mi.firstProjectionPeriod+1
    break

#data-record types
off.write(nl)
for mi in modelInfos.values():
    off.write("type data_"+mi.name+"={"+nl)
    comma=""
    for df in mi.dataFieldInfos.values():
        if df.expression!="":
            continue
        arrType=""
        if df.arraySize>0:
            arrType="["+str(df.arraySize)+"]"
        typ="int"
        if df.type=="real":
            typ="real"
        off.write(comma+df.name+":"+arrType+typ+nl)
        comma=","
    off.write("}\n")

#data conversion functions
off.write(nl)
for mi in modelInfos.values():
    off.write("let dataFromArrays_"+mi.name+" [nr] (dataInt:[nr][]i32) (dataReal:[nr][]f32):[]data_"+mi.name+"="+nl)
    dataFieldsInt=""
    dataFieldsReal=""
    countInt=0
    countReal=0
    #group all int and all real fields
    for df in mi.dataFieldInfos.values():
        if df.expression!="":
            continue
        if not df.type.__contains__("real"):
            if df.arraySize==0:
                dataFieldsInt+=df.name+"=x["+str(countInt)+"],"
                countInt += 1
            else:
                dataFieldsInt += df.name + "=["
                comma=""
                for i in range(0,df.arraySize):
                    dataFieldsInt +=comma+"x["+str(countInt)+"]"
                    countInt += 1
                    comma=","
                dataFieldsInt += "],"
        else:
            if df.arraySize==0:
                dataFieldsReal += df.name + "=y[" + str(countReal) + "],"
                countReal += 1
            else:
                dataFieldsReal += df.name + "=["
                comma=""
                for i in range(0,df.arraySize):
                    dataFieldsReal +=comma+"y["+str(countInt)+"]"
                    countInt += 1
                    comma=","
                dataFieldsReal += "],"
    dataFieldsReal=dataFieldsReal[0:len(dataFieldsReal)-1]
    off.write("map2 (\\x y :data_"+mi.name+"->{"+dataFieldsInt+dataFieldsReal+"}) dataInt dataReal"+nl)

#derived types
off.write(nl)
for mi in modelInfos.values():
    if mi.hasDerived:
        off.write("type derived_"+mi.name+"={"+nl)
        comma=""
        for df in mi.dataFieldInfos.values():
            if df.expression=="":
                continue
            arrType = ""
            if df.arraySize > 0:
                arrType = "[" + str(df.arraySize) + "]"
            typ = "int"
            if df.type == "real":
                typ = "real"
            off.write(comma + df.name + ":" + arrType + typ + nl)
            comma = ","
        off.write("}\n")

# various state types including containers for past values and the all-state
for mi in modelInfos.values():
    maxStored = 0
    for ph in mi.phases.values():
        for ci in ph.values():  # find maximum storage
            if ci.stores == -1:
                haveAll = True
            if ci.stores > maxStored:
                maxStored = ci.stores
    mi.maxStored = maxStored

    # main state, only needed for stored (incl. store-all to allow initialisation thereof) items
    off.write("\ntype state_" + mi.name + "={\n")
    comma = ""
    for ph in mi.phases.values():
        for ci in ph.values():
            if ci.stores > 0:
                typ = "int"
                if ci.type == "real":
                    typ = "real"
                brackets = ""
                for i in range(0, ci.numDims):
                    brackets = brackets + "[" + str(ci.dimSizes[i]) + "]"
                for fld in ci.fieldsCalcd:
                    off.write(comma + fld + ":" + brackets + typ + nl)
                    comma = ","
    off.write("}\n")

    # loop through past states (>1), but not store-all
    for i in range(2, maxStored + 1):
        off.write("\ntype state_" + mi.name + "__" + str(i) + "={\n")  # e.g. state_cwp__1
        comma = ""
        for ph in mi.phases.values():
            for ci in ph.values():
                if ci.stores >= i:
                    typ = "int"
                    if ci.type == "real":
                        typ = "real"
                    brackets = ""
                    for i in range(0, ci.numDims):
                        brackets = brackets + "[" + str(ci.dimSizes[i]) + "]"
                    for fld in ci.fieldsCalcd:
                        off.write(comma + fld + ":" + brackets + typ + nl)
                        comma = ","
        off.write("}\n")

    #the "all-state"
    off.write("\ntype state_" + mi.name +"_all={\n")
    if mi.hasData:
        off.write("p:data_"+mi.name+","+nl)
    if mi.hasDerived:
        off.write("der:derived_"+mi.name+","+nl)
    for i in range(2,maxStored+1):
        off.write("state__" +str(i)+ ":state_"+mi.name+"__"+str(i)+","+nl)
    off.write("state__1:state_" + mi.name + "," + nl)
    off.write("t:i32,\n")
    off.write("forceTheIssue:f32,\n")
    off.write("basisNum:i32\n}\n")

    #constants giving indexes into the store_all array (the start, for an array)
    i_count=0
    off.write(nl)
    i_added=True#need to order by overwriting so keep on looping whilst still adding indices that overwrite
    inds_added={}
    while i_added:
        i_added=False
        for ph in mi.phases.values():
            for ci in ph.values():
                if ci.stores==-1:
                    isPresent=False
                    for fld in ci.fieldsCalcd:
                        if inds_added.keys().__contains__(fld):
                            isPresent=True
                            break
                    if isPresent:
                        continue
                    if ci.overwrites=="":
                        i_added=True
                        for fld in ci.fieldsCalcd:
                            inds_added[fld]=i_count
                            off.write("let i_"+mName+"_"+fld+"="+str(i_count)+nl)
                        if ci.isRebase:
                            i_count+=numRebased
                        elif ci.isNonRebase:
                            i_count+=numNonRebased
                        else:
                            i_count+=(ci.dimSizes[0] if ci.isArrayed else 1)
                    elif inds_added.__contains__(ci.overwrites):
                        i_added=True
                        off.write("let i_" + mName + "_" + ci.name + "=" + str(inds_added[ci.overwrites]) + nl)
                        inds_added[ci.name]=inds_added[ci.overwrites]
    off.write("let numSAs="+str(i_count)+nl)

#scenario type and conversion function
hasESG=False
for mi in modelInfos.values():
    if mi.esg!={}:
        hasESG=True
        off.write("\ntype oneScen={\n")#scenario type
        comma=""
        for (k,v) in mi.esg.items():
            off.write(comma+k+":[]")
            if v!=[1]:
                for i in v:
                    off.write("["+str(i)+"]")
            off.write("f32\n")
            comma=","
        off.write("}\n\n")
        off.write("let oneScenFromArray [np][nc] (scen:[np][nc]f32): oneScen=\n")#convert one scenario (1 index of the outer dimension of the scenario file) to a oneScen
        colCount=0
        for (k,v) in mi.esg.items():#get arrays
            if v==[1]:#scalar
                off.write("\tlet "+k+"=flatten scen[:,"+str(colCount)+":"+str(colCount+1)+"]"+nl)
                colCount+=1
            elif len(v)==1: #vector
                off.write("\tlet "+k+"=scen[:,"+str(colCount)+":"+str(colCount+v[0])+"]"+nl)
                colCount+=v[0]
            else: #matrix (grid)
                off.write("\tlet "+k+"=unflatten "+str(v[0])+" "+str(v[1])+" scen[:,"+str(colCount)+":"+str(colCount+v[0]*v[1])+"]"+nl)
                colCount+=v[0]*v[1]
        off.write("\n\tin\n\t{")
        comma=""
        for (k,v) in mi.esg.items():#pack arrays in record
            off.write(comma+k+"="+k)
            comma=","
        off.write("}\n")
        off.write("\nlet scensFromArrays(scens: [][][]f32):[]oneScen =\n")#convert whole scenario file to array of oneScens
        off.write("\tmap oneScenFromArray scens\n")
        break

#main function
off.write(nl)
off.write("let main ")
if hasESG:
    off.write(" (scensData:[][][]f32) ")
for mi in modelInfos.values():#data files
    if mi.hasData:
        off.write("(fileDataInt_"+mi.name+":[numPols][]i32) (fileDataReal_"+mi.name+":[numPols][]f32)")
for mi in modelInfos.values():#tables
    for t in mi.tableInfos.values():
        off.write(" (table_"+t.name+"_"+mi.name+":[numBases]"+multiBracket[len(t.dims)]+"f32)")
off.write(":[][]f32="+nl)

off.write("\nunsafe\n\n")

#initialisation functions for setting initial state based on whether we want resume from where we left off in the (non-static) previous phase, or not.
#two functions actually, for state and for store-alls
for initMode in range(0,2):#ordinary, store-all
    for mi in modelInfos.values():
        count=0
        for (phName,ph) in mi.phases.items():#init fn for a phase
            count+=1#check if it's 1st phase (phase0  or 1)
            if mi.phaseDirections[phName]=="static":
                continue#no initialisation for static, as it's not a run through time
            off.write("\nlet init_"+mi.name+"_"+phName+("_storeAll" if initMode==1 else ""))
            off.write(" (nrBasisNum:i32) ")
            off.write(" (previousTime:i32) ")
            if initMode==1:
                off.write(" (storeAllFromLastPhase:*[][]f32) ")
            if mi.hasData:
                off.write(" (d:data_"+mi.name+") ")
            if mi.hasDerived:
                off.write(" (der:derived_" + mi.name + ") ")
            if hasESG:
                off.write(" (scen:oneScen) ")
            if count>1 and mi.phaseStart[phName]=="previousTime":#if not first phase then bring in state from end of previous phase
                off.write(" (stateFromLastPhase:state_"+mi.name+" ) ")
                off.write(" (storeAllFromLastPhase:[][]f32) ")
            if initMode==0:
                off.write(":state_"+mi.name+"=\n")
            else:
                off.write(":*[][]f32=\n")
            inited=set()
            for (phName2, ph2) in mi.phases.items():#we must mention all calcs (fom all phases) as we need to put together a state record
                for ci in ph2.values():
                    initCode=""
                    if ci.stores>0 or ci.stores==-1:#only those in state. Create binding to local value then that will be placed either in state or in store-all
                        if ci.initialisation!="" and ph2 is ph:#only use initialisation on the calc's own phase
                            pos=ci.initialisation.find("=")
                            expr=ci.initialisation[pos+1:]
                            initCode=convCode(expr,1)
                        elif (count == 1 or mi.phaseStart[phName]!="previousTime") and initMode==0:  # zeroise on first phase only
                            if ci.numDims == 0:
                                initCode = "("+"".join([ "0," for fld in ci.fieldsCalcd])
                                initCode=initCode[:-1] + ")"
                            else:
                                initCode="zeros" + str(ci.numDims) + " " + " ".join(map(str, ci.dimSizes))
                        if (initMode==0 and ci.stores>0 or initMode==1 and ci.stores==-1) and initCode!="":
                            off.write(ci.lhs  + initCode + nl)  # the local bnding
                            for fld in ci.fieldsCalcd:#record which calcs were initialised (used with "with" in state creation)
                                inited.add(fld)
            if initMode==0:
                #creating state
                if count==1 or mi.phaseStart[phName]!="previousTime":#compose the record, if no state b/f
                    off.write("\nin {")
                    comma=""
                    for ph2 in mi.phases.values():
                        for ci in ph2.values():
                            if ci.stores > 0:
                                for fld in ci.fieldsCalcd:
                                    off.write(comma+fld+"="+fld)
                                    comma=","
                    off.write("}\n\n")
                else: #we have state b/f so can use "with"
                    if len(inited)!=0:
                        off.write("\nin stateFromLastPhase ")
                        for ci in inited:
                            off.write(" with "+ci+"="+ci)
                        off.write(nl)
                    else:
                        off.write("\n= stateFromLastPhase "+nl)
            else:
                #storing in store-all; 3 cases: scalar (and that includes __NR, in this case), genuine array
                off.write("let sa=storeAllFromLastPhase\n")
                for ph2 in mi.phases.values():
                    for ci in ph2.values():
                        if ci.stores ==-1 and ci.initialisation!="" and ph2 is ph:
                            if not ci.isArrayed and not ci.isNonRebase:
                                off.write(" with [i_"+mi.name+"_"+ci.name+","+mi.phaseStart[phName]+"-firstProjectionPeriod]="+ci.name+nl)
                            elif ci.isArrayed:
                                for ind in range(0,ci.dimSizes[0]):
                                    off.write(" with [i_"+mi.name+"_"+ci.name+"+"+str(ind)+","+mi.phaseStart[phName]+"-firstProjectionPeriod]="+ci.name+"["+str(ind)+"]"+nl)
                            else:
                                off.write(" with [i_"+mi.name+"_"+ci.name+"+nrBasisNum,"+mi.phaseStart[phName]+"-firstProjectionPeriod]="+ci.name+nl)
                off.write("in sa\n")

#function to initialise the all-state on latter phases
off.write(nl)
for mi in modelInfos.values():
    count = 0
    for (phName, ph) in mi.phases.items():
        count+=1
        if mi.phaseDirections[phName] == "static":
            continue  # no initialisation for static, as it's not a run through time
        if count>1:
            off.write("\nlet init_" + mi.name + "_" + phName+"_all")
            if mi.hasData:
                off.write(" (d:data_" + mi.name + ") ")
            if mi.hasDerived:
                off.write(" (der:derived_" + mi.name + ") ")
            if hasESG:
                off.write(" (scen:oneScen) ")
            off.write("( nrBasisNum:i32 )")
            off.write(" (storeAllFromLastPhase:[][]f32) ")
            off.write(" (as:state_"+mi.name+"_all )")
            off.write(" :state_"+mi.name+"_all  ="+nl)
            off.write("\tlet state_bf= init_"+ mi.name + "_" + phName+" nrBasisNum as.t"+(" d " if mi.hasData else "")+(" der " if mi.hasDerived else "")+(" scen " if hasESG else "")+(" as.state__1" if mi.phaseStart[phName]=="previousTime"  else "")+ (" storeAllFromLastPhase " if mi.phaseStart[phName]=="previousTime"  else "")+"\n")
            off.write("\tin as with state__1=state_bf"+ ("" if mi.phaseStart[phName]=="previousTime" else " with t="+mi.phaseStart[phName])+nl)

# main function for running a single policy (independent)
# signature
off.write(nl)
off.write("\nlet runOnePol_" + mi.name)
if hasESG:
    off.write("(scen:oneScen) ")
off.write("(pol:data_" + mi.name + ") ")
if mi.hasDerived:
    off.write("(der:derived_" + mi.name + ")")
off.write(":[][]f32 =" + nl)

#Define the store-all array
off.write("\tlet storeAll:*[][]f32=copy (undef2 numSAs (numPeriods+1))\n")#one extra period for initialisation

#batches
off.write("\nlet batchSize:i32="+str(mi.batchSizeInternal)+nl)
off.write("let numBatches=if np%%batchSize==0 then (np//batchSize) else (np//batchSize+1)\n")
off.write("let sumOfBatches=\n")
off.write("\tloop sumOfBatches':[][][]f32=(zeros3 batchSize "+str(numOutputs)+" numPeriods) for i<numBatches do\n")
off.write("\tlet lo=i*batchSize\n")
off.write("\tlet hi=mini (i+1)*batchSize np\n")
off.write("\tlet batchRes = map2 runOnePol_"+mName+" fileData_"+mName+"[lo:hi] derived_"+mName+"[lo:hi]\n")
off.write("\tin sumOfBatches' +...+ batchRes\n")
off.write("in reduce (+..+) (zeros2 "+str(numOutputs)+" numPeriods) sumOfBatches\n")
