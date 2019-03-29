#dummy equity returns, just alternate the international and large cap returns
import random
ift1 = open("/home/andrew/futhark/inepta/va/gans_stuff/vamc/demo/InforceValuation/RN/base/IntlEquity.csv")
ift2 = open("/home/andrew/futhark/inepta/va/gans_stuff/vamc/demo/InforceValuation/RN/base/LargeCapEquity.csv")
off=open("/home/andrew/futhark/inepta/va/scenarios/scens.txt",'w')
for i in range(1,1001):
    off.write("~"+str(i)+"\n")
    l1=ift1.readline().split(",")
    l2=ift2.readline().split(",")
    for t in range(1,360):
        off.write(str(t)+"\t"+(l1[t]+"\t"+l2[t]+"\t")*5+str(0.02+random.random()*0.02)+"\n")
    off.write(str(360) + "\t" + (l1[359] + "\t" + l2[359] + "\t") * 5 + str(0.02 + random.random() * 0.02) + "\n")
ift1.close()
ift2.close()
off.close()
