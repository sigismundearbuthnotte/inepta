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
calcSettings={"STORE":True,"TYPE":True,"__NR1":False,"__NR2":False,"__R":False,"OUTPUT":False,"OVERWRITES":True}#does a further value follow the setting name?
allowablecalcSettings=set(calcSettings.keys())
allowablePhaseSettings=set(["NAME","DIRECTION","START"])
allowableDirections=set(["FORWARDS","BACKWARDS","STATIC"])
allowableTableBases=set(["SINGLE","PREFIX","SUFFIX","SUBDIR"])
allowableTopSections=set(["BASIC","BASES","SUBBASE","REBASING","MODELS","END"])
CALCCODE=0
INITIALISATION=1
GLOBALFN=2

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
        self.dim1HasLB=True#2nd last
        self.dim2HasLB=True#inner-most

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
        self.isWholeArray=False#NR or R whole array calcs; to distinguish from calcs that are not w/a but are stored for NR purposes
        self.overwrites=""#if the preceding is true, what calc does it overwrite.  Can only have an __NR overwriting another __NR
        self.isRebase=False#calculated by whole array calc by rebasing (once for each R basis)
        self.myPhase=None

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
                ci.myPhase=currPhaseName
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
                    if lsu[i]=="__NR1":
                        ci.stores=-1
                        ci.isNonRebase=True
                        ci.isWholeArray=False
                    if lsu[i]=="__NR2":
                        ci.stores=-1
                        ci.isNonRebase=True
                        ci.isWholeArray=True
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
                intc=0
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
                        if not dim.__contains__("int") and not enums.__contains__(dim):
                            doErr("Unknown dimension for table: ",l)
                        if dim=="int0":
                            dim="int"
                            if intc==0:
                                t.dim1HasLB=False
                            else:
                                t.dim2HasLB=False
                            intc+=1
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

def subStoreAll(mtch,l,ci,mi,isCalcInThisPhase):
    #cases:
    # store-all not NR/R: present-this-phase, scalar:present(not this phase i.e. implied t)/past/future, array: time(as scalar) and explicit/implied index
    # store-all NR/R:  as above, but indexing will depend on basis (possibly implicit)
    #return (string to insert, first position after match to keep in original string)
    m=mtch.group()
    arrExp=" storeAll["#add position in store-all: scalar, array __NR/R
    arrExp+="i_"+mi.name+"_"+ci.name
    #find position index if array
    if not ci.isArrayed and not ci.isNonRebase and not ci.isRebase:
        if m[-1]=="[":#not arrayed or __NR/R; however, may or may not have a time index
            bracketCount=1
            pos=mtch.end()
            cont=True
            timeExp=""
            while cont:#find end of time index and accumulate same
                if l[pos]=="[":
                    bracketCount+=1
                if l[pos]=="]":
                    bracketCount-=1
                cont=bracketCount==0
                if cont:
                    timeExp+=l[pos]
                pos+=1
            arrExp+=","+timeExp+"]"
            return(arrExp,pos+1)
        else:
            if isCalcInThisPhase:
                return ("",0)#nothing to do case as we can just refer to the calc binding
            else:
                arrExp+=",as.t]"
                return (arrExp,mtch.end())
    else:
        #is there a position index present or is it implicit? (we can omit both or position only; if 1 index is present it is time).  For both order is time then position.
        gotPosIndex=False
        gotTimeIndex=False
        if m[-1]=="[":
            gotTimeIndex=True#must have at least a time index
            bracketCount=1
            pos=mtch.end()
            cont=True
            timeExp=""
            while cont:
                if l[pos]=="[":
                    bracketCount+=1
                if l[pos]=="]":
                    bracketCount-=1
                cont=bracketCount==0
                if cont:
                    timeExp+=l[pos]
                pos+=1
            gotPosIndex= l[pos]=="["
            if gotPosIndex:
                bracketCount = 1
                pos +=1
                cont = True
                posExp = ""
                while cont:
                    if l[pos] == "[":
                        bracketCount += 1
                    if l[pos] == "]":
                        bracketCount -= 1
                    cont = bracketCount == 0
                    if cont:
                        posExp += l[pos]
                    pos += 1
    if not gotTimeIndex and not ci.isNonRebase and not ci.isRebase and isCalcInThisPhase:
        arrExp =ci.name+"[i1]"#current time reference to arrayed.  TODO: this implies can only refer to an arrayed store-all at current time (i.e. before it is stored in the array) using implicit position, not explicit
        return (arrExp,mtch.end())
    #no need to convert position into index as we have constants defined in the Futhark
    if gotPosIndex and gotTimeIndex:
        arrExp+=posExp+","+timeExp+"]"
    elif gotPosIndex:
        arrExp+=posExp+","+"as.t]"
    elif gotTimeIndex:
        arrExp+="i1,"+timeExp+"]"
    else:
        arrExp+="i1,as.t]"
    return (arrExp,mtch.end())

#convert line of code - used in both code, initialisation and settting derived, does not apply to NR or R whole-array calcs
def convCode(mi,ci,codeType):#print converted code and return the expression to call to get the value - this could be a function call for an arrayed calc
    #get code depending on what we are converting
    phName=ci.myPhase
    if codeType==INITIALISATION:
        pos = ci.initialisation.find("=")
        code = [ci.initialisation[pos + 1:].copy()]
    else:
        code=ci.code.copy()
    if mi.phaseDirections[phName] == "static" or ci.isNonRebase or ci.isRebase:
        off.write("let "+ci.name+" (storeAll:*[][]f32):*[][]f32=\n")#w/a case
    else:
        off.write("\tlet " + ci.lhs + nl)  # start of assigment for ordinary case
    if ci.isArrayed:
        # the calc now becomes the inner-most internal function to be called by partial application
        off.write("\tlet " + ci.name + "_arr" + str(ci.numDims))
        for ind in range(1, ci.numDims + 1):  # array index parameters
            off.write(" (i" + str(ind) + ":i32) ")
        off.write(":f32=\n")
    for l in code:  # loop through lines
        l = " " + l + " "#a frequent patern is alphanum_ terminated with !alphanum_.  This is to ensure that'll work at the start and end of the line
        l = re.sub("[a-zA-Z]\w*\s*=[^=]", lambda x: "let " + x.group(), l)  # let in front of binding
        l = convUserFn(l)  # format of calls to user-defined functions
        if len(ci.code) > 1:#return of calc value
            l = l.replace("return ", "\tin ")
        else:
            l = l.replace("return ", "")
        for kt in mi.tableInfos.keys():  # convert table name to name of parameter of main
            l = re.sub("[\W]" + kt + "[\W]",lambda x: x.group()[0] + "table_" + kt + "_" + mi.name + x.group()[len(kt) + 1:], l)
        for (kt,vt) in mi.tableInfos.items():  # add lower bound to start of table index for (potentially) the 2 inner-most dims (there's no easy way to do this...)
            if vt.dim1HasLB or vt.dim2HasLB:#look for "," at level 0 of [] or ()
                findPos=0
                tbl = "table_" + kt + "_" + mi.name
                while True:#look for all instances of this table at increasing positions in the string
                    findPos=l.find(tbl, findPos)
                    if findPos<0:
                        break#next table
                    findPos+=len(tbl)+1
                    parLevel=0
                    brLevel=0
                    pos=findPos
                    for i in range(0,len(vt.dims)-2):#skip all but the last two dimensions
                        while True:#scan forward
                            if l[pos]=="[":
                                brLevel+=1
                            if l[pos]=="]":
                                brLevel-=1
                            if l[pos]=="(":
                                parLevel+=1
                            if l[pos]==")":
                                parLevel-=1
                            pos += 1
                            if parLevel==0 and brLevel==0 and l[pos-1]==",":
                                break
                    if vt.dim1HasLB:#got 2nd last comma
                        l=l[:pos]+"(-lb_"+kt+"_"+mi.name+"_1)+"+l[pos:]
                    while True:#scan forward for last (possibly only) comma
                        if l[pos]=="[":
                            brLevel+=1
                        if l[pos]=="]":
                            brLevel-=1
                        if l[pos]=="(":
                            parLevel+=1
                        if l[pos]==")":
                            parLevel-=1
                        pos += 1
                        if parLevel==0 and brLevel==0 and l[pos-1]==",":
                            break
                    if vt.dim2HasLB:
                        l=l[:pos]+"(-lb_"+kt+"_"+mi.name+"_2)+"+l[pos:]
        for df in mi.dataFieldInfos.values():  # add as.p. in front of data/derived fields
            if df.expression == "":
                l = re.sub("[\W]" + df.name + "[\W]",lambda x: x.group()[0] + "as.p." + df.name + x.group()[len(df.name) + 1:], l)
            else:
                l = re.sub("[\W]" + df.name + "[\W]",lambda x: x.group()[0] + "as.der." + df.name + x.group()[len(df.name) + 1:], l)
        l = re.sub("[\W]" + "t" + "[\W]", lambda x: x.group()[0] + "as.t" + x.group()[2:], l)  # "t"
        l = re.sub("[\W]" + "basisNum" + "[\W]", lambda x: x.group()[0] + "as.basisNum" + x.group()[9:], l)  # basis
        if mi.phaseDirections[phName] == "static" or ci.isNonRebase or ci.isRebase:
            # static phase or __NR/R - need whole arrays.  See below for more explanation
            for udf in userDefinedFns:  # find (the only) user defined function and insert storeAll after it.
                if l.find(udf) > 0:
                    fpos = l.find(udf) + len(udf)
                    break
            l = l[:fpos] + " storeAll " + l[fpos:]
        # references to other calcs
        for (phName2, ph2) in mi.phases.items():
            for ci2 in ph2.values():
                if mi.phaseDirections[phName] != "static" and not ci.isNonRebase and not ci.isRebase:
                    if not ci2.isArrayed and ci2.stores!=-1:
                        #scalar (not s/a): only need to check for past values, could be a tuple
                        for past in range(1, ci2.stores + 1):
                            for fld in ci.fieldsCalcd:
                                l = re.sub("[\W]" + fld + "__" + str(past) + "[\W]",lambda x: x.group()[0] + "as.state__" + str(past) + "." + fld + x.group()[len(fld + "__" + str(past)) + 1:],l)
                    if ci2.isArrayed and ci2.stores != -1:
                        #array (not s/a): check for past values and for implied array indices (1d only)
                        for past in range(1, ci2.stores + 1):
                            l = re.sub("[\W]" + ci2.name + "__" + str(past) + "[\W]",lambda x: x.group()[0] + "as.state__" + str(past) + "." + ci2.name + x.group()[len(ci2.name + "__" + str(past)) + 1:],l)
                        l = re.sub("[\W]" + ci2.name + "[\W]",lambda x: (x.group() if (x.end()!=len(l)-1 and x.group()[-1]=="[")  else (x.group()[:-1]+"[i1]"+x.group()[-1])),l)
                    if ci2.stores==-1:
                        empty=False
                        while not empty:#use finditer to get an occurence of the pattern but abandon the loop after processing it as the string will have changed
                            empty=True
                            itern = re.finditer("[\W]" + ci2.name + "[\W]", l)
                            for x in itern:
                                empty=False
                                (str,ep)=subStoreAll(x,l,ci2,mi,phName2==ci.myPhase)#new string to insert plus posn of remainder of line
                                l=l[:x.start()]+str+l[ep:]
                                break#only do on iter as l has changed
                else:
                    #w/a calcs - we already added storeAll above
                    #pattern=fn <arrays> <tables>: add in "storeAll", sa->sa indices (if arrayed), sa[i]-> 1 index (for arrayed).  The remaining params should be tables only and are assumed to "match up" FTB.  They should already have been converted.
                    #NB: when converting the surrouding calc, will need to wrap in a fn taking and returning storeAll
                    if ci2.stores==-1:
                        empty=False
                        while not empty:#same logic as above iro finditer
                            empty=True
                            itern = re.finditer("[\W]" + ci2.name + "[\W]", l)
                            for x in itern:
                                #4 cases: scalar + 3 array cases: has index: translate it (could be a range, i.e. has a colon), no index: supply all
                                if not ci2.isArrayed and not ci2.isNonRebase and not ci2.isRebase:
                                    str="[i_"+mi.name+"_"+ci2.name+"]"#scalar
                                    ep=x.end()
                                elif x.group()[-1]!="[":
                                    ind="i_"+mi.name+"_"+ci2.name
                                    str="(steps "+ind+" ("+ind+"_end-"+ind+"+1) 1)"#all array
                                    ep=x.end()
                                else:
                                    #one particular element, or range
                                    elt=""
                                    for pos in range(x.end()+1,999999):#scan for ]
                                        if l[pos]!="]":#end of this array?
                                            elt+=l[pos]
                                        else:
                                            break
                                    if not elt.__contains__(":"):
                                        str="(i_"+mi.name+"_"+ci2.name+"+"+elt+")"#can use a number,an enum or a basis name (which have already been assigned constants, so no need for any conversion)
                                    else:
                                        elts=str.split(":")
                                        ind1 = " (i_" + mi.name + "_" + ci2.name+"+"+elts[0]+") "
                                        ind2 = " (i_" + mi.name + "_" + ci2.name+"+"+elts[1]+") "
                                        str="(steps "+ind1+" ("+ind2+"-"+ind1+")"+ " 1)"#range
                                    ep=pos+1
                                l = l[:x.start()] + str + l[ep:]
                                empty=False
                                break#next iter as string changed
        l.replace("][",",")#any left over ][ from multi-d arrays (but not tables).  Come to think of it, does it make any difference in Futhark?  It does as you need e.g. (x[0])[1]
    if ci.isArrayed and mi.phaseDirections[phName] != "static":#multi-level mappings for arrayed
        for ind in range(1, ci.numDims):  # loop over map functions
            off.write("let " + ci.name + "_arr" + str(ci.numDims - ind))
            for ind2 in range(1, ci.numDims - ind + 1):  # loop over parameters of a map function
                off.write(" (i" + str(ind2) + ":i32) ")
            off.write(":" + multiBracket[ind] + "f32=map (" + ci.name + "_arr" + str(
                ci.numDims - ind + 1) + " ")  # partial application of previous mapping function
            for ind2 in range(1, ci.numDims - ind + 1):  # partial application (2)
                off.write(" i" + str(ind2) + " ")
            off.write(") (iota " + str(
                ci.dimSizes[ci.numDims - ind]) + ") \n")  # the iota to which we apply the partial application
        off.write("in map " + ci.name + "_arr1 (iota " + str(ci.dimSizes[0]) + ")\n")

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
                    isPresent=False#done already?
                    for fld in ci.fieldsCalcd:
                        if inds_added.keys().__contains__(fld):
                            isPresent=True
                            break
                    if isPresent:
                        continue
                    if ci.overwrites=="":#not an overwriter
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
                        off.write("let i_"+mName+"_"+fld+"_end="+str(i_count-1)+nl)
                    elif inds_added.__contains__(ci.overwrites):
                        i_added=True
                        off.write("let i_" + mName + "_" + ci.name + "=" + str(inds_added[ci.overwrites]) + nl)
                        off.write("let i_" + mName + "_" + ci.name + "_end=i_" + mName +"_"+ci.overwrites+"_end" + nl)
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
for mi in modelInfos.values():#tables and their lower bounds (for (possibly) inner 2 dimensions)
    for t in mi.tableInfos.values():
        off.write(" (table_"+t.name+"_"+mi.name+":[numBases]"+multiBracket[len(t.dims)]+"f32) (lb_"+t.name+"_"+mi.name+":[]i32) ")
off.write(":[][]f32="+nl)

#bind constants to array LBs to avoid excess indexing
off.write(nl)
for mi in modelInfos.values():
    for t in mi.tableInfos.values():
        off.write("lb_"+t.name+"_"+mi.name+"_1="+(" lb_"+t.name+"_"+mi.name+"[0]" if t.dim2HasLB else "0i32")+nl)
        off.write("lb_"+t.name+"_"+mi.name+"_2="+(" lb_"+t.name+"_"+mi.name+"[1]" if t.dim1HasLB else "0i32")+nl)
off.write(nl)

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
            #TODO do the initialisation function need d and der?  Can they not get them from as?
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
                            initCode=convCode(mi,ci,INITIALISATION)
                        elif (count == 1 or mi.phaseStart[phName]!="previousTime") and initMode==0:  # zeroise on first phase only
                            if ci.numDims == 0:
                                initCode = "("+"".join([ "0," for fld in ci.fieldsCalcd])
                                initCode=ci.lhs + initCode[:-1] + ")"
                            else:
                                initCode=ci.lhs +"zeros" + str(ci.numDims) + " " + " ".join(map(str, ci.dimSizes))
                        if (initMode==0 and ci.stores>0 or initMode==1 and ci.stores==-1) and initCode!="":
                            off.write(initCode + nl)  # the local binding
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

#function to run an entire static phase (storeAll->storeAll)
for mi in modelInfos.values():
    for (phName,ph) in mi.phases.items():
        if mi.phaseDirections[phName]=="static":
            off.write("let  runStaticPhase_"+mi.name+"_"+phName+"(storeAll:*[][]f32):*[][]f32\n")
            revd=[]
            for ci in ph.values():#order is "just as it comes" (TODO make sure dict does not mess up the order)
                revd=[ci.name]+revd
                convCode(mi, ci, "Ordinary")  # write calc's code, this case a storeAll->storeAll fn
            call="storeAll"
            for fn in revd:#call of call of...
                call=fn+"("+call+")"
            off.write("in "+call+nl)

#functions to run one period (non-static phases)
for mi in modelInfos.values():
    for (phName,ph) in mi.phases.items():
        if mi.phaseDirections[phName]!="static":
            off.write("let  runOnePeriod_"+mi.name+"_"+phName+" (as:state_"+mi.name+"_all) (storeAll:*[][]f32):")
            off.write(" (state_"+mi.name+"_all,*[][]f32)="+nl)
            #get dependencies of calcs
            whoCallsWhom = {}
            for ci in ph.values():
                if ci.isRebase or ci.isNonRebase:
                    continue
                iCall = []
                for ci2 in ph.values():  # does ci use ci2?
                    found = False
                    for fld in ci2.fieldsCalcd:  # or rather, does it use ci2's calculated fields
                        for l in ci.code:
                            for mtch in re.finditer("[\W]" + fld + "[\W]", " " + l + " "):
                                found = True
                    if found:
                        iCall.append(ci2.name)
                whoCallsWhom[ci.name] = iCall
            #write out calcs
            while whoCallsWhom != {}:
                for (caller, callees) in whoCallsWhom.items():
                    if callees == []:  # first calc with no ancestors
                        convCode(mi,ph[caller],"Ordinary")#write calc's code
                        for l in whoCallsWhom.values():  # remove this from its users
                            if l.__contains__(caller):
                                l.remove(caller)
                        del whoCallsWhom[caller]
                        break
            #storage function
            off.write("let store (as:state_"+mi.name+"_all) (storeAll:*[][]f32):")
            off.write(" (state_" + mi.name + "_all,*[][]f32)=" + nl)
            for i in range(1, mi.maxStored + 1):#stored states
                off.write("let state__"+str(i)+"=as.state__"+str(i))
                for ci in ph.values():
                    if ci.stores >= i:
                        for fld in ci.fieldsCalcd:
                            off.write(" with "+fld+"="+("as.state__"+str(i-1)+"." if i>1 else "")+fld)
                off.write(nl)
            off.write("let asNew=as "+nl)#new all-state
            for i in range(1, mi.maxStored + 1):
                off.write(" with state__"+str(i)+"=state__"+str(i))
            if mi.phaseDirections[phName] == "forwards":#time
                off.write(" with t=as.t+1"+nl)
            else:
                off.write(" with t=as.t-1"+nl)
            #update the store-all
            off.write("let storeAllNew=storeAll ")
            for ci in ph.values():
                if ci.stores ==-1 and not ci.isRebase and not ci.isNonRebase:
                    if not ci.isArrayed:
                        off.write(" with [i_"+mi.name+"_"+ci.name+",as.t]="+ci.name)
                    else:
                        for dim in range(0,ci.numDims):
                            off.write(" with [i_" + mi.name + "_" + ci.name + "+"+str(dim)+",as.t]=" + ci.name)
                #TODO loop over subbases, store same value for each subbasis
                if ci.stores ==-1 and ci.isNonRebase and not ci.isWholeArray:#put __NRs in correct slots
                    off.write(" with [i_" + mi.name + "_" + ci.name+"+as.basisNum" + ",as.t]=" + ci.name)
                if ci.stores ==-1 and ci.isRebase and not ci.isWholeArray:#put __NRs in correct slots
                    pass

            off.write(nl)
            off.write("in (asNew,storeAllNew)"+nl)
            off.write("in store as storeAll\n")#return from runOnePeriod

#functions (used in bases) to run N periods
for mi in modelInfos.values():
    for (phName,ph) in mi.phases.items():
        if mi.phaseDirections[phName]!="static":
            off.write("let  runNPeriods_"+mi.name+"_"+phName+"(n:i32) (as:state_"+mi.name+"_all) (storeAll:*[][]f32):")
            off.write(" (state_" + mi.name + "_all,*[][]f32)=" + nl)
            off.write("\tloop (as':state_"+mi.name+"_all,storeAll':*[][]f32)=\n")
            off.write("\t(as,storeAll) for i<n do\n")
            off.write("\trunOnePeriod_"+mi.name+"_"+phName+"as' storeAll'"+nl)

#functions to do NR runs: phase 1 runNPeriod.  The latter also stores the __NR1 calcs in the correct place in s/a
for mi in modelInfos.values():
    off.write("let runNRBasis_"+mi.name+"(as:state_"+mi.name+"_all) (storeAll:*[][]f32) (bn:i32):*[][]f32"+nl)#discard the state, only interested in the store-all
    off.write("\tlet as2=as with basisNum=bn\n")
    if mi.dataFieldInfos[mi.termField].expression=="":
        off.write("\tlet (_,storeAll')= runNPeriods_"+mi.name+"_phase1 as.d."+mi.termField+" as2 storeAll"+nl)
    else:
        off.write("\tlet (_,storeAll')= runNPeriods_"+mi.name+"_phase1 as.der."+mi.termField+" as2 storeAll"+nl)

#function to do rebasing inner loop and w/a calcs
for mi in modelInfos.values():
    off.write("let calcRebasedResults_"+mi.name+"(as:state_"+mi.name+"_all) (storeAll:*[][]f32) :*[][]f32"+nl)#discard the state, only interested in the store-all
    bn = 0#loop through rebased bases
    off.write("let storeAll0=storeAll\n")
    if mi.dataFieldInfos[mi.termField].expression == "":
        tbit="d"
    else:
        tbit="der"
    for b in bases:
        if b.isRebase:
            bn+=1
            off.write("let as"+str(bn)+"=as with basisNum="+str(bn)+nl)
            off.write("\tlet (_,storeAll'"+str(bn)+")= runNPeriods_"+mi.name+"_phase1 (as."+tbit+"."+mi.termField+"-as.t+1) as"+str(bn)+" storeAll"+str(bn-1)+nl)#call projection for rebased calcs
    #place functions - as with NR, assume that the functions can deal with multiple bases (all the rebased bases) at once
    #problem: not quite the same as NR as here we assume we calculate one time's value albeit from whole arrays
    #Maybe alter codeConv so it produces a slightly different function for rebased???
    off.write("in\n")

#function to run experience basis (phase 1).  Look like runNPeriods but also calls calcRebased... if it's a rebase time
off.write("let runExperince_"+mi.name+" (as:state_"+mi.name+"_all) (storeAll:*[][]f32) (n:i32):(state_"+mi.name+"_all,*[][]f32)="+nl)
off.write(" (state_" + mi.name + "_all,*[][]f32)=" + nl)
off.write("\tloop (as':state_" + mi.name + "_all,storeAll':*[][]f32)=\n")
off.write("\t(as,storeAll) for i<n do\n")
off.write("\tif !isRebaseTime[as.t+1] then"+nl)
off.write("\trunOnePeriod_" + mi.name + "_phase1 as' storeAll'" + nl)
off.write("\telse\n")
off.write("\tcalcRebaseResults_"+mi.name+"(runOnePeriod_" + mi.name + "_phase1 as' storeAll')" + nl)

# main function for running a single policy (independent)
# signature
for mi in modelInfos:#only 1 model
    break
off.write(nl)
off.write("\nlet runOnePol_" + mi.name)
if hasESG:
    off.write("(scen:oneScen) ")
if mi.hasData:
    off.write("(pol:data_" + mi.name + ") ")
if mi.hasDerived:
    off.write("(der:derived_" + mi.name + ")")
off.write(":[][]f32 =" + nl)

#Define the store-all array
off.write("\tlet storeAll:*[][]f32=copy (undef2 numSAs (numPeriods+1))\n")#one extra period for initialisation

#initialise all-state for either phase0 (if it exists) or phase1.  Need to initialise both state and store-all
hasPhase0 = mi.phases.keys().__contains__("phase0")
if hasPhase0:
    initPhase="phase0"
else:
    initPhase="phase1"
off.write("\tlet init_as_pre"+initPhase+" = init_" + mi.name + "_"+initPhase+"_all "+(" pol " if mi.hasData else "")+(" der " if mi.hasDerived else "")+" 0 storeAll "+ (" scen " if hasESG else "") + "\n")
off.write("\tlet storeAll_pre"+initPhase+" = init_" + mi.name + "_"+initPhase+"_storeAll "+(" pol " if mi.hasData else "")+(" der " if mi.hasDerived else "")+" 0 storeAll "+ (" scen " if hasESG else "") + "\n")

#run phase 0, should it exist
if hasPhase0:
    off.write("(init_as_post_phase0,storeAll_pre_NR)=runNPeriods_"+mi.name+"_phase0 "+(" pol." if mi.dataFieldInfos[mi.termField].expression=="" else " der.")+mi.termField+" init_as_pre_phase0 storeAll_pre_phase0"+nl)
    #initialise

#run NR bases, bases only: "store" will replicate the calc results over subbases
bn=0
for b in bases:
    if not b.isRebase:
        if bn==0:
            off.write("let storeAllNR0=storeAll_pre_NR"+nl)
        bn+=1
        off.write("let storeAllNR"+str(bn)+"=runNRBasis_"+mi.name+" init_as_pre_phase1 storeAllNR"+str(bn-1)+" "+str(bn)+nl)
if bn>0:
    off.write("let storeAll_postNR=storeAll"+str(bn)+nl)
else:
    off.write("let storeAll_postNR=storeAll_pre_NR"+nl)

#as in static-phases, generate functions from the __NR2 calcs and apply to the s/a
#it is assumed that the calc formulae themselves have the ability to cope with bases/subbases
if bn>0:
    revd = []
    ph = mi.phases["phase1"]
    for ci in ph.values():  # order is "just as it comes" (TODO make sure dict does not mess up the order)
        if ci.isNonRebase and ci.isWholeArray:
            revd = [ci.name] + revd
            convCode(mi, ci, "Ordinary")  # write calc's code, this case a storeAll->storeAll fn
    call = "storeAll_postNR"
    for fn in revd:  # call of call of...
        call = fn + "(" + call + ")"
    off.write("storeAllPostNR2 = " + call + nl)
else:
    off.write("storeAllPostNR2 = storeAllPostNR\n")

#Run experience basis (phase1)- with rebasing
off.write("let (as_post_phase1,storeAllPostPhase1)=runExperience_"+mi.name+" init_as_pre_phase1 storeAllPostNR2 "+nl)

#remaining phases
phC=0
phSkip=1+(1 if hasPhase0 else 0)#number of phases already carried out
for (phName, ph) in mi.phases.items():
    phC+=1
    if phC>phSkip:
        if mi.phaseDirections[phName]=="static":#run eiher N periods or static-phase
            off.write("storeAllPostPhase"+str(phC-1)+"=runStaticPhase_"+mi.name+"_"+phName+" (storeAllPost"+str(phC-2)+")"+nl)
            off.write("let as_post_phase"+str(phC-1)+"=as_post_phase"+str(phC-2)+nl)#keep all-state the same
        else:
            #TODO this is horribly incomplete
            off.write("let as_pre_phase"+str(phC-1)+"=init_"+mi.name+"_"+phName+" as_post_phase"+str(phC-2)+" storeAllPostPhase"+str(phC-2)+nl)#initialisation from previous phase (all-state and store-all).
            off.write("let (as_post_phase"+str(phC-1)+",storeAllPostPhase"+str(phC-1)+")=runNPeriods_" + mi.name +"_"+phName+" as_pre_phase"+str(phC-1)+" storeAllPostNR"+str(phC-2) + nl)#run phase
#output from run one pol
results="["
for (phName, ph) in mi.phases.items():#get output calcs and assemble their 1-d (over time) arrays as a 2-d array
    comma=""
    for ci in ph.values():
        if ci.isOutput:
            if not ci.isArrayed:
                results+=comma+"storeAllPostPhase"+str(phC-1)+"[i_"+mi.name+ci.name+"]"
                comma = ","
            else:
                for i in range(0,ci.dimSizes[0]):
                    results += comma + "storeAllPostPhase" + str(phC - 1) + "[i_" + mi.name + ci.name +"+"+ str(i)+"]"
                    comma = ","
results+="]"
off.write("in "+results+nl)

#batches of policies
off.write("\nlet batchSize:i32="+str(mi.batchSizeInternal)+nl)
off.write("let numBatches=if np%%batchSize==0 then (np//batchSize) else (np//batchSize+1)\n")
off.write("let sumOfBatches=\n")
off.write("\tloop sumOfBatches':[][][]f32=(zeros3 batchSize "+str(numOutputs)+" numPeriods) for i<numBatches do\n")
off.write("\tlet lo=i*batchSize\n")
off.write("\tlet hi=mini (i+1)*batchSize np\n")
off.write("\tlet batchRes = map2 runOnePol_"+mName+" fileData_"+mName+"[lo:hi] derived_"+mName+"[lo:hi]\n")
off.write("\tin sumOfBatches' +...+ batchRes\n")
off.write("in reduce (+..+) (zeros2 "+str(numOutputs)+" numPeriods) sumOfBatches\n")
