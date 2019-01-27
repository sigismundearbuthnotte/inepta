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
tablesSubDir=rootSubDir+"/tables"#base subdirectory for tables
modelSubDir=rootSubDir+"/models"
exeSubDir=rootSubDir+"/exe"
outputSubDir=rootSubDir+"/output"
libSubDir=rootSubDir+"/library"#base subdirectory for tables

#dicts, sets etc.
modelInfos={}#name->modelInfo
enums={}#name->(dict of names->integer)

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
        self.tableInfos={}
        self.hasData=False
        self.hasDerived=False
        self.esg={}#only top model should have one of these

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
        self.numDims=0
        self.dimSizes=[]
        self.storeAtRebase=False
        self.code=[]
        self.initialisation=""
        self.isCall=False

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
            if section =="CALC":
                if l[0:4]=="call":
                    ci.isCall=True
                    ci.name=l[4:].strip()
                    currPhase[ls[0]] = ci
                    ci.stores=-2
                    continue
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
for l in ift.readlines():
    (ls,c,lsu)=nwscap(l,"=")
    if c:
        #mode
        if lsu[0]=="MODE":
            isDependent=lsu[1]=="DEPENDENT"
        if lsu[0]=="MODEL":
            modelInfos[lsu[1]]=readBasicModelInfo(modelSubDir + "/" + ls[1] + ".model")

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

#start generating Futhark
off=open(exeSubDir+"/"+"futhark.fut",'w')

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

    #main state
    off.write("\ntype state_"+mi.name+"={\n")
    comma=""
    for ph in mi.phases.values():
        for ci in ph.values():
            if ci.stores>0:
                typ = "int"
                if ci.type == "real":
                    typ = "real"
                brackets=""
                for i in range(0,ci.numDims):
                    brackets=brackets+"["+str(ci.dimSizes[i])+"]"
                off.write(comma+ci.name+":"+brackets+typ+nl)
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
                if ci.stores ==0 or ci.stores==-1:
                    typ = "int"
                    if ci.type == "real":
                        typ = "real"
                    brackets = ""
                    for i in range(0, ci.numDims):
                        brackets = brackets + "[" + str(ci.dimSizes[i]) + "]"
                    off.write(comma + ci.name + ":" + brackets + typ + nl)
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
    if mi.hasData:
        off.write("p:data_"+mi.name+","+nl)
    if haveAll:
        off.write("state__999:state_"+mi.name+"__999,"+nl)
    for i in range(2,maxStored+1):
        off.write("state__" +str(i)+ ":state_"+mi.name+"__"+str(i)+","+nl)
    off.write("state__1:state_" + mi.name + "," + nl)
    off.write("intermediate:state_"+mi.name+"_inter"+","+nl)
    off.write("state_new:state_" + mi.name + "," + nl)
    off.write("t:i32,\n")
    off.write("forceTheIssue:f32,\n")
    off.write("basisNum:i32\n}\n")

#scenario type
off.write("\ntype oneScen={\n")
for mi in modelInfos.values():
    if mi.esg!={}:
        comma=""
        for (k,v) in mi.esg.items():
            off.write(comma+k+":[]")
            if v!=[1]:
                for i in v:
                    off.write("["+str(i)+"]")
            off.write("f32\n")
            comma=","
        off.write("}\n\n")
        break

#main function
off.write(nl)
if not isDependent:#integer parameters
    mainParams=" [numPols] [numBases]  (numPeriods:i32) "
else:
    mainParams=" (numPeriods:i32) (numIters:i32) "
off.write("let main "+mainParams)
for mi in modelInfos.values():#data files
    if mi.hasData:
        off.write("(fileDataInt_"+mi.name+":[numPols][]i32) (fileDataReal_"+mi.name+":[numPols][]f32)")
if  not isDependent:#rebasing info
    off.write(" (doRebase:[numBases]bool) (isRebaseTime:[numPeriods]bool) ")
for mi in modelInfos.values():#tables
    for t in mi.tableInfos.values():
        off.write(" (table_"+t.name+"_"+mi.name+":[numBases]"+multiBracket[len(t.dims)]+"f32)")
off.write(":[][]f32="+nl)

off.write("\nunsafe\n\n")

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
        off.write("let data_"+mi.name+"=dataFromArrays_"+mi.name+" fileDataInt_"+mi.name+" fileDataReal_"+mi.name+nl)

#get derived
for mi in modelInfos.values():
    if mi.hasDerived:
        off.write("let derived_"+mi.name+"=map setDerived_"+mi.name+" data_"+mi.name+nl)

#some constants for an independent run
if not isDependent:
    off.write("\nlet numRebased = length(filter (id) doRebase)\n")
    off.write("let numProxies = length(filter (!) doRebase)\n")
    off.write("let zerosArray=zeros1 numPeriods\n")

#closure
off.write("in [[0]]")#temporary return value
off.close()