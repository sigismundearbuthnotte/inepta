#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <stdlib.h>
#include <cstdlib>
#include <math.h>
#include <map>

#define REAL float
//#define debug
#define openacc

using namespace std;

int main()
{
    //global stuff
    const string mort_pre_ret_fileName="/home/andrew/futhark/inepta/va/tables/va_mort_pre_retirement";
    const string mort_post_ret_fileName="/home/andrew/futhark/inepta/va/tables/va_mort_post_retirement";
    const string data_fileName="/home/andrew/futhark/inepta/va/data/data_va";
    const string scen_fileName="/home/andrew/futhark/inepta/va/scenarios/scens.txt";
    const float eps=1e-7;
    int ii;
    string line;

    //constants
    const int numPeriods=360;
    const int numScens=1000;
    const int numPols=190000;
    const int numFunds=10;
    const int numCalYears=90;
    const int firstCalYear=2018;
    const int valYear=2018;
    const int valMonth=12;
    const REAL shortRate=0.02;
    const REAL discFacMonth=exp(-shortRate/12);
    const int ABRP=0;
    const int ABRU=1;
    const int ABSU=2;
    const int DBAB=3;
    const int DBIB=4;
    const int DBMB=5;
    const int DBRP=6;
    const int DBRU=7;
    const int DBSU=8;
    const int DBWB=9;
    const int IBRP=10;
    const int IBRU=11;
    const int IBSU=12;
    const int MBRP=13;
    const int MBRU=14;
    const int MBSU=15;
    const int WBRP=16;
    const int WBRU=17;
    const int WBSU=18;

    //enums
    map<string,int> funds={{"fund1",0},{"fund2",1},{"fund3",2},{"fund4",3},{"fund5",4},{"fund6",5},{"fund7",6},{"fund8",7},{"fund9",8},{"fund10",9},};
    map<string,int>products={{"ABRP",0},{"ABRU",1},{"ABSU",2},{"DBAB",3},{"DBIB",4},{"DBMB",5},{"DBRP",6},{"DBRU",7},{"DBSU",8},{"DBWB",9},{"IBRP",10},{"IBRU",11},{"IBSU",12},{"MBRP",13},{"MBRU",14},{"MBSU",15},{"WBRP",16},{"WBRU",17},{"WBSU",18}};
    map<string,int>fCodes={{"fund1",0},{"fund2",1},{"fund3",2},{"fund4",3},{"fund5",4},{"fund6",5},{"fund7",6},{"fund8",7},{"fund9",8},{"fund10",9},};

    //read tables
    REAL mort_pre_ret[116][2];
    REAL mort_post_ret[2][201][numCalYears];
    ifstream inFile;
    #ifdef debug
        ofstream ofile;
        ofile.open("/home/andrew/futhark/inepta/va/testing/testout");
    #endif
    inFile.open(mort_pre_ret_fileName.c_str());
    getline(inFile,line);
    getline(inFile,line);
    for (int i=0;i<116;++i)
        inFile>>ii>>mort_pre_ret[i][0]>>mort_pre_ret[i][1];
    inFile.close();
    inFile.open(mort_post_ret_fileName.c_str());
    for (int sex=0;sex<2;++sex)
    {
        getline(inFile,line);
        getline(inFile,line);
        for (int i=0;i<201;++i)
        {
            getline(inFile,line);
            istringstream iss(line);
            iss>>ii;
            for (int jj=0;jj<numCalYears;++jj)
                iss>>mort_post_ret[sex][i][jj];
        }
    }
    inFile.close();

    //read data
    int *sexes,*productTypes,*ageYears_ds,*ageMonths_ds,*numFunds_ds,*fundCodes,*termOSs,*elapsedMonthss,*termToNextRenewals,*renewalTerms;

    sexes=new int[numPols];
    productTypes=new int[numPols];
    ageYears_ds=new int[numPols];
    ageMonths_ds=new int[numPols];
    numFunds_ds=new int[numPols];
    fundCodes=new int[numPols*10];
    termOSs=new int[numPols];
    elapsedMonthss=new int[numPols];
    termToNextRenewals=new int[numPols];
    renewalTerms=new int[numPols];

    REAL *baseFee_ds,*riderFee_ds,*rollUpRates,*gbAmt_ds,*gmwbBalance_ds,*wbWithdrawalRates,*withdrawals,*gteedAnnFacs,
        *fundValues,*fundFees;
    baseFee_ds=new REAL[numPols];
    riderFee_ds=new REAL[numPols];
    rollUpRates=new REAL[numPols];
    gbAmt_ds=new REAL[numPols];
    gmwbBalance_ds=new REAL[numPols];
    wbWithdrawalRates=new REAL[numPols];
    withdrawals=new REAL[numPols];
    gteedAnnFacs=new REAL[numPols];
    fundValues=new REAL[numPols*10];
    fundFees=new REAL[numPols*10];

    inFile.open(data_fileName.c_str());
    getline(inFile,line);
    int pos=0;
    for (int pol=0;pol<numPols;++pol)
    {
        int ii;
        string l;
        getline(inFile,line);
        istringstream iss(line);
        iss>>ii;
        iss>>l;
        if (l=="male")
            sexes[pol]=0;
        else
            sexes[pol]=1;
        iss>>l;
        productTypes[pol]=products[l];
        iss>>ageYears_ds[pol]>>ageMonths_ds[pol]>>baseFee_ds[pol]>>riderFee_ds[pol]>>rollUpRates[pol]>>gbAmt_ds[pol]>>gmwbBalance_ds[pol]>>wbWithdrawalRates[pol]>>
            withdrawals[pol]>>numFunds_ds[pol];
        for (int i=0;i<numFunds;++i)
        {
            iss>>l;
            fundCodes[pos++]=fCodes[l];
        }
        pos-=numFunds;
        for (int i=0;i<numFunds;++i)
            iss>>fundValues[pos++];
        pos-=numFunds;
        for (int i=0;i<numFunds;++i)
            iss>>fundFees[pos++];
        pos+=10-numFunds;
        iss>>termOSs[pol]>>elapsedMonthss[pol]>>termToNextRenewals[pol]>>renewalTerms[pol]>>gteedAnnFacs[pol];
    }
    inFile.close();

    //read scenarios
    REAL *fundRets,*annDiscRate;
    fundRets=new REAL[numScens*numPeriods*10];
    pos=0;
    int pos2=0;
    annDiscRate=new REAL[numScens*numPeriods];
    inFile.open(scen_fileName.c_str());
    for (int scen=0;scen<numScens;++scen)
    {
        getline(inFile,line);
        for (int i=0;i<numPeriods;++i)
        {
            getline(inFile,line);
            istringstream iss(line);
            iss>>ii;
            for (int f=0;f<10;++f)
                iss>>fundRets[pos++];
            iss>>annDiscRate[pos2++];
        }
    }
    inFile.close();

    //calcs
    //policy loop
    REAL totCOG=0;
    #ifdef openacc
        #pragma acc parallel loop gang vector reduction(+:totCOG) copyin(fundRets[0:numScens*numPeriods*10]) copyin(annDiscRate[0:numScens*numPeriods]) copyin(mort_pre_ret[0:116][0:2]) copyin(mort_post_ret[0:2][0:201][0:numCalYears])
    #endif
    for (int pol=0;pol<numPols;++pol)
    {
        int sex,productType,ageYears_d,ageMonths_d,numFunds_d,*fundCode,termOS,elapsedMonths,termToNextRenewal,renewalTerm;
        REAL baseFee_d,riderFee_d,rollUpRate,gbAmt_d,gmwbBalance_d,wbWithdrawalRate,withdrawal,gteedAnnFac,
            *fundValue,*fundFee;

        sex=sexes[pol];
        productType=productTypes[pol];
        ageYears_d=ageYears_ds[pol];
        ageMonths_d=ageMonths_ds[pol];
        numFunds_d=numFunds_ds[pol];
        fundCode=&fundCodes[pol*10];
        termOS=termOSs[pol];
        elapsedMonths=elapsedMonthss[pol];
        termToNextRenewal=termToNextRenewals[pol];
        renewalTerm=renewalTerms[pol];
        baseFee_d=baseFee_ds[pol];
        riderFee_d=riderFee_ds[pol];
        rollUpRate=rollUpRates[pol];
        gbAmt_d=gbAmt_ds[pol];
        gmwbBalance_d=gmwbBalance_ds[pol];
        wbWithdrawalRate=wbWithdrawalRates[pol];
        withdrawal=withdrawals[pol];
        gteedAnnFac=gteedAnnFacs[pol];
        fundValue=&fundValues[pol*10];
        fundFee=&fundFees[pol*10];

        REAL cog=0;
        bool hasIB=productType==DBIB||productType==IBRP||productType==IBRU||productType==IBSU;
        bool hasDeathBen=productType==DBAB||productType==DBIB||productType==DBMB||productType==DBRP||productType==DBRU||productType==DBSU||productType==DBWB;
        bool hasLivingBen=productType==ABRP||productType==ABRU||productType==ABSU||productType==DBAB;
        bool hasWithdrawalBen=productType==DBWB||productType==WBRP||productType==WBRU||productType==WBSU;
        bool hasMatyBen= productType==MBSU||productType==MBRU||productType==MBRP||productType==DBMB;
        const REAL rollupMonthly=pow(1+rollUpRate,1.0/12.0);

        //scenario loop
        for (int scen=0;scen<numScens;++scen)
        {
            //initialise
            int termIFMonths__1=elapsedMonths%12;
            REAL fundCF__1[numFunds];
            for (int f=0;f<numFunds_d;++f)
                fundCF__1[f]=fundValue[f];
            int termOSToRenewal__1=termToNextRenewal;
            REAL discFac__1=1;
            REAL gmwbBalance__1=gmwbBalance_d;
            REAL gbAmtCF__1=gbAmt_d;
            REAL survCF__1=1;
            int ageMonths__1=ageMonths_d;
            int ageYears__1=ageYears_d;

            //post retirement survivorship
            REAL annSurv[55];
            annSurv[0]=1;
            if (hasIB)
            {
                int matYear=(valYear*12+valMonth+termOS)/12;
                int matMonth=(valYear*12+valMonth+termOS)%12;
                REAL prop=matMonth/12.;
                int ageMat=(ageYears_d*12+ageMonths_d+termOS)/12;
                for (int i=0;i<54;++i)
                {
                    int calYear=matYear+i;
                    int age=ageMat+i;
                    REAL pxs1=1-mort_post_ret[sex][age][calYear-firstCalYear];
                    REAL pxs2=1-mort_post_ret[sex][age][calYear+1-firstCalYear];
                    REAL pxs=pow(pxs1,1-prop)*pow(pxs2,prop);
                    annSurv[i+1]=annSurv[i]*pxs;
                }
            }

            //time loop
            REAL pvCOG=0;
            for (int t=1;t<=termOS;++t)
            {
                int termIFMonths=termIFMonths__1==11?0:++termIFMonths__1;
                REAL accountValueBeforeGB=0;

                REAL fundAfterGrowth[numFunds],riderFee[numFunds],baseFee[numFunds],fundAfterRiskFees[numFunds];
                REAL fees=0;
                int fbase=scen*360*10+(t-1)*10;
                for (int f=0;f<numFunds_d;++f)
                {
                    fundAfterGrowth[f]=fundCF__1[f]*fundRets[fbase+fundCode[f]]*(1-fundFee[f]/12);
                    riderFee[f]=fundAfterGrowth[f]*riderFee_d/12;
                    baseFee[f]=fundAfterGrowth[f]*baseFee_d/12;
                    fees+=baseFee[f]+riderFee[f];
                    fundAfterRiskFees[f]=fundAfterGrowth[f]-baseFee[f]-riderFee[f];
                    accountValueBeforeGB+=fundAfterRiskFees[f];
                }
                int termOSToRenewal=!hasLivingBen?1200:(termOSToRenewal__1==1?renewalTerm:termOSToRenewal__1-1);
                REAL discFac=discFac__1*discFacMonth;
                REAL gbAmt,gbAmtCF;
                #ifdef debug
                    if (scen==8&&t==29)
                        printf("","");
                #endif
                switch(productType)
                {
                    case ABRP:
                        gbAmt=termOSToRenewal__1==1?max(gbAmtCF__1,accountValueBeforeGB):gbAmtCF__1;
                        break;
                    case DBIB:
                    case DBMB:
                    case DBSU:
                    case DBWB:
                    case IBSU:
                    case MBSU:
                    case WBSU:
                        gbAmt=termIFMonths==0?max(gbAmtCF__1,accountValueBeforeGB):gbAmtCF__1;
                        break;
                    case ABRU:
                        gbAmt=termOSToRenewal__1==1?max(gbAmtCF__1*rollupMonthly,accountValueBeforeGB):gbAmtCF__1*rollupMonthly;
                        break;
                    case ABSU:
                    case DBAB:
                        gbAmt=(termIFMonths==0||termOSToRenewal__1==1)?max(gbAmtCF__1,accountValueBeforeGB):gbAmtCF__1;
                        break;
                    case DBRP:
                    case IBRP:
                    case MBRP:
                    case WBRP:
                        gbAmt=gbAmt_d*survCF__1;
                        break;
                    case DBRU:
                    case IBRU:
                    case MBRU:
                    case WBRU:
                        gbAmt=gbAmtCF__1*rollupMonthly;
                        break;
                    default:
                        gbAmt=0;
                };
                REAL wdlAmt=0;
                REAL gmwbBalance;
                if (hasWithdrawalBen)
                    if (t==termOS)
                        wdlAmt=gmwbBalance__1;
                    else
                        wdlAmt=termIFMonths!=0?0:min(wbWithdrawalRate*gbAmt,gmwbBalance__1);

                REAL wdlBen=!hasWithdrawalBen?0:max(0.0f,wdlAmt-accountValueBeforeGB);

                REAL mktAnnFac=0;
                if (hasIB&&t==termOS)
                {
                    REAL disc=1;
                    REAL annDisc=1/(1+annDiscRate[scen*360+t-1]);
                    for (int i=0;i<55;++i,disc*=annDisc)
                        mktAnnFac+=annSurv[i]*disc;
                }

                int ageMonths=ageMonths__1+1;
                if (ageMonths==12)
                    ageMonths=0;

                int ageYears=ageMonths!=0?ageYears__1:ageYears__1+1;

                REAL qx=1-pow(1-mort_pre_ret[ageYears][sex],1./12.);

                REAL deathBen=0;
                if (hasDeathBen)
                    if (!hasWithdrawalBen)
                        deathBen=max(0.0f,gbAmt-accountValueBeforeGB)*qx;
                    else
                        deathBen=max(0.0f,gmwbBalance__1-wdlAmt-accountValueBeforeGB)*qx;

                gmwbBalance=(gmwbBalance__1-wdlAmt)*(1-qx);

                gbAmtCF=gbAmt*(1-qx);

                REAL livingBen=0;
                if (hasLivingBen)
                    livingBen=(termOSToRenewal__1 == 1)?max(0.0f,gbAmt-accountValueBeforeGB)*(1-qx):0;

                REAL accountValueAfterGB=max(0.0f,accountValueBeforeGB+livingBen-wdlAmt);

                REAL fundAfterGB[numFunds],fundCF[numFunds];
                for (int f=0;f<numFunds_d;++f)
                {
                    fundAfterGB[f]=fundAfterRiskFees[f]*accountValueAfterGB/(accountValueBeforeGB+eps);
                    fundCF[f]=fundAfterGB[f]*(1-qx);
                }

                REAL matyBen=0;
                if (hasMatyBen)
                    matyBen=(t==termOS)?max(0.0f,gbAmt-accountValueBeforeGB)*(1-qx):0;

                REAL incomeBen=0;
                if (hasIB)
                    incomeBen=(t==termOS)?max(0.0f,gbAmtCF*mktAnnFac/gteedAnnFac-accountValueBeforeGB*(1-qx)):0;

                REAL survCF=survCF__1*(1-qx);

                pvCOG+=discFac*(livingBen*(1-qx)+deathBen+incomeBen+wdlBen+matyBen-fees);
                #ifdef debug
                if (incomeBen>0)
                    printf("","");
                if (isnan(pvCOG)||isinf(pvCOG))
                    printf("","");
                if (livingBen>0)
                    printf("","");
                if (scen==8&&t==29)
                    printf("","");
                ofile<<scen<<" "<<t<<" "<<discFac*(livingBen*(1-qx)+deathBen+incomeBen+wdlBen+matyBen-fees)<<" "<<gbAmt<<" "<<accountValueBeforeGB<<"\n";
                #endif

                //roll forward
                survCF__1=survCF;
                termIFMonths__1=termIFMonths;
                termOSToRenewal__1=termOSToRenewal;
                gbAmtCF__1=gbAmtCF;
                discFac__1=discFac;
                gmwbBalance__1=gmwbBalance;
                ageMonths__1=ageMonths;
                ageYears__1=ageYears;
                for (int f=0;f<numFunds_d;++f)
                    fundCF__1[f]=fundCF[f];
            }
            cog+=pvCOG/numScens;
        }
        //cog
        totCOG+=cog;
    }

    delete[]fundRets;
    delete []annDiscRate;

    delete []sexes;
    delete []productTypes;
    delete []ageYears_ds;
    delete []ageMonths_ds;
    delete []numFunds_ds;
    delete []fundCodes;
    delete []termOSs;
    delete []elapsedMonthss;
    delete []termToNextRenewals;
    delete []renewalTerms;

    delete []baseFee_ds;
    delete []riderFee_ds;
    delete []rollUpRates;
    delete []gbAmt_ds;
    delete []gmwbBalance_ds;
    delete []wbWithdrawalRates;
    delete []withdrawals;
    delete []gteedAnnFacs;
    delete []fundValues;
    delete []fundFees;

    printf("COG=%f",totCOG);
    return 0;
}
