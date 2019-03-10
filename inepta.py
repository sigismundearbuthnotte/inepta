import os
import sys
import re
import subprocess

#errors
def doErr(errStr,infoStr):
    print(errStr+" "+ infoStr, file=sys.stderr)
    sys.exit()

#control
compileFuthark=False
compileC=False
compileExe=False
futharkPath="/home/andrew/futhark-0.9.1-linux-x86_64/bin"
targetLanguage="c"#"opencl"

#constants
maxRNsPerPeriod=10#for inner models TODO parameterise
nl="\n"
userDefinedFns={"real","exp","sqrt","log","sum","prod","zeros1","zeros2","zeros3","backDisc1","backDisc2","backDisc3","backDisc4","sumprod","sum1","sum2","cumprod","cumsum","udne", \
                "interp","maxi","maxr","mini","minr","backDiscSingle1","backDiscSingle3","backDiscSingle2","sum"}
multiBracket={}#lots of []
br="[]"
multiBracket[0]=""
for i in range(1,100):
    multiBracket[i]=br
    br+="[]"
allowableSections=set(["BASIC","ESG","DATA","DERIVED","PHASE","END","TABLES","COMMON","INNERESG"])
allowableBasicParams=set(["NAME","ARRAYED","TERM","START","FORCE","FIRSTPROJECTIONPERIOD","LASTPROJECTIONPERIOD","BATCHSIZEEXTERNAL","BATCHSIZEINTERNAL","INNERMODEL"])
calcSettings={"STORE":True,"TYPE":True,"__NR1":False,"__NR2":False,"__R1":False,"__R2":False,"OUTPUT":False,"OVERWRITES":True,"CONSTANT":False,"CALL":False,"INNERSCENARIOS":False}#does a further value follow the setting name?
allowableCallSettings=set(["NAME","STATEINPUT","MODEL","PHASE","TERM","STOCHASTIC","SCENARIOS","BASIS","WHEN","RETURNS"])
allowableInnerModelCallSettings=set(["NAME","MODEL","NUMSCENS","TERM","BASIS","WHEN","THEPARAMS"])
allowablecalcSettings=set(calcSettings.keys())
allowablePhaseSettings=set(["NAME","DIRECTION","START","TERM"])
allowableDirections=set(["FORWARDS","BACKWARDS","STATIC"])
allowableTableBases=set(["SINGLE","PREFIX","SUFFIX","SUBDIR"])
allowableTopSections=set(["BASIC","BASES","SUBBASE","REBASING","MODELS","END"])
CALCCODE=0
INITIALISATION=1
GLOBALFN=2
DERIVED=3
COMMON=4
numMTItersPerBatchOfRNs=100#who knows?

#subdirs
rootSubDir=sys.argv[1]
dataSubDir=rootSubDir+"/data"
tablesSubDir=rootSubDir+"/tables"#base subdirectory for tables
modelSubDir=rootSubDir+"/models"
exeSubDir=rootSubDir+"/exe"
outputSubDir=rootSubDir+"/output"
libSubDir=rootSubDir+"/library"#base subdirectory for tables
scensSubDir=rootSubDir+"/scenarios"

#dicts, sets etc.
modelInfos={}#name->modelInfo
enums={}#name->(dict of names->integer)
bases={}#name->basisInfo
rebaseTimes=[]
callInfos={}#name->callInfoObject
innerModelCalls={}#name->inner model call object
errorInfos={}#line number (of generated code)->errorInfo object
currentCalcInfoObject=None#for error info
currentCalcLine=0

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
        self.phaseTerm={}#Does not apply to phases 0 or 1.  name->expression
        self.tableInfos={}
        self.hasData=False
        self.hasDerived=False
        self.esg={}#only top model should have one of these, field name->list of dimension sizes
        self.innerESG={}
        self.forceThese=[]#calcs to force
        self.maxStored=0#excluding store-alls
        self.firstProjectionPeriod=1
        self.lastProjectionPeriod=600
        self.commonCode=[]
        self.batchSizeExternal=1000000
        self.batchSizeInternal=50000
        self.storeAllPosn={}#calc name-> (tuple of store-all index (low,high)).
        self.innerModel=""#name of inner file (in library subdir) containing inner ESG Futhark code

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
        self.dim1HasLB=False#2nd last
        self.dim2HasLB=False#inner-most

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
        self.sizeMax=""#name of data field giving the number of useable elements in the array
        self.code=[]
        self.initialisation=""#initialisation expression
        self.isCall=False
        self.isOutput=False#output from Experience (i.e. what reaches the outside world)
        self.isNonRebase=False#Needs a slot per basis because it's either a cflow from NRs or it's calculated by whole array calc from NR cashflows (once for each NR basis)
        self.isWholeArray=False#NR or R whole array calcs; to distinguish from calcs that are not w/a but are stored for NR purposes
        self.overwrites=""#if the preceding is true, what calc does it overwrite.  Can only have an __NR overwriting another __NR
        self.isRebase=False#calculated by whole array calc by rebasing (once for each R basis)
        self.myPhase=None
        self.isConstant=False
        self.isInnerScenarios=False
        self.description=""#mainly used in error messages

class basisInfoObject:#might be OTT
    def __init__(self):
        self.name=""
        self.isRebase=False
        self.subBases=[]#list of names

class callInfoObject:
    def __init__(self):
        self.name=""
        self.stateInput=""#input call-state to call (of this submodel) (NB the only other input will be the top models current state)
        self.model=None
        self.phase=None
        self.term=0
        self.isStochastic=False
        self.innerScenarios=""#name of inner senarios call
        self.basis=""#basis name
        self.when=""#time expresssion
        self.returns="Both"#state, output, both e.g. not interested in final state(s) for an inner stochastic run
        self.stores=False#True==(stores=1)

class innerModelCallObject:
    def __init__(self):
        self.name=""#name of call
        self.model=""#the inner model
        self.numScens=0
        self.term=0
        self.basis=""#TODO how will this work?
        self.when=""#time expression
        self.theParams=[]#all the actual model parameters

class errorInfoObject:
    def __init__(self):
        self.ci=None#ref to calc info
        self.ln=0#line number in ci

class writer:
    def __init__(self):
        self.oput=None
        self.lineCount=0#of output
    def write(self,l):
        self.lineCount+=1
        self.oput.write(l)
        ei=errorInfoObject()
        global currentCalcInfoObject
        global currentCalcLine
        ei.ci=currentCalcInfoObject
        ei.ln=currentCalcLine
        errorInfos[l]=ei
    def close(self):
        self.oput.close()

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
topModel=None
off=writer()
off.oput=open(exeSubDir+"/"+"futhark.fut",'w')
callCount = 0

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
                    l="###,"+l[3:]
                    (ls, c, lsu) = nwscap(l, "=:,")
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
                    if lsu[i]=="CALL":
                        ci.isCall=True
                    if lsu[i]=="INNERSCENARIOS":
                        ci.isInnerScenarios=True
                    if lsu[i]=="OUTPUT":
                        ci.isOutput = True
                        if outputMode=="VECTOR":
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
                            arrStr=ls[i+1]
                            if lsu[i+1].__contains__(";"):#array has effective size given by data
                                ci.sizeMax=arrStr[arrStr.find(";")+1:][:-1]
                                arrStr=arrStr[:arrStr.find(";")]
                            (ll, _, llu) = nwscap(arrStr, "[]")
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
                    if lsu[i] == "__R1":
                        ci.stores = -1
                        ci.isRebase = True
                        ci.isWholeArray = False
                    if lsu[i] == "__R2":
                        ci.stores = -1
                        ci.isRebase = True
                        ci.isWholeArray = True
                    if lsu[i]=="OVERWRITES":
                        ci.overwrites=ls[i+1]
                    if lsu[i]=="CONSTANT":
                        ci.isConstant=True
                continue
            if section=="COMMON":
                mi.commonCode=mi.commonCode.__add__([l])
            if section=="BASIC":
                if not lsu[0] in allowableBasicParams:
                    doErr("Unknown basic parameter ",ls[0])
                if lsu[0]=="NAME":
                    mi.name=ls[1]
                    if lsu[1]=="TOP":
                        global topModel
                        topModel=mi
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
                if lsu[0] == "INNERMODEL":
                    mi.innerModel=ls[1]
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
                    if lsu[i] == "TERM":
                        mi.phaseTerm[currPhaseName] = ls[i + 1]
                        skipItem = True
            if section =="CALC":
                l=l.strip()
                if lsu[0]=="INITIALISE":
                    ci.initialisation=l
                else:
                    if firstLine:
                        firstLine=False
                        ci.lhs = l
                        ci.description = "Calc:" + ci.lhs + " Phase:" + ci.myPhase + " Model:"+mi.name
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
                    if inDims:
                        t.dims.append(ls[i])
                    elif lsu[i]=="DIMS":
                        inDims=True
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
                        if not dim.__contains__("int") and not enums.__contains__(dim):
                            doErr("Unknown dimension for table: ",l)
                        if dim=="int":
                            if dimCount==len(t.dims)-2:
                                t.dim1HasLB=True
                            else:
                                t.dim2HasLB=True
                        if dim=="int0":
                            dim="int"
                        dimCount += 1
                    if lsu[i]=="NAME":
                        t.name=ls[i+1]
                    if lsu[i]=="DIMS":
                        inDims=True
                        dimCount=0
                mi.tableInfos[t.name]=t
            if section=="ESG":
                (fieldInfo,_,_)=nwscap(l,"[]")
                if len(fieldInfo)==1:
                    mi.esg[fieldInfo[0]]=[1]
                else:
                    mi.esg[fieldInfo[0]] = [int(fieldInfo[i]) for i in range(1,len(fieldInfo))]
            if section=="INNERESG":
                (fieldInfo,_,_)=nwscap(l,"[]")
                if len(fieldInfo)==1:
                    mi.innerESG[fieldInfo[0]]=[1]
                else:
                    mi.innerESG[fieldInfo[0]] = [int(fieldInfo[i]) for i in range(1,len(fieldInfo))]

    ift.close()
    return mi

#read top-level model information
modelInfoFile=sys.argv[2]
ift = open(modelSubDir + "/" + modelInfoFile+".model", 'r')
section=""
sbVals={}#subbasis name->list of enum values
inSubBase=False
numScens=0
numInnerScens=0
firstRebasedBasis=0
scensFile=""
outputMode="VECTOR"
stochasticSummaryFunctions=[]#would be false e.g. for scr run, only applicable to dependent should always be true for independent stochastic
averageOverScenarios=False#applies to dependent only
individualOutput=False#applies to independent only
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
            if lsu[0] not in set(["MODE","STOCHASTIC","NUMSCENARIOS","NUMINNERSCENARIOS","FILE","OUTPUT","STOCHASTICSUMMARYFUNCTIONS","AVERAGEOVERSCENARIOS","INDIVIDUALOUTPUT"]):
                doErr("Unknown basic setting for top level model file: ",l)
            if lsu[0]=="MODE":
                if lsu[1] not in set(["DEPENDENT","INDEPENDENT"]):
                    doErr("Unknown mode in top level model file: ",l)
                isDependent=lsu[1]=="DEPENDENT"
            if lsu[0] == "STOCHASTIC":
                isStochastic=lsu[1]=="TRUE"
            if lsu[0] == "NUMSCENARIOS":
                numScens=int(lsu[1])
            if lsu[0] == "NUMINNERSCENARIOS":
                numInnerScens = int(lsu[1])
            if lsu[0] == "FILE":
                scensFile = ls[1]
            if lsu[0]=="OUTPUT":
                outputMode=lsu[1]
            if lsu[0]=="STOCHASTICSUMMARYFUNCTIONS":
                stochasticSummaryFunctions=[ll for ll in ls[1:]]
            if lsu[0]=="AVERAGEOVERSCENARIOS":
                averageOverScenarios= (False if lsu[1]=="FALSE" else True)
            if lsu[0] == "INDIVIDUALOUTPUT":
                individualOutput = (False if lsu[1] == "FALSE" else True)
        if section=="SUBBASE":
            if lsu[0]=="NAME":
                sbVals[ls[1]]=[]
                sbName=ls[1]
            else:
                sbVals[sbName]=sbVals[sbName].__add__([ls[0]])
            continue
        if section=="MODELS":
            modelInfos[ls[0]]=readBasicModelInfo(modelSubDir + "/" + ls[0] + ".model")
            if modelInfos[ls[0]].name=="top":#will not keep topModel with others
                del modelInfos[ls[0]]
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
                        if bi.isRebase and firstRebasedBasis==0:
                            firstRebasedBasis=numActualBases
                    if lsu[i] == "SUBBASE":
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

#in certain cases we might want to process the top model with the others
modelInfosPlus=modelInfos.copy()
if isDependent:
    modelInfosPlus["top"]=topModel
    for ph in topModel.phases.values():
        for ci in ph.values():
            if ci.isCall:
                off.write("let Call__" + ci.name + "=" + str(callCount) + nl)
                callCount += 1

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
off.write("let numMTItersPerBatchOfRNs="+str(numMTItersPerBatchOfRNs)+nl)

#inner ESG model code - added verbatim.  Also extract a function to return just the number of RNs per period.
rnpp=""
rnppAdd=False
if isDependent and topModel.innerModel!="":
    ift = open(libSubDir + "/" + topModel.innerModel+".fut", 'r')
    for l in ift.readlines():
        if l.__contains__("let "+topModel.innerModel+" "):#todo use regexp
            innerModelSignature=l.replace(":[][][]f32",":i32").replace(topModel.innerModel,topModel.innerModel+"_RNsPerPeriod")
            rnppAdd=True
        else:
            if rnppAdd:
                ll=l
                if l.__contains__("let RNsPerPeriod"):
                    ll=l.replace("let RNsPerPeriod","").replace("="," in ")
                    rnppAdd=False
                rnpp+=ll
        off.write(l)
    ift.close()
    off.write(nl+innerModelSignature+nl+rnpp+nl)

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

def subStoreAll(mtch,l,ci,mi,isCalcInThisPhase):#return substituted code for a reference to a s/a; ci is the reference we are converting
    #cases:
    # store-all not NR/R: present-this-phase, scalar:present(not this phase i.e. implied t)/past/future, array: time(as scalar) and explicit/implied index
    # store-all NR/R:  as above, but indexing will depend on basis (possibly implicit)
    #return (string to insert, first position after match to keep in original string)
    m=mtch.group()
    arrExp=m[0]+"storeAll["#add position in store-all: scalar, array __NR/R
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
                cont=bracketCount!=0
                if cont:
                    timeExp+=l[pos]
                pos+=1
            arrExp+=","+timeExp+"-firstprojectionperiod]"
            return(arrExp,pos)
        else:
            if isCalcInThisPhase:
                return (m,mtch.end()-1)#nothing to do case as we can just refer to the calc binding
            else:
                arrExp+=",as.i_t]"
                return (arrExp,mtch.end()-1)
    else:
        #is there a position index present or is it implicit? (we can omit both or position only; if 1 index is present it is time).  For both order is time then position.
        gotPosIndex=False
        gotTimeIndex=False
        endPos=mtch.end()-1
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
                cont=bracketCount!=0
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
                    cont = bracketCount != 0
                    if cont:
                        posExp += l[pos]
                    pos += 1
            endPos=pos
    if not gotTimeIndex and not ci.isNonRebase and not ci.isRebase and isCalcInThisPhase:
        arrExp =ci.name+"[i1]"#current time reference to arrayed.  TODO: this implies can only refer to an arrayed store-all at current time (i.e. before it is stored in the array) using implicit position, not explicit
        return (arrExp,mtch.end()-1)
    #no need to convert position into index as we have constants defined in the Futhark
    if gotPosIndex and gotTimeIndex:
        arrExp+="+"+posExp+","+timeExp+"-firstprojectionperiod]"
    elif gotTimeIndex:#recall: if got 1, it's time
        arrExp+="+i1,"+timeExp+"-firstprojectionperiod]"
    else:
        arrExp+="+i1,as.i_t]"
    return (arrExp,endPos)

#convert line of code - used in both code, initialisation and settting derived, does not apply to NR or R whole-array calcs
def convCode(mi,ci,codeType,theCalls=[]):#print converted code and return the expression to call to get the value - this could be a function call for an arrayed calc
    #get code depending on what we are converting
    global currentCalcInfoObject
    global currentCalcLine
    currentCalcInfoObject=ci
    currentCalcLine=0
    tempVarCount=0
    phName=ci.myPhase
    if codeType==INITIALISATION or codeType==DERIVED:
        pos = ci.initialisation.find("=")
        code = [ci.initialisation[pos + 1:]]
    else:
        code=ci.code.copy()
        code=[l for l in code if l.strip()!=""]
    if mi.phaseDirections[phName] == "static" or ((ci.isNonRebase or ci.isRebase) and ci.isWholeArray):
        off.write("let "+ci.name+" (storeAll:*[][]f32):*[][]f32=\n")#w/a case
    elif ci.lhs!="":
        off.write("\tlet " + ci.lhs + nl)  # start of assigment for ordinary case
    if ci.isArrayed:
        # the calc now becomes the inner-most internal function to be called by partial application
        off.write("\tlet " + ci.name + "_arr" + str(ci.numDims))
        for ind in range(1, ci.numDims + 1):  # array index parameters
            off.write(" (i" + str(ind) + ":i32) ")
        off.write(":"+("i" if ci.type!="real" else "f")+"32=\n")
    isQuoted=False
    for l in code:  # loop through lines
        currentCalcLine+=1
        if l[0:3]=="\"\"\"":#quoting/unquoting?
            isQuoted=not isQuoted
            l=l[3:]
            if l=="":
                continue
        if isQuoted:#quoted: write verbatim
            off.write(l)
            continue
        commPos = l.find("//")  # find and eliminate comments
        if commPos > 0:
            l = l[0:commPos]
        l = " " + l + " "#a frequent patern is alphanum_ terminated with !alphanum_.  This is to ensure that'll work at the start and end of the line
        l = re.sub("[a-zA-Z]\w*\s*=[^=]", lambda x: "let " + x.group(), l)  # let in front of binding
        l = convUserFn(l)  # format of calls to user-defined functions
        if len(code) > 1:#return of calc value
            l = l.replace("return ", "\tin ")
        else:
            l = l.replace("return ", "")
        l = re.sub("[\W]" + "Me__" + "[\W]",lambda x: x.group()[0] + "as.p.Me__" + x.group()[5:], l)#Me__
        l = re.sub("[\W]" + "Call__t" + "[\W]", lambda x: x.group()[0] + "asTop.Call__t" + x.group()[8:], l)#Call__t
        l = re.sub("[\W]" + "Call__" + "[\W]", lambda x: x.group()[0] + "asTop.Call__" + x.group()[7:], l)#Call__t
        haveTempVars=False
        if mi.name=="top" and theCalls!=[]:#replace calls to submodel calls with temporary variables. Options: Filtered/Unfiltered Stochastic(output)/Non(state).  Former is much harder: needs zipping with the input state in order to do filtering.
            doCalls=True
            while doCalls:#loop until no further cases found
                doCalls=False
                for call in theCalls:
                    itern = re.finditer("[\W]" + call.name +".", l)#find <call>.
                    for x in itern:
                        doCalls=True
                        haveTempVars=True
                        tempVarCount+=1
                        filter=""
                        pos= x.end()
                        fld=""
                        sPos=x.start()
                        while pos<=len(l)-1 and l[pos].isalnum():#build up field name
                            fld+=l[pos]
                            pos+=1
                        ePos=pos-1
                        if pos<=len(l)-1:
                            if l[pos]=="[":
                                pos+=1
                                brLevel=1
                                while True:
                                     if l[pos]=="[":
                                        brLevel+=1
                                     if l[pos]=="]":
                                        brLevel-=1
                                     if brLevel==0:
                                        ePos=pos
                                        break
                                     else:
                                         filter += l[pos]
                                         pos += 1
                        tempAssign = "let tempVar" + str(tempVarCount) + "="
                        if filter!="":
                            extraDotOne=""
                            if call.isStochastic:
                                extraDotOne=".1"
                            convertedFilter="\\x__x-> "+filter+" "
                            mi2=modelInfos[call.model]
                            for ph2 in mi2.phases.values():
                                for ci2 in ph2.values():
                                    for fld2 in ci2.fieldsCalcd:
                                        convertedFilter = re.sub("[\W]" + fld2 + "[\W]",lambda x: x.group()[0] +"(x__x"+ extraDotOne+".state__1." + fld2+")" + x.group()[len(fld2) + 1:], convertedFilter)
                            for df in mi2.dataFieldInfos.values():  # add as.p. (or d.) in front of data/derived fields
                                if df.expression == "":
                                    convertedFilter = re.sub("[\W]" + df.name + "[\W]",lambda x: x.group()[0] +"(x__x"+ extraDotOne + ".p." + df.name +")"+ x.group()[len(df.name) + 1:], convertedFilter)
                                else:
                                    convertedFilter = re.sub("[\W]" + df.name + "[\W]",lambda x: x.group()[0] +"(x__x"+ extraDotOne + ".der." + df.name+")" + x.group()[len(df.name) + 1:], convertedFilter)
                        if call.isStochastic:
                            oputPosn=0
                            mi2 = modelInfos[call.model]
                            for ph2 in mi2.phases.values():
                                for ci2 in ph2.values():
                                    if ci2.isOutput:
                                        for fld2 in ci2.fieldsCalcd:
                                            if fld2==fld:
                                                break
                                            else:
                                                oputPosn+1
                            if filter=="":
                                tempAssign+="sum "+call.name+"_output[:,"+str(oputPosn)+"]"
                            else:
                                tempAssign +="sum (((unzip (filter ("+convertedFilter+")"+" (zip "+call.stateInput+"_state "+call.name+"_output))).2)[:,"+str(oputPosn)+"])"
                        else:
                            if not topModel.dataFieldInfos.__contains__(fld):
                                fldPrefix="state__1."
                            else:
                                if topModel.dataFieldInfos[fld].expression!="":
                                    fldPrefix="der."
                                else:
                                    fldPrefix="p."
                            if filter=="":
                                tempAssign+="sum (map (."+fldPrefix+fld+")"+call.name+"_state)"
                            else:
                                tempAssign +="sum (map (."+fldPrefix+fld+") (filter ("+convertedFilter+")"+call.name+"_state))"
                        off.write(tempAssign+nl)
                        l=l[:sPos+1]+"tempVar" + str(tempVarCount)+l[ePos+1:]
                        break#only do one occurence as changing the string
                    if doCalls:
                        break#as doing only 1 occurence
        for kt in mi.tableInfos.keys():  # convert table name to name of parameter of main
            l = re.sub("[\W]" + kt + "[\W]",lambda x: x.group()[0] + "table_" + kt + "_" + mi.name + x.group()[len(kt) + 1:], l)
        for (kt,vt) in mi.tableInfos.items():  # add basis index, if required
            if vt.basis!="SINGLE":
                tbl = "table_" + kt + "_" + mi.name+"\["
                l = re.sub(tbl,lambda x: x.group()+"basisNum,", l)
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
                    for i in range(0,len(vt.dims)+(0 if vt.basis=="SINGLE" else 1)-2):#skip all but the last two dimensions
                        while True:#scan forward, look for bracket-level-0 (not the brackets of this table itself but any in index-expressions)
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
        for df in mi.dataFieldInfos.values():  # add as.p. (or d.) in front of data/derived fields
            dfPrefix="as.p."
            if codeType==DERIVED:
                dfPrefix="d."
            if df.expression == "":
                l = re.sub("[\W]" + df.name + "[\W]",lambda x: x.group()[0] + dfPrefix + df.name + x.group()[len(df.name) + 1:], l)
            else:
                l = re.sub("[\W]" + df.name + "[\W]",lambda x: x.group()[0] + "as.der." + df.name + x.group()[len(df.name) + 1:], l)
            if df.arraySize>0:#implict index
                l = re.sub("[\W]" + df.name + "[\W]",lambda x: (x.group() if (x.end()!=len(l)-1 and x.group()[-1]=="[")  else (x.group()[:-1]+"[i1]"+x.group()[-1])),l)
        l = re.sub("[\W]" + "t" + "[\W]", lambda x: x.group()[0] + "as.t" + x.group()[2:], l)  # "t"
        l = re.sub("[\W]" + "basisNum" + "[\W]", lambda x: x.group()[0] + "as.basisNum" + x.group()[9:], l)  # basis
        if mi.phaseDirections[phName] == "static" or ((ci.isNonRebase or ci.isRebase) and ci.isWholeArray):
            # static phase or __NR/R2 - need whole arrays.  See below for more explanation
            fpos=0
            for udf in userDefinedFns:  # find (the only) user defined function and insert storeAll
                if l.find(udf) > 0:
                    fpos = l.find(udf) + len(udf)
                    break
            l = l[:fpos] + " storeAll " + l[fpos:]
        #reference to top model
        l = re.sub("[\W]" + "top.",lambda x: x.group()[0] + "asTop.state__1.", l)#TODO only allows present (just before call to sub-model) values in top.  Also, ignores possibility of top and submodel calcs having the same names
        # references to other calcs
        for (phName2, ph2) in mi.phases.items():
            for ci2 in ph2.values():
                if ci2.isConstant:#constant - check for "present" values
                    for fld in ci2.fieldsCalcd:
                        l = re.sub("[\W]" + fld + "[\W]",lambda x: x.group()[0] + "as.state__1." + fld + x.group()[len(fld) + 1:], l)
                elif mi.phaseDirections[phName] != "static" and not ((ci.isNonRebase or ci.isRebase) and ci.isWholeArray):#not w/a calc
                    if not ci2.isArrayed and ci2.stores!=-1:
                        #scalar (not s/a): only need to check for past values, could be a tuple
                        for past in range(1, ci2.stores + 1):
                            for fld in ci2.fieldsCalcd:
                                l = re.sub("[\W]" + fld + "__" + str(past) + "[\W]",lambda x: x.group()[0] + "as.state__" + str(past) + "." + fld + x.group()[len(fld + "__" + str(past)) + 1:],l)
                    if ci2.isArrayed and ci2.stores != -1:
                        #array (not s/a): check for past values and for implied array indices (1d only)
                        for past in range(1, ci2.stores + 1):
                            sp=str(past)
                            l = re.sub("[\W]" + ci2.name + "__" + sp + "[\W]",lambda x: x.group()[0] + "as.state__" + sp + "." + ci2.name + x.group()[len(ci2.name + "__" + sp) + 1:],l)
                        l = re.sub("[\W]" + ci2.name + "[\W]",lambda x: (x.group() if (x.end()!=len(l)-1 and x.group()[-1]=="[")  else (x.group()[:-1]+("[i1]" if ci.isArrayed else "")+x.group()[-1])),l)
                    if ci2.stores==-1:
                        empty=False
                        ll=l#convert this but whittle it down as we get matches so as to avoid infinite loops matching the same thing over
                        l=""#build this up from converted strings
                        while not empty:#use finditer to get an occurence of the pattern but abandon the loop after processing it as the string will have changed
                            empty=True
                            itern = re.finditer("[\W]" + ci2.name + "[\W]", ll)
                            for x in itern:
                                empty=False
                                (stri,ep)=subStoreAll(x,ll,ci2,mi,phName2==ci.myPhase)#new string to insert plus posn of remainder of line
                                l+=ll[:x.start()]+stri
                                ll=ll[ep:]
                                break#only do one find-iter as l has changed
                        l+=ll#add unconverted rump back on
                else:
                    #w/a calcs - we already added storeAll above
                    #pattern=fn <arrays> <tables>: add in "storeAll", sa->sa indices (if arrayed), sa[i]-> 1 index (for arrayed).  The remaining params should be tables only and are assumed to "match up" FTB.  They should already have been converted.
                    #NB <arrays> might well include the name of this calc itself - it depends on what the Futhark w/a function requires
                    #NB: when converting the surrouding calc, will need to wrap in a fn taking and returning storeAll
                    if ci2.stores==-1:
                        empty=False
                        while not empty:#same logic as above iro finditer
                            empty=True
                            itern = re.finditer("[\W]" + ci2.name + "[\W]", l)
                            for x in itern:
                                #4 cases: scalar + 3 array cases: has index: translate it (could be a range, i.e. has a colon), no index: supply all
                                if not ci2.isArrayed and not ci2.isNonRebase and not ci2.isRebase:
                                    stri="i_"+mi.name+"_"+ci2.name#scalar
                                    ep=x.end()
                                elif x.group()[-1]!="[":#no index
                                    if not ci2.isNonRebase and not ci2.isRebase:#not a __NR2/__R2
                                        ind="i_"+mi.name+"_"+ci2.name
                                        stri="(steps "+ind+" ("+ind+"_end-"+ind+"+1) 1)"#all array
                                        ep=x.end()
                                    else:
                                        #it's __NR2/__R2: the default in this case is for the range of the basis (plus subbases, if they exist) - not the whole calc - need an if..then bacause the NR/R basis will have different numbers of subbases
                                        #hmm... now no longer sure that that is what we want
                                        #stri="i_"+mi.name+"_"+ci2.name+"+.("
                                        #bn=0
                                        #elsie=""
                                        #bnr=0
                                        #for b in bases.values():
                                        #    if (ci2.isRebase and b.isRebase) or  (ci2.isNonRebase and not b.isRebase):
                                        #        stri+=elsie+"if as.basisNum=="+str(bn)+" then ("+str(bnr)+"..."+(str(bnr) if b.subBases == [] else str(bnr+len(b.subBases)-1))+")\n"
                                        #        elsie=" else "
                                        #        bnr += (1 if b.subBases == [] else len(b.subBases))
                                        #    bn += (1 if b.subBases == [] else len(b.subBases))
                                        #stri+="else [0])"#dummy, in case there's only 1 rebased basis
                                        ind="i_"+mi.name+"_"+ci2.name
                                        stri=" ("+ind+"..."+ind+"_end) "#all array
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
                                        stri="(i_"+mi.name+"_"+ci2.name+"+"+elt+")"#can use a number,an enum or a basis name (which have already been assigned constants, so no need for any conversion)
                                    else:
                                        elts=str.split(":")
                                        ind1 = " (i_" + mi.name + "_" + ci2.name+"+"+elts[0]+") "
                                        ind2 = " (i_" + mi.name + "_" + ci2.name+"+"+elts[1]+") "
                                        stri="(steps "+ind1+" ("+ind2+"-"+ind1+")"+ " 1)"#range
                                    ep=pos+1
                                l = l[:x.start()] + stri + l[ep:]
                                empty=False
                                break#next iter as string changed
        l.replace("][",",")#any left over ][ from multi-d arrays (but not tables).  Come to think of it, does it make any difference in Futhark?  It does as you need e.g. (x[0])[1]
        if haveTempVars and len(code)==1:
            off.write(" in ")
        off.write(l+nl)
    if ci.isArrayed and mi.phaseDirections[phName] != "static":#multi-level mappings for arrayed
        for ind in range(1, ci.numDims):  # loop over map functions
            off.write("let " + ci.name + "_arr" + str(ci.numDims - ind))
            for ind2 in range(1, ci.numDims - ind + 1):  # loop over parameters of a map function
                off.write(" (i" + str(ind2) + ":i32) ")
            off.write(":" + multiBracket[ind] +("i" if ci.type!="real" else "f")+ "32=map (" + ci.name + "_arr" + str(
                ci.numDims - ind + 1) + " ")  # partial application of previous mapping function
            for ind2 in range(1, ci.numDims - ind + 1):  # partial application (2)
                off.write(" i" + str(ind2) + " ")
            off.write(") (iota " + str(
                ci.dimSizes[ci.numDims - ind]) + ") \n")  # the iota to which we apply the partial application
        if ci.sizeMax=="":
            off.write("in map " + ci.name + "_arr1 (iota " + str(ci.dimSizes[0]) + ")\n")#fixed array size
        else:
            off.write("in map " + ci.name + "_arr1 (iota " + "as.p."+ci.sizeMax + ")\n")#array with maximum size but upper bound for calcs given by data
    currentCalcInfoObject=None

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

if not isDependent:
    mName=list(modelInfos.keys())[0]
    indModel=modelInfos[mName]

numOutputs=0#allow for array size (1d only)
mi=(topModel if isDependent else indModel)
outputNames=[]
for ph in mi.phases.values():
    for ci in ph.values():
        if ci.isOutput:
            if not ci.isArrayed:
                for fld in ci.fieldsCalcd:
                    outputNames=outputNames.__add__(["\""+fld+"\""])
                    numOutputs+=1
            else:
                numOutputs+=ci.dimSizes[0]
                for i in range(0,ci.dimSizes[0]):
                    outputNames = outputNames.__add__(["\""+ci.name+"["+str(i)+"]"+"\""])
off.write("let numOutputs:i32="+str(numOutputs)+nl)

#number of outputs for submodels - for stochastic
for mi in modelInfos.values():
    numOutputs2=0
    for ph in mi.phases.values():
        for ci in ph.values():
            if ci.isOutput:
                if not ci.isArrayed:
                    numOutputs2+=1
                else:
                    numOutputs2+=ci.dimSizes[0]
    off.write("let numOutputs_"+mi.name+":i32="+str(numOutputs2)+nl)

#enums
off.write(nl)
for enum in enums.values():
    for (k,v) in enum.items():
        off.write("let "+k+":i32="+str(v)+nl)

#other system constants
off.write("let firstProjectionPeriod:i32=("+str(mi.firstProjectionPeriod)+")"+nl)
off.write("let lastProjectionPeriod:i32=(" + str(mi.lastProjectionPeriod) + ")" + nl)
off.write("let numPeriods:i32=lastProjectionPeriod-firstProjectionPeriod+1" + nl)
off.write("let numScens:f32="+str(numScens)+nl)
off.write("let firstprojectionperiod:i32=("+str(mi.firstProjectionPeriod)+")"+nl)#don't remove me, I'm not a duplicate!
off.write("let lastprojectionperiod:i32=(" + str(mi.lastProjectionPeriod) + ")" + nl)
numPeriods=mi.lastProjectionPeriod-mi.firstProjectionPeriod+1

#data-record types (does not apply to top)
off.write(nl)
for mi in modelInfos.values():
    off.write("type data_"+mi.name+"={"+nl+"Me__:int,"+nl)
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

#data conversion functions (does not apply to top)
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
    off.write("map3 (\\x y i:data_"+mi.name+"->{"+dataFieldsInt+dataFieldsReal+",Me__=i}) dataInt dataReal (iota nr)"+nl)

#derived types (does not apply to top)
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

# various state types including containers for past values and the all-state.  This does apply to top, but top also needs state from calls (i.e.all-states from sub-model types)
haveAll=False
for mi in modelInfosPlus.values():
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
    anyField=False#in case there is no state (e.g. in the top model t=0 only)
    for ph in mi.phases.values():
        for ci in ph.values():
            if not ci.isCall:
                if ci.stores > 0 or (ci.isOutput and outputMode=="SCALAR") or ci.isConstant:
                    anyField=True
                    typ = "int"
                    if ci.type == "real":
                        typ = "real"
                    brackets = ""
                    for i in range(0, ci.numDims):
                        brackets = brackets + "[" + str(ci.dimSizes[i]) + "]"
                    for fld in ci.fieldsCalcd:
                        off.write(comma + fld + ":" + brackets + typ + nl)
                        comma = ","
            else:#it's a call
                if ci.stores>0:
                    anyField=True
                    l = ci.code[0]#find submodel (bit of a hack, we will analyse calls properly later in the top-modelcode generation)
                    if l.strip() == "":
                        l = ci.code[1]
                    (ls, _, _) = nwscap(l, "=,")
                    for i in range(0, len(ls)):
                        if ls[i].upper()=="MODEL":
                            subModel=ls[i+1]
                            break
                    if not l.__contains__("stochastic=true"):
                        off.write(comma+ci.name+":[]state_"+subModel+"_all"+nl)
                    else:
                        off.write(comma + ci.name + ":[][]f32" + nl)
                    comma=","
    if not anyField:#add dummy field to prevent empty type
        off.write("x__zog:f32")
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
    off.write("t:i32,\n")#actual time
    off.write("i_t:i32,\n")#time for indexing s/as
    off.write("forceTheIssue:f32,\n")
    if mi is topModel:
        off.write("Call__:i32,Call__t:i32,")
    off.write("basisNum:i32\n}\n")

    #constants giving indexes into the store_all array (the start, for an array)
    i_count=0
    off.write(nl)
    i_added=True#need to order by overwriting so keep on looping whilst still adding indices that overwrite
    inds_added={}
    while i_added:
        i_added=False
        for (phName,ph) in mi.phases.items():
            for ci in ph.values():
                if mi.phaseDirections[phName]=="static":
                    ci.stores=-1
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
                            off.write("let i_"+mName+"_"+fld+":i32="+str(i_count)+nl)
                        if ci.isRebase:
                            i_count+=numRebased
                        elif ci.isNonRebase:
                            i_count+=numNonRebased
                        else:
                            i_count+=(ci.dimSizes[0] if ci.isArrayed else 1)
                        off.write("let i_"+mName+"_"+fld+"_end:i32="+str(i_count-1)+nl)
                    elif inds_added.__contains__(ci.overwrites):
                        i_added=True
                        off.write("let i_" + mName + "_" + ci.name + ":i32=" + str(inds_added[ci.overwrites]) + nl)
                        off.write("let i_" + mName + "_" + ci.name + "_end:i32=i_" + mName +"_"+ci.overwrites+"_end" + nl)
                        inds_added[ci.name]=inds_added[ci.overwrites]
off.write("let numSAs:i32="+str(i_count)+nl)

#scenario type and conversion function (including inner scenarios, if present)
hasESG=False
mi=(topModel if isDependent else indModel)
for i in range(0,(2 if isDependent else 1)):#scen, inner scen
    if i==0 and mi.esg!={} or i==1 and mi.innerESG!={}:
        hasESG=True
        esgt=("Inner" if i==1 else "")
        esg=(mi.esg if i==0 else mi.innerESG)
        off.write("\ntype oneScen"+esgt+"={\n")#scenario type
        comma=""
        for (k,v) in esg.items():
            off.write(comma+k+":[]")
            if v!=[1]:
                for i in v:
                    off.write("["+str(i)+"]")
            off.write("f32\n")
            comma=","
        off.write("}\n\n")
        off.write("let oneScen"+esgt+"FromArray [np][nc] (scen:[np][nc]f32): oneScen"+esgt+"=\n")#convert one scenario (1 index of the outer dimension of the scenario file) to a oneScen
        colCount=0
        for (k,v) in esg.items():#get arrays
            if v==[1]:#scalar
                off.write("\tlet "+k+"=scen[:,"+str(colCount)+"]"+nl)
                colCount+=1
            elif len(v)==1: #vector
                off.write("\tlet "+k+"=scen[:,"+str(colCount)+":"+str(colCount+v[0])+"]"+nl)
                colCount+=v[0]
            else: #matrix (grid)
                off.write("\tlet "+k+"=map (unflatten "+str(v[0])+" "+str(v[1])+") scen[:,"+str(colCount)+":"+str(colCount+v[0]*v[1])+"]"+nl)
                colCount+=v[0]*v[1]
        off.write("\n\tin\n\t{")
        comma=""
        for (k,v) in esg.items():#pack arrays in record
            off.write(comma+k+"="+k)
            comma=","
        off.write("}\n")
        off.write("\nlet scens"+esgt+"FromArrays(scens: [][][]f32):[]oneScen"+esgt+" =\n")#convert whole scenario file to array of oneScens
        off.write("\tmap oneScen"+esgt+"FromArray scens\n")

#main function
off.write(nl)
off.write("let main ")
if numActualBases>1:
    off.write(" [numBases] ")
for mi in modelInfos.values():#data files
    if mi.hasData:
        off.write(" [numPols"+("_"+mi.name if not isDependent else "")+"] ")
        break
if hasESG:
    off.write(" (scensData:[][][]f32) ")
for mi in modelInfos.values():#data files
    if mi.hasData:
        off.write("(fileDataInt_"+mi.name+":[numPols"+("_"+mi.name if not isDependent else "")+"][]i32) (fileDataReal_"+mi.name+":[numPols"+("_"+mi.name if not isDependent else "")+"][]f32)")
for mi in modelInfosPlus.values():#tables and their lower bounds (for (possibly) inner 2 dimensions)
    for t in mi.tableInfos.values():
        off.write(" (table_"+t.name+"_"+mi.name+":"+("[numBases]" if t.basis!="SINGLE" else "")+multiBracket[len(t.dims)]+"f32)"+(" (lb_"+t.name+"_"+mi.name+":[]i32)" if t.dim1HasLB or t.dim2HasLB else ""))
if not isDependent:
    off.write(":"+("[]" if outputMode=="VECTOR" else "")+("[]" if individualOutput else "")+"[]f32="+nl)#independent: item (x time) (always average of scens)
else:
    off.write(":"+("[]" if not averageOverScenarios else "")+"[]f32="+nl)#dependent: item (x scen, if not averaging) (output over time not allowed; however, could fake it using an arrayed calc)

off.write("\nunsafe\n\n")

#Are there NR or R bases?
haveNR=False
haveR=False
if not isDependent:
    for b in bases.values():
        if b.name!="Experience" and not b.isRebase:
            haveNR=True
        if b.name!="Experience" and b.isRebase:
            haveR=True

#rebase times
if haveR:
    off.write("\nlet rbtrue=replicate (length rebaseTimes) true" + nl)
    off.write("let rbts:*[]bool = replicate numPeriods" + " false " + nl)
    off.write("let isRebaseTime:*[]bool=(replicate (-firstprojectionperiod) false)++(scatter rbts rebaseTimes rbtrue)\n")#NB add falses to front for -ve start times

# create dummy calcInfo for use in common code and setDerived, no need to set fields (defaults are fine) except code and that is set at the point of use
dummyCi=calcInfoObject()
dummyCi.myPhase="phase0"

#convert (outer) scenarios
if hasESG:
    off.write("let scens=scensFromArrays scensData"+nl)
    #cut down the outer scenarios so they have the same format as the inner (they are supposed to be a super-set of the inner scenarios, so essentially exclude params for inner model)
    if isDependent:
        off.write("let scenToInner (scen:oneScen):oneScenInner=\n")
        off.write("{")
        comma=""
        for (k,v) in topModel.innerESG.items():
            off.write(comma+k+"=scen."+k+nl)
            comma=","
        off.write("}"+nl)
        off.write("let scensAsInner=map scenToInner scens"+nl)

#common code - i.e outside calcs - can really access only tables or call user-defined functions (there are no assumptions or checks about dependencies betwen models)
for mi in modelInfosPlus.values():
    dummyCi.code=mi.commonCode
    dummyCi.lhs=""
    convCode(mi, dummyCi, CALCCODE)
    off.write(nl)

#derived setting functions (inside main because they might use tables or scenarios)
for mi in modelInfos.values():
    if mi.hasDerived:
        off.write("\nlet setDerived_"+mi.name+"(d:data_"+mi.name+"):derived_"+mi.name+"="+nl)
        for df in mi.dataFieldInfos.values():  # set temporary variables to derived expressions
            if df.expression != "":
                dummyCi.name=df.name
                dummyCi.lhs=df.name+"="
                dummyCi.initialisation=df.expression
                if df.arraySize>0:
                    dummyCi.isArrayed=True
                    dummyCi.numDims=1
                    dummyCi.dimSizes=[df.arraySize]
                convCode(mi, dummyCi, DERIVED)
        comma=""
        off.write("in {"+nl)#now create record
        for df in mi.dataFieldInfos.values():
            if df.expression!="":
                off.write(comma+df.name+"="+df.name+nl)
                comma=","
        off.write("}" + nl)  # now create record

#bind constants to array LBs to avoid excess indexing
off.write(nl)
for mi in modelInfosPlus.values():
    for t in mi.tableInfos.values():
        if t.dim2HasLB or t.dim1HasLB:
            off.write("let lb_"+t.name+"_"+mi.name+"_1="+(" lb_"+t.name+"_"+mi.name+"[0]" if t.dim2HasLB else "0i32")+nl)
            off.write("let lb_"+t.name+"_"+mi.name+"_2="+(" lb_"+t.name+"_"+mi.name+"[1]" if t.dim1HasLB else "0i32")+nl)
off.write(nl)

#get data
off.write(nl)
for mi in modelInfos.values():
    if mi.hasData:
        off.write("let fileData_"+mi.name+"=dataFromArrays_"+mi.name+" fileDataInt_"+mi.name+" fileDataReal_"+mi.name+nl)

#get derived
for mi in modelInfos.values():
    if mi.hasDerived:
        off.write("let derived_"+mi.name+"=map setDerived_"+mi.name+" fileData_"+mi.name+nl)

#initialisation functions for setting initial state based on whether we want resume from where we left off in the (non-static) previous phase, or not.
#two functions actually, for state and for store-alls
for initMode in range(0,(1 if not haveAll else 2)):#ordinary, store-all
    for mi in modelInfosPlus.values():
        for (phName,ph) in mi.phases.items():#init fn for a phase
            if mi.phaseDirections[phName]=="static":
                continue#no initialisation for static, as it's not a run through time
            off.write("\nlet init_"+mi.name+"_"+phName+("_storeAll" if initMode==1 else ""))
            if initMode==1:
                off.write(" (nrBasisNum:i32) ")
            off.write(" (as: state_"+mi.name+"_all) ")
            if hasESG:
                off.write(" (scen:oneScen) ")
            if haveAll:
                off.write(" (storeAll:*[][]f32) ")
            if initMode==0:#returns
                if haveAll:
                    off.write(":(state_"+mi.name+",*[][]f32)=\n")#return tuple with s/a, if we have s/a's
                else:
                    off.write(":state_"+mi.name+"=\n")
            else:
                off.write(":*[][]f32=\n")
            inited=set()#who was initialised; for with" purposes
            for ci in ph.values():
                initCode=""
                if ci.isCall or ci.isInnerScenarios:
                    continue
                if (initMode==0 and ci.stores>0 or initMode==1 and ci.stores==-1) and ci.initialisation!="":
                    convCode(mi,ci,INITIALISATION)
                    for fld in ci.fieldsCalcd:#record which calcs were initialised (used with "with" in state creation)
                        inited.add(fld)
                if (initMode==0 and ci.isConstant):
                    convCode(mi,ci,CALCCODE)
                    for fld in ci.fieldsCalcd:
                        inited.add(fld)
            if initMode==0:#can always use "with" as we always create a zeroised state before any initialisations
                if len(inited)!=0:
                    off.write("\nin "+("(" if haveAll else "")+"(as.state__1")
                    for ci in inited:
                        off.write(" with "+ci+"="+ci)
                    off.write(")"+(",storeAll)" if haveAll else ""))
                    off.write(nl)
                else:
                    if haveAll:
                        off.write("\n (as.state__1,storeAll) "+nl)
                    else:
                        off.write(" as.state__1 "+nl)
            else:
                #storing in store-all; 3 cases: scalar (and that includes __NR, in this case), genuine array
                off.write("let sa=storeAll\n")
                for ci in ph.values():
                    if ci.stores ==-1 and ci.initialisation!="" :
                        if not ci.isArrayed and not ci.isNonRebase:
                            off.write(" with [i_"+mi.name+"_"+ci.name+","+mi.phaseStart[phName]+"-firstProjectionPeriod]="+ci.name+nl)
                        elif ci.isArrayed:
                            for ind in range(0,ci.dimSizes[0]):
                                off.write(" with [i_"+mi.name+"_"+ci.name+"+"+str(ind)+","+mi.phaseStart[phName]+"-firstProjectionPeriod]="+ci.name+"["+str(ind)+"]"+nl)
                        else:
                            off.write(" with [i_"+mi.name+"_"+ci.name+"+nrBasisNum,"+mi.phaseStart[phName]+"-firstProjectionPeriod]="+ci.name+nl)
                off.write("in sa\n")

#function to initialise the all-state on latter phases.  Sets state and start time.  Probably silly to have separate function for this as it does so little.
off.write(nl)
for mi in modelInfos.values():
    for (phName, ph) in mi.phases.items():
        if mi.phaseDirections[phName] == "static":
            continue  # no initialisation for static, as it's not a run through time
        off.write("\nlet init_" + mi.name + "_" + phName+"_all")
        off.write(" (as: state_" + mi.name + "_all) ")
        if hasESG:
            off.write(" (scen:oneScen) ")
        off.write("( nrBasisNum:i32 )")
        if haveAll:
            off.write(" (storeAll:*[][]f32) ")
            off.write(" :(state_"+mi.name+"_all,*[][]f32) ="+nl)
            off.write("\tlet (state_bf,sa)= init_"+ mi.name + "_" + phName+" as "+(" scen " if hasESG else "")+ " storeAll \n")
            off.write("\tin ((as with state__1=state_bf"+ ("),sa)" if mi.phaseStart[phName]=="previousTime" else " with t="+mi.phaseStart[phName]+" with i_t="+mi.phaseStart[phName]+"-firstprojectionperiod),sa)")+nl)
        else:
            off.write(" :state_" + mi.name+"_all="+nl)
            off.write("\tlet state_bf= init_"+ mi.name + "_" + phName+" as "+(" scen " if hasESG else "")+nl)
            off.write("\tin (as with state__1=state_bf"+ (")" if mi.phaseStart[phName]=="previousTime" else " with t="+mi.phaseStart[phName]+" with i_t="+mi.phaseStart[phName]+"-firstprojectionperiod)")+nl)

#function to run an entire static phase (storeAll->storeAll)
for mi in modelInfos.values():
    for (phName,ph) in mi.phases.items():
        if mi.phaseDirections[phName]=="static":
            off.write(nl)
            off.write("let  runStaticPhase_"+mi.name+"_"+phName+" (storeAll:*[][]f32) :*[][]f32=\n")
            revd=[]
            for ci in ph.values():#order is "just as it comes" (TODO make sure dict does not mess up the order)
                revd=revd+[ci.name]
                convCode(mi, ci, CALCCODE)  # write calc's code, this case a storeAll->storeAll fn
            call="storeAll"
            for fn in revd:#call of call of...
                call=fn+"("+call+")"
            off.write("in "+call+nl)

#functions to run one period (non-static phases)
for mi in modelInfos.values():
    for (phName,ph) in mi.phases.items():
        if mi.phaseDirections[phName]!="static":
            off.write(nl)
            off.write("let runOnePeriod_"+mi.name+"_"+phName+("" if not isDependent else " (asTop:state_top_all) ")+(" (scen:oneScen"+("Inner" if isDependent else "")+") " if hasESG else "")+" (as:state_"+mi.name+"_all)"+(" (storeAll:*[][]f32):" if haveAll else ":"))
            if haveAll:
                off.write(" (state_"+mi.name+"_all,*[][]f32)="+nl)
            else:
                off.write(" state_"+mi.name+"_all="+nl)
            #get dependencies of calcs
            whoCallsWhom = {}
            for ci in ph.values():
                if ci.isConstant:#constant calcs are not in runOnePeriod
                    continue
                iCall = []
                for ci2 in ph.values():  # does ci use ci2?
                    if ci2.isConstant:  # constant calcs are not in runOnePeriod
                        continue
                    found = False
                    for fld in ci2.fieldsCalcd:  # or rather, does it use ci2's calculated fields
                        for l in ci.code:
                            for mtch in re.finditer("[\W]" + fld + "[\W]", " " + l + " "):
                                found = True
                    if found:
                        iCall.append(ci2.name)
                whoCallsWhom[ci.name] = iCall
            #write out calcs - but not __NR2 or __R2
            while whoCallsWhom != {}:
                planted=False
                for (caller, callees) in whoCallsWhom.items():
                    if callees == []:  # first calc with no ancestors
                        planted=True
                        if not ph[caller].isWholeArray:#i.e. if ignore it's a __NR2
                            convCode(mi,ph[caller],CALCCODE)#write calc's code
                            off.write(nl)
                        for l in whoCallsWhom.values():  # remove this from its users
                            if l.__contains__(caller):
                                l.remove(caller)
                        del whoCallsWhom[caller]
                        break
                if not planted:
                    doErr("Circular calculations",mi.name+" "+phName)

            #storage function
            off.write("let store (as:state_"+mi.name+"_all) "+("(storeAll:*[][]f32):" if haveAll else ":"))
            if haveAll:
                off.write(" (state_" + mi.name + "_all,*[][]f32)=" + nl)
            else:
                off.write(" state_" + mi.name + "_all=" + nl)
            for i in range(mi.maxStored ,0,-1):#stored states
                off.write("let state__"+str(i)+"=as.state__"+str(i))
                for ci in ph.values():
                    if ci.stores >= i or (i==1 and ci.isOutput and outputMode=="SCALAR"):
                        for fld in ci.fieldsCalcd:
                            off.write(" with "+fld+"="+("as.state__"+str(i-1)+"." if i>1 else "")+fld)
                off.write(nl)
            off.write("let asNew=as "+nl)#new all-state
            for i in range(1, mi.maxStored + 1):
                off.write(" with state__"+str(i)+"=state__"+str(i))
            if mi.phaseDirections[phName] == "forwards":#time
                off.write(" with t=as.t+1")
                off.write(" with i_t=as.i_t+1"+nl)
            else:
                off.write(" with t=as.t-1")
                off.write(" with i_t=as.i_t-1" + nl)
            #update the store-all
            if haveAll:
                off.write("let storeAllNew= if ")#write __NR only when in NR bases
                for b in bases.values():
                    if b.name=="Experience":
                        off.write("as.basisNum==0 then storeAll "+nl)
                        bNum = 1
                    else:
                        off.write("\n else if as.basisNum=="+str(bNum)+" then storeAll "+nl)
                        bNum+=(len(b.subBases) if b.subBases!=[] else 1)
                    for ci in ph.values():
                        if ci.stores ==-1 and not ci.isRebase and not ci.isNonRebase:#not __NR/__R - do always
                            if not ci.isArrayed:
                                off.write("\t with [i_"+mi.name+"_"+ci.name+",as.i_t]="+ci.name+nl)
                            else:
                                for dim in range(0,ci.dimSizes[0]):
                                    off.write("\t with [i_" + mi.name + "_" + ci.name + "+"+str(dim)+",as.i_t]=" + ci.name+"["+str(dim)+"]"+nl)
                        if ci.stores ==-1 and ci.isNonRebase and not ci.isWholeArray and b.name!="Experience" and not b.isRebase:#put __NRs in correct slots, including allowing for  subbases
                            for sb in range(0,(len(b.subBases) if b.subBases!=[] else 1)):#loop through subbases, if any
                                off.write("\t with [i_" + mi.name + "_" + ci.name+"+as.basisNum+"+str(sb) + ",as.i_t]=" + ci.name+nl)
                        if ci.stores ==-1 and ci.isRebase and not ci.isWholeArray and b.name!="Experience" and b.isRebase:#put __Rs in correct slots, including allowing for  subbases
                            for sb in range(0,(len(b.subBases) if b.subBases!=[] else 1)):#loop through subbases, if any
                                off.write("\t with [i_" + mi.name + "_" + ci.name+"+as.basisNum-"+str(firstRebasedBasis)+"+"+str(sb) + ",as.i_t]=" + ci.name+nl)
                off.write("else storeAll\n")#dummy else to finish off the if's
                off.write(nl)
                off.write("in (asNew,storeAllNew)"+nl)
                off.write("in store as storeAll\n")#return from runOnePeriod
            else:
                off.write("in asNew"+nl)
                off.write("in store as \n")#return from runOnePeriod

#functions (used in bases) to run N periods
for mi in modelInfos.values():
    for (phName,ph) in mi.phases.items():
        if mi.phaseDirections[phName]!="static":
            off.write(nl)
            if haveAll:
                off.write("let runNPeriods_"+mi.name+"_"+phName+("" if not isDependent else " (asTop:state_top_all) ")+("(scen:oneScen"+("Inner" if isDependent else "")+")" if hasESG else "")+" (n:i32) (as:state_"+mi.name+"_all) (storeAll:*[][]f32):")
                off.write(" (state_" + mi.name + "_all,*[][]f32)=" + nl)
                off.write("\tloop (as':state_"+mi.name+"_all,storeAll':*[][]f32)=\n")
                off.write("\t(as,storeAll) for i<n do\n")
                off.write("\trunOnePeriod_"+mi.name+"_"+phName+("" if not isDependent else " asTop scen")+" as' storeAll'"+nl)
            else:
                off.write("let  runNPeriods_"+mi.name+"_"+phName+("" if not isDependent else " (asTop:state_top_all) ")+(" (scen:oneScen"+("Inner" if isDependent else "")+")" if hasESG else "")+" (n:i32) (as:state_"+mi.name+"_all):state_"+mi.name+"_all="+nl)
                off.write("\t(iterate n (runOnePeriod_"+mi.name+"_"+phName+(" scen)" if not isDependent else " asTop scen) ")+") as"+nl)

#functions to run N periods one policy, ONE scenario, get outputs.  Destined for use in inner stochastic runs.
if isDependent:
    for mi in modelInfos.values():
        for (phName,ph) in mi.phases.items():
            if mi.phaseDirections[phName]!="static":
                off.write(nl)
                if haveAll:
                    pass
                else:
                    off.write("let  runNPeriodsWithOutput_"+mi.name+"_"+phName+" (asTop:state_top_all)  (n:i32) (as:state_"+mi.name+"_all) (scen:oneScenInner):[]f32="+nl)
                    off.write("\tlet asNew=(iterate n (runOnePeriod_"+mi.name+"_"+phName+" asTop scen))  as in"+nl)
                    off.write("\t[")
                    comma=""
                    for ci in ph.values():
                        if ci.isOutput:
                            if not ci.isArrayed:
                                for fld in ci.fieldsCalcd:
                                    off.write(comma + "asNew.state__1." + fld)
                                    comma = ","
                            else:
                                for i in range(0, ci.dimSizes[0]):
                                    off.write(comma + "asNew.state__1." + ci.name + "[" + str(i) + "]")
                                    comma = ","
                    off.write("]"+nl)

#functions for inner stochastic run, one policy all scenarios. TODO we would like outputs to be defined by the list of "stochastic summary functions" in the main-model file, but it's too hard: means only FTB.
if isDependent:
    for mi in modelInfos.values():
        for (phName, ph) in mi.phases.items():
            if mi.phaseDirections[phName] != "static":
                off.write(nl)
                if haveAll:
                    pass
                else:
                    off.write("let runStochastic_"+mi.name+"_"+phName+ " (asTop:state_top_all) (scens:[]oneScenInner) (n:i32) (as:state_"+mi.name+"_all):[]f32="+nl)#returns mean value of output
                    off.write("let allSimsResults:[][]f32=map (runNPeriodsWithOutput_"+mi.name+"_"+phName+" asTop n as) scens"+nl)#scen x item
                    off.write("let sumSims = reduce (+.+) (zeros1 numOutputs_"+mi.name+") allSimsResults"+nl)
                    off.write("in map (/(real (length scens))) sumSims"+nl)

#functions to do NR runs: phase 1 runNPeriod.  The latter also stores the __NR1 calcs in the correct place in s/a (in the store function)
if haveNR:
    for mi in modelInfos.values():
        off.write(nl)
        off.write("let runNRBasis_"+mi.name+" (as:state_"+mi.name+"_all) (storeAll:*[][]f32) (bn:i32):*[][]f32="+nl)#discard the state, only interested in the store-all
        off.write("\tlet as2=as with basisNum=bn\n")
        if mi.dataFieldInfos[mi.termField].expression=="":
            off.write("\tlet (_,storeAll')= runNPeriods_"+mi.name+"_phase1 (as.d."+mi.termField+"-"+mi.phaseStart["phase1"]+") as2 storeAll"+nl)
        else:
            off.write("\tlet (_,storeAll')= runNPeriods_"+mi.name+"_phase1 (as.der."+mi.termField+"-"+mi.phaseStart["phase1"]+") as2 storeAll"+nl)
        off.write(" in storeAll'\n")

#function to do rebasing inner loop and w/a calcs
if haveR:
    for mi in modelInfos.values():
        off.write(nl)
        off.write("let calcRebasedResults_"+mi.name+" (as:state_"+mi.name+"_all,storeAll:*[][]f32) "+nl)#pass-through the state, only interested in the store-all.  NB: takes tuple as it receives results of runOnePeriod
        off.write(": (state_" + mi.name + "_all,*[][]f32)=" + nl)
        bn = 0#loop through rebased bases, if there are any
        off.write("let storeAll0=storeAll\n")
        if mi.dataFieldInfos[mi.termField].expression == "":
            tbit="d"
        else:
            tbit="der"
        bn=0
        bnr=0
        for b in bases.values():
            if b.isRebase:
                bnr+=1
                off.write("let as"+str(bnr)+"=as with basisNum="+str(bn)+nl)
                off.write("\tlet (_,storeAll"+str(bnr)+")= runNPeriods_"+mi.name+"_phase1 (as."+tbit+"."+mi.termField+"-as.t+1) as"+str(bnr)+" storeAll"+str(bnr-1)+nl)#call projection for rebased calcs
            bn += (len(b.subBases) if len(b.subBases)>0 else 1)
        if bnr>0:
            ph = mi.phases["phase1"]
            revd = []
            for ci in ph.values():
                if ci.isRebase and ci.isWholeArray:  # place functions - as with NR, assume that the functions can deal with multiple bases (all the rebased bases) at once
                    revd = [ci.name] + revd
                    convCode(mi, ci, CALCCODE)  # write calc's code, this case a storeAll->storeAll fn
            call = "storeAll"+str(bnr)
            for fn in revd:  # call of call of...
                call = fn + "(" + call + ")"
            off.write("let storeAllPostRebase = " + call + nl)
            off.write("in (as,storeAllPostRebase)\n")
        else:
            off.write("in (as,storeAll)\n")

#function to run experience basis (phase 1) (only applies if independent).  Look like runNPeriods but also calls calcRebased... if it's a rebase time
if not isDependent:
    if haveAll:
        off.write("\nlet runExperience_"+mi.name+" (as:state_"+mi.name+"_all) (storeAll:*[][]f32) (n:i32):(state_"+mi.name+"_all,*[][]f32)="+nl)
        off.write("\tloop (as':state_" + mi.name + "_all,storeAll':*[][]f32)=\n")
        off.write("\t(as,storeAll) for i<n do\n")
        if haveR:
            off.write("\tif !isRebaseTime[as.i_t+1] then"+nl)
        off.write("\trunOnePeriod_" + mi.name + "_phase1 as' storeAll'" + nl)
        if haveR:
            off.write("\telse\n")
            off.write("\tcalcRebasedResults_"+mi.name+"(runOnePeriod_" + mi.name + "_phase1 as' storeAll')" + nl)
    else:
        off.write("\nlet runExperience_"+mi.name+"=runNPeriods_"+mi.name+"_phase1"+nl)

# main function for running a single policy (independent case only)
if not isDependent:
    # signature
    for mi in modelInfos.values():#only 1 model
        break
    off.write(nl)
    off.write("\nlet runOnePol_" + mi.name)
    if hasESG and not isStochastic:
        off.write(" (scen:oneScen) ")
    if mi.hasData:
        off.write("(pol:data_" + mi.name + ") ")
    if mi.hasDerived:
        off.write("(der:derived_" + mi.name + ")")
    if isStochastic:#different position of scens to allow easy map thereover
        off.write(" (scen:oneScen) ")
    off.write(":"+("[]" if outputMode=="VECTOR" else "")+"[]f32 =" + nl)

    #Define the store-all array
    if haveAll:
        off.write("let storeAll:*[][]f32=copy (undef2 numSAs (numPeriods+1))\n")#one extra period for initialisation

    #initialise all-state for either phase0 (if it exists) or phase1.  Need to initialise both state and store-all
    hasPhase0 = mi.phases.keys().__contains__("phase0")
    if hasPhase0:
        initPhase="phase0"
    else:
        initPhase="phase1"

#create a zeroised state explicitly (this is so that all initialisation functions can have the same pattern of using "with").
for mi in modelInfosPlus.values():
    off.write("\nlet zero_state_"+mi.name+":state_"+mi.name+"={"+nl)
    comma=""
    for (phName, ph) in mi.phases.items():
        for ci in ph.values():
            if not ci.isCall:
                if ci.stores > 0 or (ci.isOutput and outputMode=="SCALAR") or ci.isConstant:
                    for fld in ci.fieldsCalcd:
                        if not ci.isArrayed:
                            off.write(comma+fld+"=0\n")
                        else:
                            off.write(comma+fld+"=zeros"+("i" if ci.type=="int" else "")+str(ci.numDims)+" "+"".join([str(i)+" " for i in ci.dimSizes])+nl)
                        comma = ","
            else:#a call, it's an array of something, it'll need to be initialised so make it a replication of the zeroised submodel state
                if ci.stores>0:
                    l = ci.code[0]#find submodel (bit of a hack (again!), we will analyse calls properly later in the top-modelcode generation)
                    if l.strip() == "":
                        l = ci.code[1]
                    (ls, _, _) = nwscap(l, "=,")
                    for i in range(0, len(ls)):
                        if ls[i].upper()=="MODEL":
                            subModel=ls[i+1]
                            break
                    if not l.__contains__("stochastic=true"):
                        off.write(comma+ci.name+"=zeros_as_"+subModel+nl)
                    else:
                        off.write(comma+ci.name+"=[]"+nl)
                    comma=","
    off.write("}\n")

    #create an all-state explicitly, this also involves explictly creating records for past values - for the dependent case this is a function
    off.write("\nlet zero_as_"+mi.name+(" (pol:data_"+mi.name+") " if isDependent and mi.hasData else "")+(" (der:derived_"+mi.name+") " if isDependent and mi.hasDerived else "")+":state_"+mi.name+"_all={\n")
    if mi.hasData:
        off.write("p = pol,"+nl)
    if mi.hasDerived:
        off.write("der = der,"+nl)
    off.write("state__1 = zero_state_"+mi.name+","+nl)
    for i in range(2, mi.maxStored + 1):#past values records
        off.write("state__" + str(i) + "={")
        comma=""
        for (phName, ph) in mi.phases.items():
            for ci in ph.values():
                if ci.stores >=i:
                    for fld in ci.fieldsCalcd:
                        if not ci.isArrayed:
                            off.write(comma+fld+"=0\n")
                        else:
                            off.write(comma+fld+"=zeros"+("i" if ci.type=="int" else "")+str(ci.numDims)+" "+"".join([str(i)+" " for i in ci.dimSizes])+nl)
                        comma = ","
        off.write("},\n")
    off.write("t = firstProjectionPeriod,"+nl)
    off.write("i_t = 0,"+nl)
    off.write("basisNum = 0,"+nl)
    off.write("forceTheIssue=0")
    if mi is topModel:
        off.write(",Call__=0,Call__t=0")
    off.write("}\n")
    off.write(nl)

    if isDependent and not mi is topModel:
        off.write("let zeros_as_"+mi.name+"=map"+("2 " if mi.hasDerived else " ")+"zero_as_"+mi.name+" fileData_"+mi.name+(" derived_"+mi.name if mi.hasDerived else "")+nl)#create array of zeroised states and all-states for sub-models

#all the special stuff for the independent case
if not isDependent:
    # initialise either for phase0 or 1
    if haveAll:
        off.write("let (init_as_pre_"+initPhase+",storeAll') = init_" + mi.name + "_"+initPhase+"_all zero_as_"+mi.name+(" scen " if hasESG else "")+" 0 storeAll \n")
        off.write("let storeAll_pre_"+initPhase+" = init_" + mi.name + "_"+initPhase+"_storeAll  0 zero_as_"+mi.name+ (" scen " if hasESG else "")+" storeAll' \n")
    else:
        off.write("let init_as_pre_"+initPhase+" = init_" + mi.name + "_"+initPhase+"_all zero_as_"+mi.name+(" scen " if hasESG else "")+" 0 \n")

    #run phase 0, should it exist,  TODO; term is fixed: it runs to firstprojectionperiod
    if hasPhase0:
        if haveAll:
            off.write("let (init_as_post_phase0,storeAll_post_phase0)=runNPeriods_"+mi.name+"_phase0 "+" (-firstprojectionperiod) "+" init_as_pre_phase0 storeAll_pre_phase0"+nl)
        else:
            off.write("let init_as_post_phase0=runNPeriods_"+mi.name+"_phase0 "+" (-firstprojectionperiod) "+" init_as_pre_phase0 "+nl)
        # initialise all-state (and store-all) for phase1 (if not already set up)
        if haveAll:
            off.write("let (init_as_pre_phase1,storeAll'') = init_" + mi.name + "_phase1_all init_as_post_phase0"+(" scen " if hasESG else "")+" 0 storeAll_post_phase0 \n")
            off.write("let storeAll_pre_phase1 = init_" + mi.name + "_phase1_storeAll  0 init_as_post_phase0 "+ (" scen " if hasESG else "")+" storeAll'' \n")
        else:
            off.write("let init_as_pre_phase1 = init_" + mi.name + "_phase1_all init_as_post_phase0"+(" scen " if hasESG else "")+" 0 \n")

    #run NR bases if they exist, bases only: "store" will replicate the calc results over subbases
    bn=1
    sa_c=0
    if haveAll:
        off.write("let storeAllNR0=storeAll_pre_phase1" + nl)
    for b in bases.values():
        if not b.isRebase and b.name!="Experience":
            off.write("let storeAllNR"+str(sa_c+1)+"=runNRBasis_"+mi.name+" init_as_pre_phase1 storeAllNR"+str(sa_c)+" "+str(bn)+nl)
            bn += (1 if b.subBases==[] else len(b.subBases))
            sa_c+=1
    if bn>1:
        off.write("let storeAll_postNR=storeAllNR"+str(sa_c)+nl)
    else:
        if haveAll:
            off.write("let storeAll_postNR=storeAll_pre_NR"+nl)

    #as in static-phases, generate functions from the __NR2 calcs and apply to the s/a
    #it is assumed that the calc formulae themselves have the ability to cope with bases/subbases
    if bn>1:
        revd = []
        ph = mi.phases["phase1"]
        for ci in ph.values():  # order is "just as it comes" (TODO make sure dict does not mess up the order)
            if ci.isNonRebase and ci.isWholeArray:
                revd = [ci.name] + revd
                off.write(nl)
                convCode(mi, ci, CALCCODE)  # write calc's code, this case a storeAll->storeAll fn
        call = "storeAll_postNR"
        for fn in revd:  # call of call of...
            call = fn + "(" + call + ")"
        off.write("\nlet storeAllPostNR2 = " + call + nl)
    else:
        if haveAll:
            off.write("\nlet storeAllPostNR2 = storeAllPostNR\n")

    #Run experience basis (phase1)- with rebasing
    if mi.dataFieldInfos[mi.termField].expression=="":
        termBit="(pol."+mi.termField+"-"+mi.phaseStart["phase1"]+"+1)"
    else:
        termBit="(der."+mi.termField+"-"+mi.phaseStart["phase1"]+"+1)"
    if haveAll:
        off.write("\nlet (as_post_phase1,storeAllPostphase1)=runExperience_"+mi.name+(" scen " if hasESG else "")+" init_as_pre_phase1 storeAllPostNR2 "+termBit+nl)
    else:
        off.write("\nlet as_post_phase1=runExperience_"+mi.name+" "+(" scen " if hasESG else "")+termBit+" init_as_pre_phase1 "+nl)

    #remaining phases
    phC=0
    phSkip=1+(1 if hasPhase0 else 0)#number of phases already carried out
    prevPhName="phase1"
    for (phName, ph) in mi.phases.items():
        phC+=1
        if phC>phSkip:
            off.write(nl)
            if mi.phaseDirections[phName]=="static":#run eiher N periods or static-phase
                off.write("let storeAllPost"+phName+"=runStaticPhase_"+mi.name+"_"+phName+" (storeAllPost"+prevPhName+")"+nl)
                off.write("let as_post_"+phName+"=as_post_"+prevPhName+nl)#keep all-state the same
            else:
                if mi.phaseStart[phName]!="previousTime":
                    strt=mi.phaseStart[phName]
                else:
                    strt="as_post_"+prevPhName+".t"
                dummyCi=calcInfoObject()
                dummyCi.name = ""
                dummyCi.lhs = "phTerm="
                dummyCi.initialisation = mi.phaseTerm[phName]
                dummyCi.myPhase=phName
                convCode(mi, dummyCi, DERIVED)
                if haveAll:
                    off.write("let (as_pre_"+phName+",storeAllPost"+prevPhName+"')=init_"+mi.name+"_"+phName+"_all as_post_"+prevPhName+(" scen " if hasESG else "")+" 0 storeAllPost"+prevPhName+nl)#initialisation from previous phase (all-state and store-all).
                    off.write("let storeAllPre"+phName+"=init_"+mi.name+"_"+phName+"_storeAll 0 as_post_"+prevPhName+(" scen " if hasESG else "")+" storeAllPost"+prevPhName+"'"+nl)#initialisation from previous phase (all-state and store-all).
                    off.write("let (as_post_"+phName+",storeAllPost"+phName+")=runNPeriods_" + mi.name +"_"+phName+" phTerm as_pre_"+phName+" storeAllPre"+phName + nl)#run phase
                else:
                    off.write("let as_pre_"+phName+"=init_"+mi.name+"_"+phName+"_all as_post_"+prevPhName+(" scen " if hasESG else "")+" 0 "+nl)#initialisation from previous phase (all-state and store-all).
                    off.write("let as_post_"+phName+"=runNPeriods_" + mi.name +"_"+phName+" phTerm as_pre_"+phName+nl)#run phase
            prevPhName=phName

    #output from run one pol
    off.write(nl)
    results="["
    for (phName, ph) in mi.phases.items():#get output calcs and assemble their 1-d (over time) arrays as a 2-d array
        comma=""
        for ci in ph.values():
            if ci.isOutput:
                if outputMode=="VECTOR":
                    if not ci.isArrayed:
                        results+=comma+"storeAllPost"+prevPhName+"[i_"+mi.name+"_"+ci.name+"]"
                        comma = ","
                    else:
                        for i in range(0,ci.dimSizes[0]):
                            results += comma + "storeAllPost" + prevPhName + "[i_" + mi.name + "_"+ci.name +"+"+ str(i)+"]"
                            comma = ","
                else:
                    if not ci.isArrayed:
                        for fld in ci.fieldsCalcd:
                            results+=comma+"as_post_"+prevPhName+".state__1."+fld
                            comma = ","
                    else:
                        for i in range(0,ci.dimSizes[0]):
                            results += comma + "as_post_" + prevPhName + ".state__1."+ci.name+"["+str(i)+"]"
                            comma = ","

    results+="]"
    off.write("in "+results+nl)

    #run one policy on all scenarios, for stochastic
    if isStochastic:
        off.write("\nlet runOnePolAllScens_"+mi.name+" (scens:[]oneScen) (pol:data_"+mName+")"+(" (der:derived_"+mName+")" if mi.hasDerived else "")+":[]f32 ="+nl)
        off.write("let allSimsResults:[][]f32=map (runOnePol_"+mi.name+" pol"+(" der" if mi.hasDerived else "")+") scens"+nl)
        off.write("let sumSims = reduce (+.+) (zeros1 numOutputs) allSimsResults"+nl)
        off.write("in map (/numScens) sumSims\n")

    #batches of policies, if required
    if mi.batchSizeInternal>0:
        off.write("\nlet batchSize:i32="+str(mi.batchSizeInternal)+nl)
        off.write("let numBatches=if numPols_"+mi.name+"%%batchSize==0 then (numPols_"+mi.name+"//batchSize) else (numPols_"+mi.name+"//batchSize+1)\n")
        off.write("let "+("sum" if not individualOutput else "concat")+"OfBatches=\n")
        if not individualOutput:
            off.write("\tloop sumOfBatches':"+("[]" if outputMode=="VECTOR" else "")+"[][]f32=(zeros"+("3" if outputMode=="VECTOR" else "2")+" batchSize "+str(numOutputs)+(" numPeriods)" if outputMode=="VECTOR" else ")")+" for i<numBatches do\n")
        else:
            off.write("\tloop concatOfBatches':"+("[]" if outputMode=="VECTOR" else "")+"[][]f32=[] for i<numBatches do\n")
        off.write("\tlet lo=i*batchSize\n")
        off.write("\tlet hi=mini ((i+1i32)*batchSize) numPols_"+mi.name+nl)
        off.write("\tlet batchRes = map"+("2" if mi.hasDerived else "")+" (runOnePol"+("AllScens" if isStochastic else "")+"_"+mName+(" scens"+("[0]"if not isStochastic else "")+")" if hasESG else ")")+" fileData_"+mName+"[lo:hi]"+( "derived_"+mName+"[lo:hi] " if mi.hasDerived else "")+nl)
        if not individualOutput:
            off.write("\tin sumOfBatches' +." + ("." if outputMode == "VECTOR" else "") + ".+ batchRes\n")
            off.write("in reduce (+."+("." if outputMode=="VECTOR" else "")+"+) (zeros"+("2" if outputMode=="VECTOR" else "1")+" "+str(numOutputs)+(" numPeriods)" if outputMode=="VECTOR" else ")")+" sumOfBatches\n")
        else:
            off.write("\tin concatOfBatches'++batchRes"+nl)
            off.write("in concatOfBatches"+nl)
    else:
        off.write(nl)
        off.write("let res = map2 (runOnePol"+("AllScens" if isStochastic else "")+"_"+mName+(" scens"+("[0]"if not isStochastic else "")+")" if hasESG else ")")+" fileData_"+mName+" derived_"+mName+nl)
        if not individualOutput:
            off.write("in reduce (+."+("." if outputMode=="VECTOR" else "")+"+) (zeros"+("2" if outputMode=="VECTOR" else "1")+" "+str(numOutputs)+(" numPeriods)" if outputMode=="VECTOR" else ")")+" res\n")
        else:
            off.write("in res"+nl)

#Dependent case - all the top model code - directly within main
if isDependent:
    topPhaseName=list(topModel.phases.keys())[0]
    topPhase=topModel.phases[topPhaseName]#only 1 phase
    del topModel.phases[topPhaseName]#remove the actual single phase as it'll be replaced with pseudo-phases (between calls) so as to do the ordering

    currPhase={}
    pc=1
    topModel.phaseDirections={}
    topModel.phaseDirections[topPhaseName]="forwards"
    dummyCi=calcInfoObject()
    dummyCi.isCall=True
    topPhase["ZZZZZ"]=dummyCi#dummy at end to ensure any calls at tne end are picked up
    currPhaseName="phase1"
    maxNumInnerScenarios=0
    for (cin,ci) in topPhase.items():#get call info, inner-model call info  and create pseudo-phases
        if not ci.isCall:#add calc to pseudo-phase
            ci.myPhase=currPhaseName
            currPhase[ci.name]=ci
        if ci.isCall:
            topModel.phases[currPhaseName]=currPhase#got some calcs between calls, make a phase out of them.  Keep empty phases so we can simply loop: phase, call, phase...
            topModel.phaseDirections[currPhaseName]="forwards"
            topModel.phaseStart[currPhaseName]=""
            topModel.phaseTerm[currPhaseName]=""
            pc+=1
            currPhase={}
            currPhaseName="phase"+str(pc)
            if cin=="ZZZZZ":
                continue
            call=callInfoObject()
            call.name=ci.name
            call.stores=(ci.stores==1)
            #a bit silly, but need to avoid = in conditional expression being used as a delimiter
            l=ci.code[0]
            if l.strip()=="":
                l=ci.code[1]
            l=l.replace("==","@@")
            l=l.replace("<=","<@")
            l=l.replace(">=",">@")
            l=l.replace("!=","!@")
            (ls, _, _) = nwscap(l, "=,")
            skipItem=False
            for i in range(0,len(ls)):
                l=ls[i]
                lu=l.upper()
                if not skipItem:
                    if not allowableCallSettings.__contains__(lu):
                        doErr("Unknown store setting for call: ", l)
                    if lu=="STATEINPUT":
                        call.stateInput =  ls[i+1]
                    if lu=="MODEL":
                        call.model =  ls[i+1]
                    if lu=="PHASE":
                        call.phase =  ls[i+1]
                    if lu=="TERM":
                        call.term = ls[i+1]
                    if lu=="STOCHASTIC":
                        call.isStochastic = (False if ls[i+1].upper()=="FALSE" else True)
                    if lu=="SCENARIOS":
                        call.innerScenarios =  ls[i+1]
                    if lu=="BASIS":
                        call.basis =  ls[i+1]
                    if lu=="WHEN":
                        ll=ls[i+1]#reverse the silly hack from above
                        ll = ll.replace("@", "=")
                        call.when =  (ll if ll!="all" else "true")
                    if lu=="RETURNS":
                        call.returns =  ls[i+1]
                skipItem=not skipItem
            callInfos[ci.name]=call
        if ci.isInnerScenarios:
            imco=innerModelCallObject()
            imco.name=ci.name
            l=ci.code[0]
            if l.strip()=="":
                l=ci.code[1]
            l=l.replace("==","@@")
            l=l.replace("<=","<@")
            l=l.replace(">=",">@")
            l=l.replace("!=","!@")
            (ls, _, _) = nwscap(l, "=,")
            skipItem=False
            inParams=False
            for i in range(0,len(ls)):
                l=ls[i]
                lu=l.upper()
                if not skipItem:
                    if inParams:
                        ll=ls[i]
                        ll=ll.replace("(","")
                        ll=ll.replace(")","")
                        imco.theParams=imco.theParams.__add__([ll])
                        continue
                    if not allowableInnerModelCallSettings.__contains__(lu):
                        doErr("Unknown setting for inner model call: ", l)
                    if lu=="MODEL":
                        imco.model=ls[i+1]
                    if lu=="NUMSCENS":
                        imco.numScens=int(ls[i+1])
                        if imco.numScens>maxNumInnerScenarios:
                            maxNumInnerScenarios=imco.numScens
                    if lu == "TERM":
                        imco.term = ls[i + 1]
                    if lu=="BASIS":
                        imco.basis=ls[i+1]
                    if lu == "WHEN":
                        ll = ls[i + 1]  # reverse the silly hack from above
                        ll = ll.replace("@", "=")
                        imco.when = (ll if ll!="all" else "true")
                    if lu=="THEPARAMS":
                        inParams=True
                        continue
                if not inParams:
                    skipItem = not skipItem
            innerModelCalls[ci.name]=imco

    #generate a single (large) set of Normals for use in inner runs
    off.write("\nlet maxNumRNs:i32="+topModel.phaseTerm[topPhaseName]+"*"+str(maxRNsPerPeriod)+"*"+str(maxNumInnerScenarios)+"//2"+nl)#numberof RNs to pre-generate, only half as we'll negate so as to generate anithetes as we run (extra calcs, less memory)
    off.write("let numBlocksOf624:i32=1+maxNumRNs//(624*numMTItersPerBatchOfRNs)"+nl)
    off.write("let RNsPerIteration:i32=numBlocksOf624*624"+nl)
    off.write("let seeds:[]u32=5984...(5984+(u32.i32 numBlocksOf624-1))"+nl)
    off.write("let initStatesOf624:[][]u32=map initMT seeds"+nl)
    off.write("let U_inner':*[][]f32=replicate numMTItersPerBatchOfRNs (replicate RNsPerIteration 0f32)"+nl)#zeroise in-place array to fill with all the RNs
    off.write("let (U_inner'':*[][]f32,_)=loop (u':*[][]f32,st':[][]u32)=(U_inner',initStatesOf624) for i<numMTItersPerBatchOfRNs do" + nl)
    off.write("\tlet (st'',u'')=unzip (map nextBlockOf624 st')"+nl)
    off.write("\tlet u'''=map f32.f64 (map BSMNormInv (flatten u''))"+nl)
    off.write("\t in (u' with [i]=u''',st'')"+nl)
    off.write("let innerRNs:[]f32=flatten U_inner''"+nl)

    #function to run 1 period of the top model.  NB "scenInner" is actually the inner form of the outer scen.  It is used to evolve the submodels in the outer scenario.
    off.write("\nlet  runOnePeriod_top (scen:oneScen) (scenInner:oneScenInner) (as:state_top_all)"+(" (storeAll:*[][]f32):" if haveAll else ":"))
    if haveAll:
        off.write(" (state_top_all,*[][]f32)="+nl)
    else:
        off.write(" state_top_all="+nl)
    off.write("let t=as.t\n")
    doACall=False#call or phase?
    theCalls=list(callInfos.values())
    thePhases=list(topModel.phases.values())
    i_call=0#positons in calls/phases
    i_phase=0
    doneSomething=True
    tempASCount=0#incremented to produce unique names for anything really
    anyCount=0
    while doneSomething:#loop through pseudo-phases and calls, alternately (a phase might be empty if there are two adjacent calls)
        doneSomething=False
        if not doACall:
            whoCallsWhom = {}
            if i_phase>=len(thePhases):
                continue
            doneSomething=True
            ph=thePhases[i_phase]
            for ci in ph.values():
                if ci.isConstant:
                    continue
                iCall = []
                for ci2 in ph.values():
                    if ci2.isConstant:
                        continue
                    found = False
                    for fld in ci2.fieldsCalcd:
                        for l in ci.code:
                            for mtch in re.finditer("[\W]" + fld + "[\W]", " " + l + " "):
                                found = True
                    if found:
                        iCall.append(ci2.name)
                whoCallsWhom[ci.name] = iCall
            while whoCallsWhom != {}:
                for (caller, callees) in whoCallsWhom.items():
                    if callees == []:
                        if not ph[caller].isInnerScenarios:
                            convCode(topModel,ph[caller],CALCCODE,theCalls)#calc, NB: pass in details of calls so references to submodels can be converted
                        else:#inner model call
                            #get uniforms
                            imco=innerModelCalls[caller]#call to inner model to generate inner scenarios
                            anyCount += 1
                            off.write("let whenExpr"+str(anyCount)+":bool=" + imco.when + nl)
                            dummyCi=calcInfoObject()
                            dummyCi.myPhase=topPhaseName
                            ii=-1
                            for parm in imco.theParams:#convert parameter expressions
                                ii+=1
                                dummyCi.code = [parm]
                                dummyCi.lhs = imco.name+"_"+str(ii)+"="
                                convCode(topModel, dummyCi, CALCCODE)
                            imcoParams=" ("+",".join([imco.name+"_"+str(ii) for ii in range(0,len(imco.theParams))])+") "#tuple of params
                            off.write("let "+imco.name+"_RNsPerPeriod=if whenExpr"+str(anyCount)+" then "+imco.model+"_RNsPerPeriod "+str(imco.numScens)+" "+imco.term+imcoParams+" [] else 0"+nl)#get number of RNs per period
                            off.write("let RNs_"+imco.name+"=innerRNs[0:"+str(imco.numScens)+"*"+imco.term+"*"+imco.name+"_RNsPerPeriod"+"//2]"+nl)#the inner model will do the antithetical stuff
                            off.write("let "+imco.name+"=scensInnerFromArrays (if whenExpr"+str(anyCount)+" then "+imco.model+" "+str(imco.numScens)+" "+imco.term+imcoParams+" RNs_"+imco.name+" else ([]))")#call inner model
                        off.write(nl)
                        for l in whoCallsWhom.values():
                            if l.__contains__(caller):
                                l.remove(caller)
                        del whoCallsWhom[caller]
                        break
            doACall = True
            i_phase+=1
        else:# a call
            if i_call>=len(theCalls):#finished all calls
                continue
            doneSomething=True
            tempASCount+=1
            off.write("let as"+str(tempASCount)+"=as")#temporary state incorporating top model calcs so far, to pass into call
            if tempASCount>1:
                off.write(str(tempASCount-1))
            call=theCalls[i_call]
            if i_phase>=1:#in case call right at start
                for ci in thePhases[i_phase-1].values():#incorporate the changes in the last pseudo-phase
                    if ci.stores>0:
                        for fld in ci.fieldsCalcd:
                            off.write(" with state__1."+fld+"="+fld)
            off.write(" with Call__=Call__"+call.name+" with Call__t=t+1")
            off.write(nl)
            anyCount+=1
            off.write("let whenExpr"+str(anyCount)+":bool="+call.when+nl)
            stateInput=call.stateInput
            if stateInput[-3:]=="__1":
                stateInput="as.state__1."+stateInput[:-3]
            else:
                stateInput=stateInput+"_state"
            off.write("let termExpr"+str(anyCount)+"=if whenExpr"+str(anyCount)+" then (map (.state__1."+call.term+") "+stateInput+") else ([])"+nl)#lambda to calculate term from a calc in the state
            if not call.isStochastic:
                off.write("let "+call.name+"_state=if whenExpr"+str(anyCount)+" then ")
                off.write("(map2 (runNPeriods_"+call.model+"_"+call.phase+" (as"+str(tempASCount)+" with basisNum="+call.basis+") scenInner) termExpr"+str(anyCount)+" "+stateInput+") else"+(" as.state__1."+call.name if call.stores else "([])")+nl)
            else:
                off.write("let "+call.name+"_output=if whenExpr"+str(anyCount)+" then ")
                off.write("(map2 (runStochastic_"+call.model+"_"+call.phase+" (as"+str(tempASCount)+" with basisNum="+call.basis+") "+call.innerScenarios+") "+" termExpr"+str(anyCount)+" "+stateInput+") else"+(" state__1."+call.name if (call.stores and not call.isStochastic) else "([])")+nl)
                if call.stores:
                    tempASCount+=1
                    off.write("let as"+str(tempASCount)+"=as")
                    if tempASCount>1:
                        off.write(str(tempASCount-1))
                    off.write(" with state__1."+call.name+"="+call.name+"_output"+nl)
            doACall=False
            i_call+=1
    #storage function TODO: store-all
    off.write("let store (as:state_top_all) "+("(storeAll:*[][]f32):" if haveAll else ":"))
    if haveAll:
        off.write(" (state_top_all,*[][]f32)=" + nl)
    else:
        off.write(" state_top_all=" + nl)
    for i in range(topModel.maxStored ,0,-1):#stored states
        off.write("let state__"+str(i)+"=as.state__"+str(i))
        for ci in topPhase.values():
            if ci.stores >= i or (i==1 and ci.isOutput and outputMode=="SCALAR"):
                for fld in ci.fieldsCalcd:
                    if not ci.isCall or not callInfos[ci.name].isStochastic:
                        off.write(" with "+fld+"="+("as.state__"+str(i-1)+"." if i>1 else "")+fld+("_state" if ci.isCall else ""))
        off.write(nl)
    off.write("let asNew=as "+nl)#new all-state
    for i in range(1, topModel.maxStored + 1):
        off.write(" with state__"+str(i)+"=state__"+str(i))
    off.write(" with t=as.t+1")
    off.write(" with i_t=as.i_t+1"+nl)
    off.write("in asNew" + nl)
    off.write("in store as \n")  # return from runOnePeriod

    #function to initialise top (and submodels)
    off.write(nl)
    off.write("let init_top (s:state_top) (scen:oneScen):state_top="+nl)
    comma=""
    inited=set()
    for (cin,ci) in topPhase.items():
        if cin=="ZZZZZ":
            continue
        if not ci.isCall:#not call, ordinary initialisation code
            if ci.stores > 0 and ci.initialisation != "":
                convCode(topModel, ci, INITIALISATION)
                for fld in ci.fieldsCalcd:  # record which calcs were initialised (used with "with" in state creation)
                    inited.add(fld)
            if ci.isConstant:
                convCode(mi, ci, CALCCODE)
                for fld in ci.fieldsCalcd:
                    inited.add(fld)
        else:#call, call the appropriate submodel phase initialisation
            call=callInfos[ci.name]
            if call.stores and not call.isStochastic:
                off.write("let "+call.name+"=map ((\\a b c->init_"+call.model+"_"+call.phase+"_all c a b) scen 0) s."+call.name+nl)
                inited.add(call.name)
    if len(inited) != 0:#withs...
        off.write("\nin s ")
        for ci in inited:
            off.write(" with " + ci + "=" + ci)
        off.write(nl)
    else:#no initialisation
        off.write(" s " + nl)

    #function to run N periods of the top model and get output (initialise state and all-state for top model first)
    off.write(nl)
    off.write("let runNPeriodsWithOutput_top (n:i32) (scen:oneScen) (scenInner:oneScenInner) :[]f32="+nl)
    off.write("\tlet init_as=zero_as_top with state__1=init_top zero_as_top.state__1 scen"+nl)#initialise top model state (both for calcs and for sub-models that are stored)
    off.write("\tlet asNew=iterate n (runOnePeriod_top scen scenInner) init_as in"+nl)
    off.write("[")
    comma=""
    for ci in topPhase.values():
        if ci.isOutput:
            if not ci.isArrayed:
                for fld in ci.fieldsCalcd:
                    off.write(comma + "asNew.state__1." + fld)
                    comma = ","
            else:
                for i in range(0, ci.dimSizes[0]):
                    off.write(comma + "asNew.state__1." + ci.name + "[" + str(i) + "]")
                    comma = ","
    off.write("]" + nl)

    #results from main (dependent)
    off.write(nl)
    off.write("let allSimsResults:[][]f32=map2 (runNPeriodsWithOutput_top "+topModel.phaseTerm[topPhaseName]+") scens scensAsInner"+nl)
    if averageOverScenarios:
        off.write("let sumSims = reduce (+.+) (zeros1 numOutputs) allSimsResults"+nl)
        off.write("in map (/(length scens)) sumSims"+nl)
    else:
        off.write("in allSimsResults"+nl)
off.close()

#call Futhark .c file
ofc=open(exeSubDir+"/"+"call_futhark.c",'w')

#includes: standard
ofc.write("#include <stdio.h>"+nl)
ofc.write("#include <stdlib.h>"+nl)
ofc.write("#include <stdbool.h>"+nl)
ofc.write("#include <string.h>"+nl)
ofc.write("#include <time.h>"+nl)

#includes: futhark and reading routines
ofc.write("#include \"futhark.h\""+nl)
ofc.write("#include \"reading.h\""+nl)

#main and command line arguments
ofc.write("\nint main(int argc, char *argv[])"+nl)
ofc.write("{"+nl)

#get context and config
ofc.write(nl)
ofc.write("struct futhark_context_config * cfg = futhark_context_config_new();"+nl);
ofc.write("struct futhark_context * ctx = futhark_context_new(cfg);"+nl)

#declare c table arrays
ofc.write("\nfloat ")
comma=""
for mi in modelInfosPlus.values():
    for (k,t) in mi.tableInfos.items():
        ofc.write(comma+"*table_"+k+"_"+mi.name)
        comma=","
ofc.write(";"+nl)

#declare c data arrays (int)
ofc.write("\nint ")
comma=""
for mi in modelInfos.values():
    if mi.hasData:
        ofc.write(comma+"*fileDataInt_"+mi.name)
        comma=","
ofc.write(";"+nl)
ofc.write("\nfloat ")
#now float
comma = ""
for mi in modelInfos.values():
    if mi.hasData:
        ofc.write(comma + "*fileDataReal_" + mi.name)
        comma = ","
ofc.write(";" + nl)

#declare c ESG arrays
if hasESG:
    ofc.write("float *scens;"+nl)
    ofc.write("int numScenPeriods;"+nl)#do not know this in advance

#read scenarios
if hasESG:
    ofc.write("int err;\n")
    schLineLength=0
    for fldSize in mi.esg.values():#get scenario line length
        fldLength=1
        for fs in fldSize:
            fldLength*=fs
        schLineLength+=fldLength
    ofc.write("err=readESG(\""+scensSubDir+"/"+scensFile+"\",\"\","+str(numScens)+","+str(schLineLength)+",&numScenPeriods,&scens);\n")

def printTableBlocks(t,level,stringSoFar):#recursively build up string an then print e.g. male+sch1; will only do blocks i.e. all except last 2 dims
    if level==len(t.dims)-2 or t.dims[level]=="int" or t.dims[level]=="int0":
        if stringSoFar!="":
            ofc.write(",\""+stringSoFar+"+\"")
    else:
        e=enums[t.dims[level].replace("(","").replace(")","").strip()]
        for k in e.keys():
            printTableBlocks(t,level+1,stringSoFar+"+"+k)

#read tables and get size information, this amalgamates all bases into one big table
basisToNum={"SINGLE":1,"PREFIX":2,"SUFFIX":3,"SUBDIR":4}
ofc.write("const char *basisNames["+str(len(bases))+"]={")
comma=""
for basis in bases:
    ofc.write(comma+"\""+basis+"\"")
    comma=","
ofc.write("};\n")
for mi in modelInfosPlus.values():
    for (k,t) in mi.tableInfos.items():
        comma=""
        ofc.write("int lb_"+k+"_"+mi.name+"[2];"+nl)#declare c arrays to hold table lower bounds
        ofc.write("int dimSizes_"+k+"_"+mi.name+"["+str(len(t.dims))+"]={")
        for e in t.dims:
            if e[0]=="(":
                e=e[1:]
            if e[-1]==")":
                e=e[:-1]
            if e=="int" or e=="int0":
                ofc.write(comma+"-1")
            else:
                ofc.write(comma+str(enums[e].__len__()))
            comma=","
        ofc.write("};\n")
        ofc.write("const char *blockOrder_"+k+"_"+mi.name+"[]={\"\"")#arrays of strings labelling in blocks in the order given by the enums - will be used by c++ to read blocks in the correct order
        printTableBlocks(t,0,"")
        ofc.write("};\n")
        ofc.write("err=readTable(\""+tablesSubDir+"/"+k+"\",\"\","+str(len(t.dims))+",dimSizes_"+k+"_"+mi.name+","+str(numBases)+",basisNames,"+str(basisToNum[t.basis])+","+"&table_"+k+"_"+mi.name+",lb_"+k+"_"+mi.name+",blockOrder_"+k+"_"+mi.name+");"+nl)

#create futhark table arrays
tables=[]
for mi in modelInfosPlus.values():
    for (k,t) in mi.tableInfos.items():
        ofc.write("struct futhark_f32_"+str((1 if t.basis!="SINGLE" else 0)+len(t.dims))+"d *fut_"+"table_"+k+"_"+mi.name+"=futhark_new_f32_"+str((1 if t.basis!="SINGLE" else 0)+len(t.dims))+"d(ctx,"+"table_"+k+"_"+mi.name+(","+str(numBases)if t.basis!="SINGLE" else "")+",")
        tables=tables.__add__(["fut_"+"table_"+k+"_"+mi.name])
        comma=""
        dimCount=0
        for e in t.dims:
            if e[0]=="(":
                e=e[1:]
            if e[-1]==")":
                e=e[:-1]
            if e == "int" or e=="int0":
                ofc.write(comma + "dimSizes_"+k+"_"+mi.name+"["+str(dimCount)+"]")
            else:
                ofc.write(comma + str(enums[e].__len__()))
            comma = ","
            dimCount+=1
        ofc.write(");\n")
        ofc.write("struct futhark_i32_1d *fut_"+"lb_"+k+"_"+mi.name+"=futhark_new_i32_1d(ctx,"+"lb_"+k+"_"+mi.name+",2);"+nl)

# enum info for data read
ofc.write("const char **enumInfo[" + str(enums.__len__()) + "];" + nl)
enumCount = 2
enumNum = {}
for (enumName, enum) in enums.items():
    enumNum[enumName] = enumCount
    ofc.write("const char *enumVals" + str(enumCount) + "[]={")
    comma = ""
    for (k, v) in enum.items():
        ofc.write(comma + "\"" + k + "\"")
        comma = ","
    ofc.write(",\"endMarker\"};" + nl)
    ofc.write("enumInfo[" + str(enumCount-2) + "]=enumVals" + str(enumCount) + ";" + nl)
    enumCount += 1

#read data and create futhark data arrays
ofc.write("int numPols;\n")
dataFiles=[]
for mi in modelInfos.values():
    if mi.hasData:
        numDF=0
        numDFInt=0
        numDFReal=0
        for df in mi.dataFieldInfos.values():
            if df.expression=="":
                numDF+=1
                if df.type != "real":
                    numDFInt+=max(df.arraySize,1)
                else:
                    numDFReal+=max(df.arraySize,1)
        ofc.write("int intOrReal_"+mi.name+"["+str(numDF)+"]={")
        comma=""
        for df in mi.dataFieldInfos.values():
            if df.expression=="":
                if df.type=="real":
                    ofc.write(comma+"1")
                elif df.type=="int":
                    ofc.write(comma+"0")
                else:
                    ofc.write(comma+str(enumNum[df.type]))
                comma=","
        ofc.write("};\n")
        ofc.write("int arraySize_"+mi.name+"["+str(numDF)+"]={")
        comma=""
        for df in mi.dataFieldInfos.values():
            if df.expression=="":
                ofc.write(comma+("1" if df.arraySize==0 else str(df.arraySize)))
                comma=","
        ofc.write("};\n")
        ofc.write("err=readData(\""+dataSubDir+"/data_"+mi.name+"\",\"\","+str(numDF)+",intOrReal_"+mi.name+",enumInfo,"+str(enums.__len__())+",arraySize_"+mi.name+",&numPols,&fileDataReal_"+mi.name+",&fileDataInt_"+mi.name+");\n")
        dataFiles=dataFiles.__add__(["fileDataInt_"+mi.name])
        dataFiles=dataFiles.__add__(["fileDataReal_"+mi.name])
        ofc.write("struct futhark_i32_2d *fut_fileDataInt_"+mi.name+"=futhark_new_i32_2d(ctx,fileDataInt_"+mi.name+",numPols,"+str(numDFInt)+");"+nl)
        ofc.write("struct futhark_f32_2d *fut_fileDataReal_" + mi.name + "=futhark_new_f32_2d(ctx,fileDataReal_" + mi.name + ",numPols," + str(numDFReal) + ");" + nl)

#declare futhark ESG arrays
if hasESG:
    ofc.write("struct futhark_f32_3d *fut_scens=futhark_new_f32_3d(ctx,scens,"+str(numScens)+",numScenPeriods,"+str(schLineLength)+");" + nl)

#create the futhark results arrays
if not isDependent:
    numOutputs = 0
    for mi in modelInfos.values():
        numPeriods=mi.lastProjectionPeriod-mi.firstProjectionPeriod+1
        for ph in mi.phases.values():
            for ci in ph.values():
                if ci.isOutput:
                    numOutputs+=(1 if ci.dimSizes==[] else ci.dimSizes[0])
if not isDependent:
    ofc.write("struct futhark_f32_"+("2" if outputMode=="VECTOR" else "1")+"d *fut_Res;\n")
    ofc.write("float *res=(float*) malloc("+str(numOutputs)+("*"+str(numPeriods)if outputMode=="VECTOR" else "")+"*sizeof(float));\n")
else:
    ofc.write("struct futhark_f32_"+("2" if not averageOverScenarios else "1")+"d *fut_Res;\n")
    ofc.write("float *res=(float*) malloc("+str(numOutputs)+("*"+str(numScens)if not averageOverScenarios else "")+"*sizeof(float));\n")

#call futhark (incl.timing)
ofc.write("struct timespec startTime,endTime;\n")
ofc.write("clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&startTime);\n")

ofc.write("int futErr=futhark_entry_main(ctx,&fut_Res,"+(" fut_scens " if hasESG else "")+",")
for dfl in dataFiles:
    ofc.write("fut_"+dfl+",")
comma=""
for mi in modelInfosPlus.values():
    for (kt,t) in mi.tableInfos.items():
        ofc.write(comma+"fut_table_"+kt+"_"+mi.name)
        comma=","
        if t.dim1HasLB or  t.dim2HasLB:
            ofc.write(comma+"fut_lb_"+kt+"_"+mi.name)
ofc.write(");\n")

ofc.write("clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&endTime);\n")
ofc.write("double diffTime=(endTime.tv_sec-startTime.tv_sec)+(endTime.tv_nsec-startTime.tv_nsec)/1e9;\n")

#get results from futhark
if not isDependent:
    ofc.write("futhark_values_f32_"+("2" if outputMode=="VECTOR" else "1")+"d(ctx,fut_Res,res);\n")
else:
    ofc.write("futhark_values_f32_"+("2" if not averageOverScenarios else "1")+"d(ctx,fut_Res,res);\n")

#free c table arrays
for tbl in tables:
    ofc.write("freeReals ("+tbl[4:]+");"+nl)

#free futhark table arrays
for mi in modelInfosPlus.values():
    for (k,t) in mi.tableInfos.items():
        ofc.write("futhark_free_f32_"+str((1 if t.basis!="SINGLE" else 0)+len(t.dims))+"d(ctx,fut_table_"+k+"_"+mi.name+");\n")

#free c data arrays
dc=0
for df in dataFiles:
    if dc==0:
        ofc.write("freeInts("+df+");"+nl)
    else:
        ofc.write("freeReals(" + df + ");" + nl)
    dc=1-dc

#free futhark data arrays
intIsh=0
for df in dataFiles:
    if intIsh==0:
        ofc.write("futhark_free_i32_2d(ctx,fut_"+df+ ");\n")
    else:
        ofc.write("futhark_free_f32_2d(ctx,fut_"+df+ ");\n")
    intIsh=1-intIsh;

#free c ESG arrays
if hasESG:
    ofc.write("freeReals(scens);\n")

#free futhark ESG arrays
if hasESG:
    ofc.write("futhark_free_f32_3d(ctx,fut_scens);"+nl)

#free context
ofc.write("futhark_context_free(ctx);\n")
ofc.write("futhark_context_config_free(cfg);\n")

#output results to file
ofc.write("FILE *fp;\n")
ofc.write("fp=fopen(\""+outputSubDir+"/futhark.out\",\"w\");"+nl)
fmtstr="%s         "*len(outputNames)
ofc.write("fprint(fp,\""+("Policy" if not isDependent and individualOutput else "")+("Scenario" if isDependent and not averageOverScenarios else "")+fmtstr+"\","+",".join(outputNames)+");"+nl)
fmtstr=("%d         " if isDependent and not averageOverScenarios or not isDependent and individualOutput else "")+"%f         "*len(outputNames)
if isDependent:
    if averageOverScenarios:
        ofc.write("fprint(fp,\""+fmtstr+"\"")
        for i in range(0,numOutputs):
            ofc.write(","+"res["+str(i)+"]")
        ofc.write(");"+nl)
    else:#individual (outer) scenarios
        ofc.write("for (int scen=0;scen<"+str(numScens)+";++scen){"+nl)
        ofc.write("\tint ind=scen*"+str(numOutputs)+";"+nl)
        ofc.write("\tfprint(fp,\""+fmtstr+"\"")
        ofc.write(",scen")
        for i in range(0,numOutputs):
            ofc.write(","+"res[ind+"+str(i)+"]")
        ofc.write(");"+nl)
        ofc.write("}\n")
else:#independent
    if individualOutput:#policy loop
        ofc.write("for (int pol=0;pol<numPols;++pol){"+nl)
        ofc.write("\tint ind=pol*" + str(numOutputs) + ";" + nl)
    if outputMode=="Vector":
        pass
    else:#scalar output (no time)
        ofc.write("\tfprint(fp,\""+fmtstr+"\"")
        ofc.write(",pol")
        for i in range(0,numOutputs):
            ofc.write(","+"res["+("ind+" if individualOutput else "")+str(i)+"]")
        ofc.write(");"+nl)
        ofc.write("}\n")

ofc.write("fclose(fp);"+nl)

ofc.write("\nreturn 0;\n")
ofc.write("}"+nl)
ofc.close()

#Compile Futhark to Futhark library
if compileFuthark:
    os.environ["PATH"]+=os.pathsep+futharkPath#goodness only knows why I need to do this...
    cp=subprocess.run(["futhark "+targetLanguage+" --library futhark.fut"],cwd=exeSubDir,shell=True,stderr=subprocess.PIPE,universal_newlines=True)#individual arguments do not seem to work...
    if cp.stderr.__contains__("Error"):
        itern=re.finditer(":[0-9]+:",cp.stderr)
        for mtch in itern:
            errLine = int(mtch.group()[1:-1])
            print("Error in line " +str(errLine)+" of generated code.")
            ift = open(exeSubDir + "/" + "futhark.fut", 'r')#find the offending line
            for i in range(0,errLine):
                l=ift.readline()
            ift.close()
            if l in errorInfos:
                ei=errorInfos[l]
                if not ei.ci is None:
                    print("This corresponds to "+ei.ci.description+" line "+str(ei.ln)+" of calc.")
                else:
                    print("Sorry. No further Inepta information is available.")
            else:
                print("Sorry. No further Inepta information is available.")
    else:
        print("Bloody hell, it compiled!")

#Compile latter to C
if compileC:
    subprocess.run(["gcc futhark.c -o libfuthark.so -fPIC -shared"],cwd=exeSubDir,shell=True)#individual arguments do not seem to work...

#Compile and link call_futhark, reading libraries, Futhark library => final "exe"
#TODO needs paths and libraries to opencl etc. - see "commands" file
if compileExe:
    pass
