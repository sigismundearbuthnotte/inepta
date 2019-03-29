ift = open("/home/andrew/futhark/inepta/va/gans_stuff/vamc/datasets/inforce.csv", 'r')
off=open("/home/andrew/futhark/inepta/va/data/data_va",'w')
off.write("190000\n")
import operator
import functools
c=0
unsorted={}
for l in ift.readlines():
    l=l.replace("\n","")
    c=c+1
    if c==1:
        continue
    ls=l.split(",")
    lo=ls[0]+"\t"
    lo+=("male" if ls[2]=="M" else "female")+"\t"
    lo+=ls[3]+"\t"#product
    age=(int(ls[7])-int(ls[6]))/365.25
    ageYears=int(age)
    ageMonths=int((age-ageYears)*365.25/31)
    lo+=str(ageYears)+"\t"+str(ageMonths)+"\t"
    lo+="".join([ll+"\t" for ll in ls[8:15]])
    numFunds=functools.reduce(operator.add,[(1 if float(ll)>0 else 0) for ll in ls[15:25]])
    lo+=str(numFunds)+"\t"
    fundCodes="".join(["fund"+ll[1]+"\t" for ll in list(zip(ls[15:25],ls[25:35])) if float(ll[0])>0])+("0\t"*(10-numFunds))
    fundCodes2="".join([(ll[1] if ll[1]<='9' else 'a') for ll in list(zip(ls[15:25],ls[25:35])) if float(ll[0])>0])+("0"*(10-numFunds))
    fundFees="".join([ll[1]+"\t" for ll in list(zip(ls[15:25],ls[35:45])) if float(ll[0])>0])+("0\t"*(10-numFunds))
    fundValues="".join([str(int(float(ll)))+"\t" for ll in ls[15:25] if float(ll)>0])+("0\t"*(10-numFunds))
    lo+=fundCodes
    lo+=fundValues
    lo+=fundFees
    termOS=int((int(ls[5])-int(ls[7]))/365.25*12)
    elapsed=int((int(ls[7])-int(ls[4]))/365.25*12)
    renewalTerm=60
    termToRnl=renewalTerm-elapsed%renewalTerm
    lo+=str(termOS)+"\t"
    lo+=str(elapsed)+"\t"
    lo+=str(termToRnl)+"\t"
    lo+=str(renewalTerm)+"\t"
    gteedAnnFac=10
    lo+=str(gteedAnnFac)+"\t"
    termStr=str(termOS)
    if termOS<100:
        termStr="0"+termStr
    if termOS<10:
        termStr="0"+termStr
    termStr2=str(int(termOS/12))
    if int(termOS/12)<10:
        termStr2="0"+termStr2

    id="0"*(6-len(str(c)))+str(c)

    #current experiment
    #key=str(numFunds if numFunds<10 else 99)+"_"+termStr+"_"+ls[3]+"_"+str(c)#numfunds, term EXACT, THEN PRODUCT =91

    #current best
    key=str(numFunds if numFunds<10 else 99)+"_"+termStr+"_"+ls[3]+"_"+str(c)#numfunds, term EXACT, THEN PRODUCT =91

    #old
    #key=str(numFunds if numFunds<10 else 99)+"_"+termStr+"_"+ls[3]+"_"+fundCodes2+"_"+str(c)#numfunds, term EXACT, THEN PRODUCT =91
    #key=termStr+"_"+str(numFunds if numFunds<10 else 99)+"_"+ls[3]+"_"+str(c)#numfunds, term EXACT, THEN PRODUCT =91
    #key=str(numFunds if numFunds<10 else 99)+"_"+ls[3]+"_"+termStr+"_"+str(c)#numfunds, term EXACT, THEN PRODUCT =91
    #key=str(numFunds if numFunds<10 else 99)+"_"+termStr+"_"+ls[3]+"_"+id#numfunds, term EXACT, THEN PRODUCT =91
    #key=str(numFunds if numFunds<10 else 99)+"_"+fundCodes2+"_"+termStr+"_"+ls[3]+"_"+id#numfunds,funds-alpha, term EXACT, THEN PRODUCT =91
    #key=str(numFunds if numFunds<10 else 99)+"_"+termStr+"_"+ls[3]+"_"+str(c)#numfunds, term EXACT, THEN PRODUCT =91
    #key=ls[3]+"_"+str(numFunds if numFunds<10 else 99)+"_"+termStr+"_"+str(c)#numfunds, term exact=96
    #key = ls[3]+ "_" + termStr2 + "_"+str(numFunds if numFunds<10 else 99)+"_" + fundCodes2  + "_" + str(c)#=106
    #key = ls[3]+ "_" + termStr + "_"+str(numFunds if numFunds<10 else 99)+"_" + fundCodes2  + "_" + str(c)#=117
    #key = ls[3] + "_"+str(numFunds if numFunds<10 else 99)+"_" + fundCodes2 + "_" + termStr + "_" + str(c)#=163
    #key=ls[3]+"_"+str(numFunds if numFunds<10 else 99)+"_"+str(termOS)+"_"+str(c)#numfunds, term exact
    #key = ls[3] + "_" + fundCodes2 + "_" + str(termOS) + "_" + str(c)#funds in lex order, ignore missing, term
    #key = ls[3] + "_"+str(numFunds if numFunds<10 else 99)+"_" + fundCodes2 + "_" + str(termOS) + "_" + str(c)#funds in lex order, override of number of funds, term
    #key = ls[3]+ "_" + str(termOS) + "_"+str(numFunds if numFunds<10 else 99)+"_" + fundCodes2  + "_" + str(c)#term, funds in lex order, override of number of funds
    #key = ls[3]+ "_" + str(termOS/12) + "_"+str(numFunds if numFunds<10 else 99)+"_" + fundCodes2  + "_" + str(c)#term, funds in lex order, override of number of funds
    unsorted[key]=lo
sortedKeys=sorted(list(unsorted.keys()))
for k in sortedKeys:
    off.write(unsorted[k]+"\n")
ift.close()
off.close()
