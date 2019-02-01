import os
import sys
import re

#constants
nl="\n"
userDefinedFns={"real","exp","sqrt","log","sum","prod","zeros1","zeros2","zeros3","backDisc"}
multiBracket={}#lots of []
br="[]"
multiBracket[0]=""
for i in range(1,100):
    multiBracket[i]=br
    br+="[]"

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
bases={}#name->rebased
rebaseTimes=[]

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
        self.dataFieldInfos={}
        self.phases={}#indexed by name, returns dict of calcInfoObjects
        self.phaseDirections={"phase0":"backwards","phase1":"forwards"}
        self.tableInfos={}
        self.hasData=False
        self.hasDerived=False
        self.esg={}#only top model should have one of these
        self.forceThese=[]
        self.maxStored=0#excluding alls
        self.haveAll=False
        self.have0=False
        self.firstProjectionPeriod=1
        self.lastProjectionPeriod=600
        self.commonCode=[]

class dataFieldInfo(object):#covers derived fields as well
    def __init__(self):
        self.name = ""
        self.type=""
        self.arraySize=0
        self.expression=""#raw expression for derived

class calcInfoObject:
    def __init__(self):
        self.name = ""#is concatenation of the fields returned whn returning a tuple
        self.fieldsCalcd=[]#One elt==name where returning one value
        self.type="real"
        self.stores=0
        self.isArrayed=False
        self.numDims=0
        self.dimSizes=[]
        self.storedForExperience=False
        self.code=[]
        self.initialisation=""
        self.skipCondition=""
        self.isCall=False
        self.outputMe=False
        self.usedForRebasing=False

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
    return ([ll for ll in ls if ll!=""],not(l[0:2]=="//" or l==""),[ll.upper() for ll in ls if ll!=""])#bool is whether it's a comment or empty

#eliminate excess white space,capitalise,check if it's a comment and split on multiple delimiters
def newscap(l,splits):
    l=l.strip()
    lOld=""
    while lOld!=l:
        lOld=l
        l=l.replace("  "," ")
    l=l.replace("\t"," ")
    ls=[l]
    for c in range(0,len(splits)):
        ls1=[ll.split(splits[c]) for ll in ls]
        ls=[it for sl in ls1 for it in sl]
    return (l,[ll for ll in ls if ll!=""],not(l[0:2]=="//" or l==""),[ll.upper() for ll in ls if ll!=""])#bool is whether it's a comment or empty

#start generating Futhark
numBases=0
numRebased=0
off=open(exeSubDir+"/"+"futhark.fut",'w')

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
                    if lsu[i]=="OUTPUT":
                        ci.outputMe = True
                    if lsu[i]=="EXPERIENCE":
                        ci.storedForExperience=True
                    if lsu[i]=="STORE":
                        if ls[i+1].isnumeric():
                            ci.stores = int(ls[i + 1])
                        else:
                            ci.stores=-1
                    if lsu[i]=="ARRAYED":
                        (ll,_,_)=nwscap(ls[i+1],"[]")
                        ci.isArrayed=True
                        ci.numDims=len(ll)
                        ci.dimSizes=[(lambda x: int(x) if x.isnumeric() else (numBases if not ci.usedForRebasing else numRebased))(lll) for lll in ll]
                    if lsu[i]=="TYPE":
                        ci.type=ls[i+1]
                    if  lsu[i]=="REBASE":
                        ci.usedForRebasing=True
                continue
            if section=="COMMON":
                mi.commonCode=mi.commonCode.__add__([l])
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
                if lsu[0]=="FORCE":
                    mi.forceThese=ls[1:]
                if lsu[0]=="FIRSTPROJECTIONPERIOD":
                    mi.firstProjectionPeriod=int(ls[1])
                if lsu[0] == "LASTPROJECTIONPERIOD":
                    mi.lastProjectionPeriod = int(ls[1])
            if section == "DATA" or section == "DERIVED":
                mi.hasData=True
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
                df.expression=l[l.find("=")+1:]
                mi.hasDerived=True
            if section=="PHASE":
                if lsu[0]=="NAME":
                    currPhase={}
                    mi.phases[ls[1]]=currPhase#disc of calInfoObjects
                    for ii in range(2,len(ls)):
                        if lsu[ii]=="DIRECTION":
                            mi.phaseDirections[ls[1]]=ls[ii+1]
            if section =="CALC":
                if l[0:4]=="call":
                    ci.isCall=True
                    ci.name=l[4:].strip()
                    currPhase[ls[0]] = ci
                    ci.stores=-2
                    continue
                elif lsu[0]=="INITIALISE":
                    ci.initialisation=l
                elif lsu[0]=="SKIP":
                    ci.skipCondition=l[l.find("=")+1:]
                else:
                    if firstLine:
                        firstLine=False
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

#read basic model information
modelInfoFile=sys.argv[2]
ift = open(modelSubDir + "/" + modelInfoFile+".model", 'r')
section=""
for l in ift.readlines():
    (ls,c,lsu)=nwscap(l,",=")
    if c:
        if ls[0][0] == "[":
            section = lsu[0][1:len(lsu[0]) - 1]
            continue
        if section=="BASIC":
            if lsu[0]=="MODE":
                isDependent=lsu[1]=="DEPENDENT"
        if section=="MODELS":
            modelInfos[ls[0]]=readBasicModelInfo(modelSubDir + "/" + ls[0] + ".model")
        if section=="BASES":
            numBases+=1
            bases[ls[0]]=False
            if len(ls)>2:
                bases[ls[0]]=(lsu[2]=="TRUE")
            if bases[ls[0]]:
               numRebased+=1
        if section=="REBASING":
            rebaseTimes=ls

#enum for bases plus rebase info which may later be read from run parameters instead
doRebase="["
comma=""
for k in bases.keys():
    off.write("let "+k+":i32="+str(numBases)+nl)
    doRebase+=comma+str(bases[k]).lower()
    comma=","
doRebase+="]"
off.write("let doRebase="+doRebase+nl)
off.write("let rebaseTimes:[]i32=["+",".join(rebaseTimes)+"]"+nl)

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

#type synonyms
off.write("type real=f32\n")
off.write("type int=i32\n")

#Library code - added verbatim
ift=open(libSubDir+"/"+"library.fut",'r')
for l in ift.readlines():
    off.write(l+nl)
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
    #some useful transformations in one place
    if l[0:3]=="fn ":#declare functions, add a let, convert (,,) to ()()
        l="let "+l+" = "
        l=l.replace(",",") (")
        l=l.replace("fn ","")
        return l
    l=re.sub("[a-zA-Z]\w*\s*=[^=]",lambda x: "let "+x.group(),l)#let in front of a binding
    l=re.sub("\s*return\s"," in ",l)#replace return with in
    l=convUserFn(l)#change format of calls to user functions
    return l

#Global function code
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

#enums
for enum in enums.values():
    for (k,v) in enum.items():
        off.write("let "+k+":i32="+str(v)+nl)

#other system constants
for mi in modelInfos.values():
    off.write("let firstProjectionPeriod=("+str(mi.firstProjectionPeriod)+")"+nl)

#data types
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
            typ="int"
            if df.type=="real":
                typ="real"
            off.write(comma+df.name+":"+typ+nl)
            comma=","
        off.write("}\n")

#various state types including containers for past values and the all-state
for mi in modelInfos.values():
    maxStored=0
    haveAll=False
    have0=False
    for ph in mi.phases.values():
        for ci in ph.values():#find maximum storage
            if ci.stores==-1:
                haveAll=True
                have0=True
            if ci.stores>maxStored:
                maxStored=ci.stores
            if ci.stores==0:
                have0=True
    mi.maxStored=maxStored

    #main state
    off.write("\ntype state_"+mi.name+"={\n")
    comma=""
    for ph in mi.phases.values():
        for ci in ph.values():
            if ci.stores>0  or ci.stores==-1:
                typ = "int"
                if ci.type == "real":
                    typ = "real"
                brackets=""
                for i in range(0,ci.numDims):
                    brackets=brackets+"["+str(ci.dimSizes[i])+"]"
                off.write(comma + ci.name + ":" + brackets + typ + nl)
                comma=","
    off.write("}\n")

    #loop through past states (>1)
    for i in range(2,maxStored+1):
        off.write("\ntype state_" + mi.name +"__"+str(i)+ "={\n")
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
                    off.write(comma + ci.name + ":" + brackets + typ + nl)
                    comma = ","
        off.write("}\n")

    #intermediate
    if have0:
        off.write("\ntype state_" + mi.name +"_inter={\n")
        comma = ""
        for ph in mi.phases.values():
            for ci in ph.values():
                if ci.stores ==0:
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

    #store all
    if haveAll:
        off.write("\ntype state_" + mi.name +"__999={\n")
        comma = ""
        for ph in mi.phases.values():
            for ci in ph.values():
                if ci.stores ==-1 :
                    typ = "int"
                    if ci.type == "real":
                        typ = "real"
                    off.write(comma + ci.name + ":[]" + typ + nl)#not allowing store-all for arrayed calcs
                    comma = ","
        off.write("}\n")

    #all-state
    off.write("\ntype state_" + mi.name +"_all={\n")
    mi.have0=have0
    mi.haveAll=haveAll
    if mi.hasData:
        off.write("p:data_"+mi.name+","+nl)
    if mi.hasDerived:
        off.write("der:derived_"+mi.name+","+nl)
    if haveAll:
        off.write("state__999:state_"+mi.name+"__999,"+nl)
    for i in range(2,maxStored+1):
        off.write("state__" +str(i)+ ":state_"+mi.name+"__"+str(i)+","+nl)
    off.write("state__1:state_" + mi.name + "," + nl)
    if have0:
        off.write("intermediate:state_"+mi.name+"_inter"+","+nl)
    off.write("state_new:state_" + mi.name + "," + nl)
    off.write("t:i32,\n")
    off.write("forceTheIssue:f32,\n")
    off.write("basisNum:i32\n}\n")

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
if not isDependent:#integer parameters
    mainParams=" [numPols] [numBases]  (numPeriods:i32) "
else:
    mainParams=" (numPeriods:i32) (numIters:i32) "
off.write("let main "+mainParams)
if hasESG:
    off.write(" (scensData:[][][]f32) ")
for mi in modelInfos.values():#data files
    if mi.hasData:
        off.write("(fileDataInt_"+mi.name+":[numPols][]i32) (fileDataReal_"+mi.name+":[numPols][]f32)")
#if  not isDependent:#rebasing info  At present this is read from the model file
#    off.write(" (doRebase:[numBases]bool) (isRebaseTime:[numPeriods]bool) ")
for mi in modelInfos.values():#tables
    for t in mi.tableInfos.values():
        off.write(" (table_"+t.name+"_"+mi.name+":[numBases]"+multiBracket[len(t.dims)]+"f32)")
off.write(":[][]f32="+nl)

off.write("\nunsafe\n\n")

#common code - i.e outside calcs - can really access only tables
for mi in modelInfos.values():
    for l in mi.commonCode:
        l = re.sub("[a-zA-Z]\w*\s*=[^=]", lambda x: "let " + x.group(), l)  # let in front of binding
        l = convUserFn(l)  # format of calls to user-defined functions
        for kt in mi.tableInfos.keys():  # convert table name to name of main parameter
            l = re.sub("[\W]" + kt + "[\W]",lambda x: x.group()[0] + "table_" + kt + "_" + mi.name + x.group()[len(kt) + 1:], l)
        off.write(l+nl)

#convert scenarios
off.write("let scens=scensFromArrays scensData"+nl)

#derived setting functions (inside main because they might use tables)
for mi in modelInfos.values():
    if mi.hasDerived:
        off.write("\nlet setDerived_"+mi.name+"(d:data_"+mi.name+"):derived_"+mi.name+"="+nl)
        for df in mi.dataFieldInfos.values():#set temporary variables to derived expressions
            if df.expression!="":
                expr=" "+df.expression+" "
                for kt in mi.tableInfos.keys():#convert table name to name of main parameter
                    expr=re.sub("[\W]"+kt+"[\W]",lambda x:x.group()[0]+"table_"+kt+"_"+mi.name+x.group()[len(kt)+1:],expr)
                for df2 in mi.dataFieldInfos.values():#add d. in front of data fields
                    expr=re.sub("[\W]"+df2.name+"[\W]",lambda x:x.group()[0]+"d."+df2.name+x.group()[len(df2.name)+1:],expr)
                off.write("\tlet "+df.name+"="+expr)
        off.write("\n\tin\n\t{")
        for df in mi.dataFieldInfos.values():#assemble the output record
            if df.expression!="":
                off.write(df.name+"="+df.name)
        off.write("}\n")

#get data
off.write(nl)
for mi in modelInfos.values():
    if mi.hasData:
        off.write("let fileData_"+mi.name+"=dataFromArrays_"+mi.name+" fileDataInt_"+mi.name+" fileDataReal_"+mi.name+nl)

#get derived
for mi in modelInfos.values():
    if mi.hasDerived:
        off.write("let derived_"+mi.name+"=map setDerived_"+mi.name+" fileData_"+mi.name+nl)

#some constants for an independent run
if not isDependent:
    off.write("\nlet numRebased = length(filter (id) doRebase)\n")
    off.write("let numNonRebased = length(filter (!) doRebase)\n")
    off.write("let zerosArray=zeros1 numPeriods\n")

#initialisation functions (local as need access to tables)
for mi in modelInfos.values():
    count=0
    for (phName,ph) in mi.phases.items():
        count+=1
        if mi.phaseDirections[phName]=="static":
            continue
        off.write("\nlet init_"+mi.name+"_"+phName)
        if mi.hasData:
            off.write(" (d:data_"+mi.name+") ")
        if mi.hasDerived:
            off.write(" (der:derived_" + mi.name + ") ")
        if hasESG:
            off.write(" (scen:oneScen) ")
        if count>1:#if not first phase then bring in state from end of previous phase
            off.write(" (stateFromLastPhase:state_"+mi.name+" ) ")
        off.write(":state_"+mi.name+"=\n")
        for (phName2, ph2) in mi.phases.items():#must mention all calcs (fom all phases)
            for ci in ph2.values():
                if ci.stores>0 or ci.stores==-1:#only those in state
                    if ci.initialisation!="" and ph2 is ph:
                        pos=ci.initialisation.find("=")
                        expr=ci.initialisation[pos+1:]
                        expr=" "+expr+" "
                        for kt in mi.tableInfos.keys():#convert table name to name of main parameter
                            expr=re.sub("[\W]"+kt+"[\W]",lambda x:x.group()[0]+"table_"+kt+"_"+mi.name+x.group()[len(kt)+1:],expr)
                        for df2 in mi.dataFieldInfos.values():#add d. in front of data fields or der. for derived
                            if df2.expression=="":
                                expr=re.sub("[\W]"+df2.name+"[\W]",lambda x:x.group()[0]+"d."+df2.name+x.group()[len(df2.name)+1:],expr)
                            else:
                                expr=re.sub("[\W]"+df2.name+"[\W]",lambda x:x.group()[0]+"der."+df2.name+x.group()[len(df2.name)+1:],expr)
                        for (phName3, ph3) in mi.phases.items():#3rd level (!) calc used in calc formula
                            for ci3 in ph3.values():
                                expr = re.sub("[\W]" + ci3.name + "[\W]",lambda x: x.group()[0] + "stateFromLastPhase." + ci3.name + x.group()[len(ci3.name) + 1:],expr)
                        off.write("\tlet "+ci.name+"="+expr+nl)
                    elif count == 1:  # zeroise on first phase only
                        if ci.numDims == 0:
                            off.write("\tlet " + ci.name + "=0\n")
                        else:
                            off.write("\tlet " + ci.name + "=zeros" + str(ci.numDims) + " " + " ".join(
                                map(str, ci.dimSizes)) + nl)
                    else:#bring forward (even if it's not been calculated yet it'll have zeros from the first initialisation), this would not be nec. if I could do a multiple "with"
                        off.write("let "+ci.name+"=stateFromLastPhase."+ci.name+nl)
        off.write("\n\tin {")
        comma=""
        for ph in mi.phases.values():#compose the record
            for ci in ph.values():
                if ci.stores > 0 or ci.stores == -1:
                    off.write(comma+ci.name+"="+ci.name)
                    comma=","
        off.write("}\n\n")
        #also need initialisation of all-state for later phases
        if count>1:
            off.write("\nlet init_" + mi.name + "_" + phName+"_all")
            if mi.hasData:
                off.write(" (d:data_" + mi.name + ") ")
            if mi.hasDerived:
                off.write(" (der:derived_" + mi.name + ") ")
            if hasESG:
                off.write(" (scen:oneScen) ")
            off.write(" (as:state_"+mi.name+"_all ) ="+nl)
            off.write("\tlet state_bf= init_"+ mi.name + "_" + phName+" d der scen as.state_new\n")
            off.write("\tlet as1= as with state_new=state_bf\n")
            off.write("\tin as1 with state__1 = state_bf\n")

#enums for calcs stored for experience
count=-1
off.write(nl)
for mi in modelInfos.values():
    for ph in mi.phases.values():
        for ci in ph.values():
            if ci.storedForExperience:
                count+=1
                off.write("let basis__"+ci.name+"_"+mi.name+"="+str(count)+nl)
off.write(nl)

#generate calculations - append model name to name to avoid clashes
#main effort here is to pull past values out of the correct bit of the all-state
#TODO not done:
#reference to other models (incl. filtering and reduction)
#reference to ESG
#calls
#variants
for mi in modelInfos.values():
    for (phName,ph) in mi.phases.items():
        for ci in ph.values():
            if not ci.isCall:
                off.write("let "+ci.name+"_"+mi.name+"(as:(state_"+mi.name+"_all,[][][]f32)):(state_"+mi.name+"_all,[][][]f32)=\n")
                off.write("\tlet asTemp=as.1 in"+nl)
                off.write("\tlet basisValues=as.2 in"+nl)
                if ci.isArrayed:
                    #the calc now becomes the inner-most internal function to be called by partial application
                    off.write("\tlet "+ci.name+"_arr"+str(ci.numDims))
                    for ind in range(1,ci.numDims+1):#array index parameters
                        off.write(" (i"+str(ind)+":i32) ")
                    off.write(":f32=\n")
                code=ci.code.copy()
                if ci.skipCondition!="":
                    condLine="if "+ci.skipCondition+" then "
                    if not ci.isArrayed:#not arrayed: pass entire state through unchanged
                        condLine+="as else \n"
                    else:
                        condLine+="0 else \n"#arrayed so calc is in the inner-most function - here we'll return 0
                    code.insert(0,condLine)
                for l in code:#loop through lines
                    l=" "+l+" "
                    l = re.sub("[a-zA-Z]\w*\s*=[^=]", lambda x: "let " + x.group(), l)  # let in front of binding
                    l = convUserFn(l)#format of calls to user-defined functions
                    if not ci.isArrayed:
                        if len(ci.fieldsCalcd)==1:
                            l=l.replace("return ","\tlet "+ci.name+"_res=")#final return for scalar function, returns 1 value
                        else:
                            l=l.replace("return ","\tlet ("+",".join(map(lambda x:x+"_res",ci.fieldsCalcd))+") = ")#final return for scalar function, returns tuple
                    else:
                        if len(ci.code)>1:
                            l=l.replace("return ","\tin ")#final return for array inner function
                        else:
                            l = l.replace("return ", "")  # final return for array inner function
                    for kt in mi.tableInfos.keys():#convert table name to name of main parameter
                        l=re.sub("[\W]"+kt+"[\W]",lambda x:x.group()[0]+"table_"+kt+"_"+mi.name+x.group()[len(kt)+1:],l)
                    for df in mi.dataFieldInfos.values():#add as.p. in front of data/derived fields
                        if df.expression=="":
                            l=re.sub("[\W]"+df.name+"[\W]",lambda x:x.group()[0]+"asTemp.p."+df.name+x.group()[len(df.name)+1:],l)
                        else:
                            l=re.sub("[\W]"+df.name+"[\W]",lambda x:x.group()[0]+"asTemp.der."+df.name+x.group()[len(df.name)+1:],l)
                    l=re.sub("[\W]"+"t"+"[\W]",lambda x:x.group()[0]+"asTemp.t"+x.group()[2:],l)# t
                    l=re.sub("[\W]"+"basisNum"+"[\W]",lambda x:x.group()[0]+"asTemp.basisNum"+x.group()[9:],l)#basis
                    #other calcs
                    for (phName2,ph2) in mi.phases.items():
                        for ci2 in ph2.values():
                            #present time values
                            if mi.phaseDirections[phName]!="static":
                                if ci2.stores!=0:
                                    source="asTemp.state_new."
                                else:
                                    source="asTemp.intermediate."
                            else:
                                source = "asTemp.state__999."#static phase, can only be whole array calcs, take entire array
                            for fld in ci2.fieldsCalcd:
                                l = re.sub("[\W]" + fld + "[\W]",lambda x: x.group()[0] + source + fld + x.group()[len(fld) + 1:],l)
                            #past values
                            if ci2.stores!=-1:
                                for past in range(1,ci2.stores+1):
                                    l = re.sub("[\W]" + ci2.name+"__"+str(past) + "[\W]",lambda x: x.group()[0] + "asTemp.state__"+str(past) +"."+ ci2.name + x.group()[len(ci2.name+"__"+str(past)) + 1:],l)
                            else:
                                for past in range(1,100):
                                    l = re.sub("[\W]" + ci2.name + "__" + str(past) + "[\W]",lambda x: x.group()[0] + "asTemp.state__999."  + ci2.name +"[asTemp.t+firstProjectionPeriod-"+str(past)+"]" +x.group()[len(ci2.name+"__"+str(past)) + 1:], l)
                    off.write("\t"+l+nl)
                if ci.isArrayed:#multi-level mappings for arrayed
                    for ind in range(1,ci.numDims):#loop over map functions
                        off.write("let "+ci.name+"_arr"+str(ci.numDims-ind))
                        for ind2 in range(1,ci.numDims-ind+1):#loop over parameters of a map function
                            off.write(" (i"+str(ind2)+":i32) ")
                        off.write(":"+multiBracket[ind]+"f32=map ("+ci.name+"_arr"+str(ci.numDims-ind+1)+" " )#partial application of previous mapping function
                        for ind2 in range(1,ci.numDims-ind+1):#partial application (2)
                            off.write(" i"+str(ind2)+" ")
                        off.write(") (iota "+str(ci.dimSizes[ci.numDims-ind])+") \n")#the iota to which we apply the partial application
                    off.write("let "+ci.name+"_res=map "+ci.name+"_arr1 (iota "+str(ci.dimSizes[0])+")\n")
                if ci.stores!=0:#final result (this is the same variable regardless of whether or not the calc is arrayed
                    if mi.phaseDirections[phName]!="static":
                        off.write("\nin (asTemp with state_new."+ci.name+"="+ci.name+"_res,as.2)"+nl)
                    else:
                        off.write("\nin (asTemp with state__999."+ci.name+"="+ci.name+"_res,as.2)"+nl)
                else:
                    if len(ci.fieldsCalcd)==1:#storing, might or might not be a tuple
                        off.write("\nin (asTemp with intermediate."+ci.name+"="+ci.name+"_res,as.2)"+nl)#not tuple
                    else:
                        prevas=".1"
                        for fldi in range(0,len(ci.fieldsCalcd)-1):#tuple, stages of changing as
                            fld=ci.fieldsCalcd[fldi]
                            off.write("\nlet as"+str(fldi)+"=as"+prevas+" with intermediate." + fld + "=" + fld + "_res" + nl)
                            prevas=str(fldi)
                        fld=ci.fieldsCalcd[len(ci.fieldsCalcd)-1]
                        off.write("\nin (as"+prevas+" with intermediate."+fld+"="+fld+"_res,as.2)"+nl)#final alteration to as

#"force-all" calculation
for mi in modelInfos.values():
    off.write("\nlet forceTheIssue_"+mi.name+"(as:(state_"+mi.name+"_all,[][][]f32)):(state_"+mi.name+"_all,[][][]f32)=\n")
    off.write("\tlet asTemp=as.1 in\n")
    off.write("\t(asTemp with forceTheIssue=")
    forceCode=""
    plus=""
    for ph in mi.phases.values():
        for ci in ph.values():
            if ci.isCall:
                continue
            if mi.forceThese==["all"] or mi.forceThese.__contains(ci.name):
                for elt in ci.fieldsCalcd:
                    if ci.stores==0:
                        elt="asTemp.intermediate."+elt
                    else:
                        elt="asTemp.state_new."+elt
                    if ci.numDims==1:
                        elt="(sum1 "+elt+")"
                    if ci.numDims==2:
                        elt="(sum2 "+elt+")"
                    if ci.type!="real":
                        elt="(real "+elt+")"
                    forceCode+=plus+elt
                    plus="+"
    off.write(forceCode+",as.2)"+nl)

#run one period for each phase (this is where we order)
for mi in modelInfos.values():
    count=0
    for (phName,ph) in mi.phases.items():
        count+=1
        off.write("\nlet runOnePeriod_"+mi.name+"_"+phName+"(as:(state_"+mi.name+"_all,[][][]f32)):(state_"+mi.name+"_all,[][][]f32)=\n")
        off.write("\tlet asNew=as ")
        whoCallsWhom={}
        for ci in ph.values():
            if ci.usedForRebasing:#these are applied in rebasing calcs and so do not enter the normal pipeline
                continue
            iCall=[]
            for ci2 in ph.values():#does ci use ci2?
                found = False
                for fld in ci2.fieldsCalcd:#or rather, does it use ci2's calculated fields
                    for l in ci.code:
                        for mtch in re.finditer("[\W]"+fld+"[\W]"," "+l+" "):
                            found=True
                if found:
                    iCall.append(ci2.name)
            whoCallsWhom[ci.name]=iCall
        while whoCallsWhom!={}:
            for (caller,callees) in whoCallsWhom.items():
                if callees==[]:#first calc with no ancestors
                    off.write(" |> "+caller+"_"+mi.name)
                    for l in whoCallsWhom.values():#remove this
                        if l.__contains__(caller):
                            l.remove(caller)
                    del whoCallsWhom[caller]
                    break
        if count<mi.phases.__len__():
            off.write("\n\tin asNew"+nl)
        else:
            off.write(" |> forceTheIssue_"+mi.name+nl)
            off.write("\tin asNew"+nl)

#storage
for mi in modelInfos.values():
    for (phName,phx) in mi.phases.items():
        if mi.phaseDirections[phName]=="static":#no need for storage at end of period if there are no periods
            continue
        off.write("\nlet store_"+mi.name+"_"+phName+"(as:(state_"+mi.name+"_all,[][][]f32)):(state_"+mi.name+"_all,[][][]f32)=\n")
        #store-alls: the method used (in the absence of in-place updates) is to copy the exisitng array and in-place that
        if mi.haveAll:
            st999="state__999={"
            comma=""
            for ph in mi.phases.values():
                for ci in ph.values():
                    if ci.stores==-1:
                        if ph is phx:#only do (possibly expensive) copying etc. if the store-all was actually in this phase
                            off.write("\tlet z_"+ci.name+"__new=copy as.1.state__999."+ci.name+nl)
                            off.write("\tlet "+ci.name+"__new = update z_"+ci.name+"__new (as.1.t+firstProjectionPeriod) as.1.state_new."+ci.name+nl)
                            st999+=comma+ci.name+"="+ci.name+"__new"
                        else:
                            off.write("\tlet "+ci.name+"= as.1.state__999."+ci.name+nl)
                            st999+=comma+ci.name+"="+ci.name
                        comma = ","
            st999+="}"
        off.write("\tin(\n\t{")
        if mi.hasData:
            off.write("\n\tp=as.1.p,\n")
        if mi.hasDerived:
            off.write("\tder=as.1.der,\n")
        off.write("\tbasisNum=as.1.basisNum,\n")
        if mi.phaseDirections[phName]=="forwards":
            off.write("\tt=as.1.t+1,\n")
        else:
            off.write("\tt=as.1.t-1,\n")
        off.write("\tstate__1 = as.1.state_new,\n")
        off.write("\tstate_new = as.1.state_new,\n")
        if mi.have0:
            off.write("\tintermediate = as.1.intermediate,\n")
        if mi.haveAll:
            off.write("\t"+st999+","+nl)
        off.write("\tforceTheIssue=as.1.forceTheIssue*0.001,\n")
        for past in range(2,mi.maxStored+1):
            comma = ""
            st_n = "state__"+str(past)+"={"
            for ph in mi.phases.values():
                for ci in ph.values():
                    if ci.stores>=past:
                        st_n+=comma+ci.name+"=as.1.state__"+str(past-1)+"."+ci.name
                        comma=","
            st_n += "}"
            off.write("\t" + st_n + nl)
        off.write("\t},as.2)\n")

#Functions to actually run stuff
for mi in modelInfos.values():
    #utility function to run phase 1 (only) n times (intended for running other bases)
    for ph in mi.phases.keys():
        if mi.phaseDirections[ph]!="static":
            off.write("\nlet runNPeriods_"+mi.name+"_"+ph+" (n:i32) = iterate n (runOnePeriod_"+mi.name+"_"+ph+" >-> store_"+mi.name+"_"+ph+")"+nl)

    #function to run a single basis (phase1 only) and get results (=vector of vectors item x time)
    off.write("\nlet runOneBasisFromOneTime_"+mi.name+" (as: state_"+mi.name+"_all)"+" (fromTime:i32 ) (bn:i32):[][]f32=")
    off.write("\n\tlet as2=as with basisNum=bn")
    off.write("\n\tlet final_all_state = (runNPeriods_"+mi.name+"_phase1 (as.p."+mi.termField+"-fromTime+1i32))  (as2,[])")#the [][][]f32 is empty as we are not running experience
    off.write("\n\tlet res:[][]f32=")
    concat=""
    numForExperience=0
    for (phName,ph) in mi.phases.items():
        if phName=="phase1":
            for ci in ph.values():
                if ci.storedForExperience:
                    off.write(concat+"[final_all_state.1.state__999."+ci.name+"]")
                    numForExperience+=1
                    concat="++"
            break
    off.write("\n\t in res\n")

    #run with rebasing
    off.write("let rebasedBases=map (numNonRebased+) (iota numRebased)"+nl)
    off.write("\nlet rbtrue=replicate (length rebaseTimes) true"+nl)
    off.write("let rbts:*[]bool = replicate numPeriods"+" false "+nl)
    off.write("let isRebaseTime:*[]bool=scatter rbts rebaseTimes rbtrue\n")
    off.write("\nlet calcRebasedResults_"+mi.name+"(as:(state_"+mi.name+"_all,[][][]f32)):(state_"+mi.name+"_all,[][][]f32)="+nl)
    off.write("\tlet rebasedResults1=\n")
    off.write("\t\tif isRebaseTime[as.1.t] then\n")
    off.write("\t\t\t(map (runOneBasisFromOneTime_"+mi.name+" as.1 (as.1.t)) rebasedBases)\n")
    off.write("\t\telse\n")
    off.write("\t\t\t(zeros3 numRebased "+str(numForExperience)+" numPeriods)"+nl)
    off.write("\tlet rebasedResults=rebasedResults1[:,:,firstProjectionPeriod:]"+nl)#for basis results, make time start at 0 not firstProjectionPeriod so all references to basisValues can just use t
    off.write("\tlet asPreRebase=(as.1,rebasedResults)"+nl)
    off.write("\tlet asWithRebasing=asPreRebase")
    for ph in mi.phases.values():
        for ci in ph.values():
            if ci.usedForRebasing:
                off.write("|> "+ci.name+"_"+mi.name)
    off.write("\n\tin (asWithRebasing.1,as.2)")#calculate state based on rebased results but pass on the original non-rebased results
    off.write("\nlet runNPeriodsWithRebasing_"+mi.name+" (n:i32) = iterate n (runOnePeriod_"+mi.name+"_phase1 >-> store_"+mi.name+"_phase1 >->calcRebasedResults_"+mi.name+")"+nl)

    #main function for running a single policy (independent)
    #TODO - rebased!

    #signature
    off.write("\nlet runOnePol_"+mi.name)
    if hasESG:
        off.write("(scen:oneScen) ")
    off.write("(pol:data_"+mi.name+") ")
    if mi.hasDerived:
        off.write("(der:derived_"+mi.name+")")
    off.write(":[][]f32 ="+nl)

    #initial state from either phase0 or phase1 initialisation)
    hasPhase0=mi.phases.keys().__contains__("phase0")
    if hasPhase0:
        off.write("\tlet init_state = init_"+mi.name+"_phase0 pol der scen\n")
    else:
        off.write("\tlet init_state = init_"+mi.name+"_phase1 pol der scen\n")

    #initial all-state
    off.write("\tlet init_all_state"+("_prePhase0" if hasPhase0 else "")+":state_"+mi.name+"_all = {"+nl)
    off.write("\tp=pol,\n")
    if mi.hasDerived:
        off.write("\tder=der,\n")
    off.write("\tbasisNum=0,\n")
    off.write("\tforceTheIssue=0,\n")
    off.write("\tt=("+("0" if hasPhase0 else "firstProjectionPeriod")+"),\n")
    off.write("\tstate_new=init_state,\n")
    off.write("\tstate__1=init_state,\n")
    if mi.have0:
        comma=""
        off.write("\tintermediate={")
        for ph in mi.phases.values():
            for ci in ph.values():
                if ci.stores==0:
                    if not ci.isArrayed:
                        for fld in ci.fieldsCalcd:
                            off.write(comma+fld+"=0")
                            comma=","
                    else:
                        off.write(comma+ci.name+"=(zeros"+str(ci.numDims))
                        for dim in ci.dimSizes:
                            off.write(" "+str(dim))
                        off.write(") ")
                        comma=","
        off.write("\t},\n")
    if mi.haveAll:
        comma=""
        off.write("\tstate__999={")
        for ph in mi.phases.values():
            for ci in ph.values():
                if ci.stores==-1:
                    off.write(comma+ci.name+"=zerosArray")
                    comma=","
        off.write("\t},\n")
    for past in range(2,mi.maxStored+1):
        comma=""
        off.write("\tstate__"+str(past)+"={")
        for ph in mi.phases.values():
            for ci in ph.values():
                if ci.stores==past:
                    if not ci.isArrayed:
                        off.write(comma+ci.name+"=0")
                        comma=","
                    else:
                        off.write(comma+ci.name+"=(zeros"+str(ci.numDims))
                        for dim in ci.dimSizes:
                            off.write(" "+str(dim))
                        off.write(") ")
                        comma=","
        if past<maxStored:
            off.write("\t},\n")
        else:
            off.write("\t}\n")
    off.write("\t}"+nl+nl)

    #run phase0 (should it exist)
    if hasPhase0:
        off.write("\tlet init_all_state=(init_all_state_prePhase0,[])\n \t|> " + nl)
        off.write("\t(runNPeriods_"+mi.name+"_phase0 (1-firstProjectionPeriod))\n\t|> (.1) |>\n")
        off.write("\t(init_"+mi.name+"_phase1_all pol der scen"+")"+nl)

    #run the non-rebased bases
    off.write("\n\tlet nonRebasedResults1:[][][]f32=map (runOneBasisFromOneTime_"+mi.name+" init_all_state ("+str(mi.firstProjectionPeriod)+") ) (map (1+) (iota (numNonRebased-1)))"+nl)
    off.write("\tlet nonRebasedResults=nonRebasedResults1[:,:,firstProjectionPeriod:]"+nl)#for basis results, make time start at 0 not firstProjectionPeriod so all references to basisValues can just use t

    #run experience basis (incl. rebasing)
    off.write("\n\tlet experience_super_state = (init_all_state,nonRebasedResults) |> (runNPeriodsWithRebasing_"+mi.name+" (pol."+mi.termField+"))  "+nl)
    #run later phases for experience
    for (phName,ph) in mi.phases.items():
        if phName=="phase1" or phName=="phase0":#do not do the first phases
            continue
        off.write("\t|>\n")
        if mi.phaseDirections[phName]!="static":
            off.write("\t(\(x:state_"+mi.name+"_all,y:[][][]f32)->(((init_"+mi.name+"_"+phName+"_all pol der scen ) x),y))\n\t|>\n")#pipe into phase initialisation
        if mi.phaseDirections[phName]!="static":
            off.write("\t(runNPeriods_"+mi.name+"_"+phName+" pol."+mi.termField+")"+nl)#pipe into next phase
        else:
            off.write("\trunOnePeriod_"+mi.name+"_"+phName+nl)#pipe into next phase
    off.write("\tlet experience_state=experience_super_state.1"+nl)#get output results for experience
    off.write("\tlet res:[][]f32=")
    plus=""
    for ph in mi.phases.values():
        for ci in ph.values():
            if ci.outputMe:
                off.write(plus+"[experience_state.state__999."+ci.name+"]")
                plus="++"
    off.write("\n\tin res"+nl)

#closure
#todo will need a more sophisticated methodology here to avoid memory blowup e.g. extract certain periods
model=list(modelInfos.keys())[0]#todo temporary
off.write("let allPols=map2 (runOnePol_"+model+" scens[0]) fileData_"+model+" derived_"+model+nl)
off.write("in reduce (+..+) (zeros2 "+str(numForExperience)+" numPeriods) allPols\n")
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
ofc.write("struct futhark_context_config * cfg = futhark_context_config_new()"+nl);
ofc.write("struct futhark_context * ctx = futhark_context_new(cfg);"+nl)

#declare c table arrays
ofc.write("\nfloat ")
comma=""
for mi in modelInfos.values():
    for (k,t) in mi.tableInfos.items():
        ofc.write(comma+"*table_"+mi.name+"_"+k)
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
#todo

#read tables and get size information, this amalgamates all bases into one big table
basisToNum={"SINGLE":1,"PREFIX":2,"SUFFIX":3,"SUBDIR":4}
ofc.write("int err;\n")
ofc.write("char *basisNames["+str(len(bases))+"]={")
comma=""
for basis in bases:
    ofc.write(comma+"\""+basis+"\"")
    comma=","
ofc.write("};\n")
for mi in modelInfos.values():
    for (k,t) in mi.tableInfos.items():
        comma=""
        ofc.write("int dimSizes_"+mi.name+"_"+k+"["+str(len(t.dims))+"]={")
        for e in t.dims:
            if e=="int":
                ofc.write(comma+"-1")
            else:
                ofc.write(comma+str(enums[e].__len__()))
            comma=","
        ofc.write("};\n")
        ofc.write("err=readTable(\""+tablesSubDir+"/"+k+"\",\"\","+str(len(t.dims))+",dimSizes_"+mi.name+"_"+k+","+str(numBases)+",basisNames,"+str(basisToNum[t.basis])+","+"&table_"+mi.name+"_"+k+");"+nl)

#create futhark table arrays
tables=[]
for mi in modelInfos.values():
    for (k,t) in mi.tableInfos.items():
        ofc.write("struct futhark_f32_"+str(1+len(t.dims))+"d *fut_"+"table_"+mi.name+"_"+k+"=futhark_new_f32_"+str(1+len(t.dims))+"d(ctx,"+"table_"+mi.name+"_"+k+","+str(numBases)+",")
        tables=tables.__add__(["fut_"+"table_"+mi.name+"_"+k])
        comma=""
        dimCount=0
        for e in t.dims:
            if e == "int":
                ofc.write(comma + "dimSizes_"+mi.name+"_"+k+"["+str(dimCount)+"]")
            else:
                ofc.write(comma + str(enums[e].__len__()))
            comma = ","
            dimCount+=1
        ofc.write(");\n")

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
                    numDFInt+=1
                else:
                    numDFReal+=1
        ofc.write("int intOrReal_"+mi.name+"["+str(numDF)+"]={")
        comma=""
        for df in mi.dataFieldInfos.values():
            if df.expression=="":
                ofc.write(comma+("1" if df.type=="real" else "0"))
                comma=","
        ofc.write("};\n")
        ofc.write("int arraySize_"+mi.name+"["+str(numDF)+"]={")
        comma=""
        for df in mi.dataFieldInfos.values():
            if df.expression=="":
                ofc.write(comma+("1" if df.arraySize==0 else str(df.arraySize)))
                comma=","
        ofc.write("};\n")
        ofc.write("err=readData(\""+dataSubDir+"/data_"+mi.name+"\",\"\","+str(numDF)+",intOrReal_"+mi.name+",arraySize_"+mi.name+",&numPols,fileDataInt_"+mi.name+",fileDataReal_"+mi.name+");\n")
        dataFiles=dataFiles.__add__(["fileDataInt_"+mi.name])
        dataFiles=dataFiles.__add__(["fileDataReal_"+mi.name])
        ofc.write("struct futhark_i32_2d *fut_fileDataInt_"+mi.name+"=futhark_new_i32_2d(ctx,fileDataInt_"+mi.name+",numPols,"+str(numDFInt)+");"+nl)
        ofc.write("struct futhark_f32_2d *fut_fileDataReal_" + mi.name + "=futhark_new_f32_2d(ctx,fileDataReal_" + mi.name + ",numPols," + str(numDFReal) + ");" + nl)

#declare futhark ESG arrays
#todo

#create the futhark results arrays
numOutputs=0
for mi in modelInfos.values():
    numPeriods=mi.lastProjectionPeriod-mi.firstProjectionPeriod+1
    for ph in mi.phases.values():
        for ci in ph.values():
            if ci.outputMe:
                numOutputs+=1
ofc.write("struct futhark_f32_2d *fut_Res;\n")
ofc.write("float *res=(float*) malloc("+str(numOutputs)+"*"+str(numPeriods)+"*sizeof(float));\n")

#call futhark (incl.timing)
ofc.write("struct timespec startTime,endTime;\n")
ofc.write("clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&startTime);\n")

ofc.write("int futErr=futhark_entry_main(ctx,&fut_Res,"+str(numPeriods)+",")
for dfl in dataFiles:
    ofc.write("fut_"+dfl+",")
comma=""
for tbl in tables:
    ofc.write(comma+tbl)
    comma=","
ofc.write(");\n")

ofc.write("clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&endTime);\n")
ofc.write("double diffTime=(endTime.tv_sec-startTime.tv_sec)+(endTime.tv_nsec-startTime.tv_nsec)/1e9;\n")

#get results from futhark
ofc.write("futhark_values_f32_2d(ctx,fut_Res,res);\n")

#free c table arrays
for tbl in tables:
    ofc.write("free ("+tbl[4:]+");"+nl)

#free futhark table arrays
for mi in modelInfos.values():
    for (k,t) in mi.tableInfos.items():
        ofc.write("futhark_free_f32_"+str(1+len(t.dims))+"d(ctx,fut_table_"+mi.name+"_"+k+");\n")

#free c data arrays
for df in dataFiles:
    ofc.write("free ("+df+");"+nl)

#free futhark data arrays
for df in dataFiles:
    ofc.write("futhark_free_f32_2d(ctx,fut_"+df+ ");\n")

#free c ESG arrays
#todo

#free futhark ESG arrays
#todo

#free context
ofc.write("futhark_context_free(ctx);\n")
ofc.write("futhark_context_config_free(cfg);\n")

#output results to file

ofc.write("\nreturn 0;\n")
ofc.write("}"+nl)
ofc.close()